import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine

from app.ingest.captioning import CAPTION_ERRORS, Captioner
from app.ingest.checksums import VerifiedDocument
from app.ingest.chunking import Chunk, chunk_pages
from app.ingest.embedding import Embedder
from app.ingest.figures import Figure, extract_figures
from app.ingest.parsing import parse_pdf
from app.repositories.chunks import ChunkRepository, ChunkRow
from app.repositories.documents import DocumentRepository

logger = structlog.get_logger(__name__)

CAPTION_CONCURRENCY = 8


@dataclass
class PipelineIndexer:
    """Parse -> chunk -> embed -> caption -> write, per document."""

    embedder: Embedder
    captioner: Captioner
    documents: DocumentRepository
    chunks: ChunkRepository
    chunk_tokens: int
    chunk_overlap: int

    async def index(self, doc: VerifiedDocument) -> int:
        if await self.documents.is_indexed(doc.name, doc.sha256):
            logger.info("document_already_indexed", document=doc.name)
            return 0

        parsed = parse_pdf(doc.path)
        text_chunks = chunk_pages(
            parsed.pages,
            chunk_tokens=self.chunk_tokens,
            chunk_overlap=self.chunk_overlap,
            count_tokens=self.embedder.count_tokens,
        )
        rows = self._text_rows(text_chunks)
        rows += await asyncio.to_thread(self._figure_rows, doc.path, parsed.page_offset)

        document_id = await self.documents.insert(
            title=doc.name,
            filename=doc.name,
            sha256=doc.sha256,
            page_count=len(parsed.pages),
        )
        await self.chunks.insert_many(document_id, rows)
        logger.info("document_indexed", document=doc.name, chunk_count=len(rows))
        return len(rows)

    def _text_rows(self, chunks: list[Chunk]) -> list[ChunkRow]:
        if not chunks:
            return []
        embeddings = self.embedder.embed_documents([chunk.content for chunk in chunks])
        return [
            ChunkRow(
                content=chunk.content,
                embedding=embedding,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                section=chunk.section,
                chunk_type="text",
                figure_ref=None,
                token_count=chunk.token_count,
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]

    def _figure_rows(self, path: Path, page_offset: int) -> list[ChunkRow]:
        figures = extract_figures(path)
        with ThreadPoolExecutor(max_workers=CAPTION_CONCURRENCY) as pool:
            captions = list(pool.map(self._caption_or_none, figures))
        captioned = [
            (figure, caption)
            for figure, caption in zip(figures, captions, strict=True)
            if caption is not None
        ]
        if not captioned:
            return []
        embeddings = self.embedder.embed_documents(
            [caption for _, caption in captioned]
        )
        return [
            ChunkRow(
                content=caption,
                embedding=embedding,
                page_start=max(1, figure.page - page_offset),
                page_end=max(1, figure.page - page_offset),
                section=None,
                chunk_type="figure_caption",
                # figure_ref keeps the raw physical page — it identifies the
                # figure within extract_figures's own output, not a citation.
                figure_ref=f"page-{figure.page}-fig-{figure.index}",
                token_count=self.embedder.count_tokens(caption),
            )
            for (figure, caption), embedding in zip(captioned, embeddings, strict=True)
        ]

    def _caption_or_none(self, figure: Figure) -> str | None:
        try:
            return self.captioner.caption(figure.image_bytes)
        except CAPTION_ERRORS:
            logger.warning(
                "figure_captioning_failed", page=figure.page, index=figure.index
            )
            return None


async def index_all(
    engine: AsyncEngine,
    embedder: Embedder,
    captioner: Captioner,
    verified: list[VerifiedDocument],
    *,
    chunk_tokens: int,
    chunk_overlap: int,
) -> int:
    """Index each document in its own transaction.

    A crash partway through a long captioning run (many figures, slow VLM
    calls) shouldn't roll back documents that already finished — each one
    commits independently, and the idempotency check lets a re-run resume.
    """
    total = 0
    for doc in verified:
        async with engine.begin() as connection:
            indexer = PipelineIndexer(
                embedder=embedder,
                captioner=captioner,
                documents=DocumentRepository(connection),
                chunks=ChunkRepository(connection),
                chunk_tokens=chunk_tokens,
                chunk_overlap=chunk_overlap,
            )
            total += await indexer.index(doc)
    return total
