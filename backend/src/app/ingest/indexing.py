import asyncio
from dataclasses import dataclass
from pathlib import Path

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncEngine

from app.ingest.captioning import OllamaCaptioner
from app.ingest.checksums import VerifiedDocument
from app.ingest.chunking import Chunk, chunk_pages
from app.ingest.embedding import Embedder
from app.ingest.figures import extract_figures
from app.ingest.parsing import parse_pdf
from app.repositories.chunks import ChunkRepository, ChunkRow
from app.repositories.documents import DocumentRepository

logger = structlog.get_logger(__name__)


@dataclass
class PipelineIndexer:
    """Parse -> chunk -> embed -> caption -> write, per document (SPEC §7)."""

    embedder: Embedder
    captioner: OllamaCaptioner
    documents: DocumentRepository
    chunks: ChunkRepository
    chunk_tokens: int
    chunk_overlap: int

    async def index(self, doc: VerifiedDocument) -> int:
        if await self.documents.is_indexed(doc.name, doc.sha256):
            logger.info("document_already_indexed", document=doc.name)
            return 0

        pages = parse_pdf(doc.path)
        text_chunks = chunk_pages(
            pages,
            chunk_tokens=self.chunk_tokens,
            chunk_overlap=self.chunk_overlap,
            count_tokens=self.embedder.count_tokens,
        )
        rows = self._text_rows(text_chunks)
        rows += await asyncio.to_thread(self._figure_rows, doc.path)

        document_id = await self.documents.insert(
            title=doc.name, filename=doc.name, sha256=doc.sha256, page_count=len(pages)
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

    def _figure_rows(self, path: Path) -> list[ChunkRow]:
        rows = []
        for figure in extract_figures(path):
            try:
                caption = self.captioner.caption(figure.image_bytes)
            except httpx.HTTPError:
                logger.warning(
                    "figure_captioning_failed", page=figure.page, index=figure.index
                )
                continue
            [embedding] = self.embedder.embed_documents([caption])
            rows.append(
                ChunkRow(
                    content=caption,
                    embedding=embedding,
                    page_start=figure.page,
                    page_end=figure.page,
                    section=None,
                    chunk_type="figure_caption",
                    figure_ref=f"page-{figure.page}-fig-{figure.index}",
                    token_count=self.embedder.count_tokens(caption),
                )
            )
        return rows


async def index_all(
    engine: AsyncEngine,
    embedder: Embedder,
    captioner: OllamaCaptioner,
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
