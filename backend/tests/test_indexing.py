"""Behavior: parse -> chunk -> embed -> caption -> write orchestration.

Real collaborators: a real synthetic PDF on disk, real parsing/chunking/figure
extraction. The embedder, captioner, and repositories are the genuine external
boundaries (model weights, HTTP, DB) — doubled with create_autospec.
"""

from unittest.mock import create_autospec

import fitz
import httpx

from app.ingest.captioning import OllamaCaptioner
from app.ingest.checksums import VerifiedDocument
from app.ingest.embedding import Embedder
from app.ingest.indexing import PipelineIndexer
from app.repositories.chunks import ChunkRepository
from app.repositories.documents import DocumentRepository


def solid_pixmap(width: int, height: int, color: tuple[int, int, int]) -> fitz.Pixmap:
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, width, height), False)
    pix.set_rect(pix.irect, color)
    return pix


def build_pdf(path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Cartridge Replacement", fontsize=18, fontname="helv")
    page.insert_text(
        (72, 110),
        "Open the front cover and slide out the tray.",
        fontsize=10,
        fontname="helv",
    )
    figure = solid_pixmap(200, 200, (255, 0, 0))
    page.insert_image(fitz.Rect(72, 300, 272, 500), pixmap=figure)
    doc.save(str(path))


def make_indexer(*, already_indexed: bool = False):
    embedder = create_autospec(Embedder, instance=True)
    embedder.count_tokens.side_effect = lambda text: len(text.split())
    embedder.embed_documents.side_effect = lambda texts: [[0.0] * 640 for _ in texts]
    captioner = create_autospec(OllamaCaptioner, instance=True)
    captioner.caption.return_value = "A photo of the cartridge access door."
    documents = create_autospec(DocumentRepository, instance=True)
    documents.is_indexed.return_value = already_indexed
    documents.insert.return_value = 42
    chunks = create_autospec(ChunkRepository, instance=True)

    indexer = PipelineIndexer(
        embedder=embedder,
        captioner=captioner,
        documents=documents,
        chunks=chunks,
        chunk_tokens=450,
        chunk_overlap=80,
    )
    return indexer, embedder, captioner, documents, chunks


async def test_skips_an_already_indexed_document(tmp_path):
    build_pdf(tmp_path / "envy.pdf")
    doc = VerifiedDocument(name="envy.pdf", path=tmp_path / "envy.pdf", sha256="a" * 64)
    indexer, _, _, documents, chunks = make_indexer(already_indexed=True)

    count = await indexer.index(doc)

    assert count == 0
    chunks.insert_many.assert_not_called()
    documents.insert.assert_not_called()


async def test_indexes_text_and_figure_chunks(tmp_path):
    build_pdf(tmp_path / "envy.pdf")
    doc = VerifiedDocument(name="envy.pdf", path=tmp_path / "envy.pdf", sha256="a" * 64)
    indexer, embedder, captioner, documents, chunks = make_indexer()

    count = await indexer.index(doc)

    documents.insert.assert_called_once_with(
        title="envy.pdf", filename="envy.pdf", sha256="a" * 64, page_count=1
    )
    captioner.caption.assert_called_once()
    document_id, rows = chunks.insert_many.call_args.args
    assert document_id == 42
    assert count == len(rows)

    text_rows = [r for r in rows if r.chunk_type == "text"]
    figure_rows = [r for r in rows if r.chunk_type == "figure_caption"]
    assert len(text_rows) == 1
    assert text_rows[0].section == "Cartridge Replacement"
    assert text_rows[0].content == "Open the front cover and slide out the tray."
    assert len(figure_rows) == 1
    assert figure_rows[0].content == "A photo of the cartridge access door."
    assert figure_rows[0].figure_ref == "page-1-fig-0"
    assert figure_rows[0].page_start == 1
    assert all(len(r.embedding) == 640 for r in rows)


async def test_indexes_only_figures_when_a_page_has_no_extractable_text(tmp_path):
    doc_path = tmp_path / "envy.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(
        fitz.Rect(72, 300, 272, 500), pixmap=solid_pixmap(200, 200, (255, 0, 0))
    )
    doc.save(str(doc_path))
    verified = VerifiedDocument(name="envy.pdf", path=doc_path, sha256="a" * 64)
    indexer, _, captioner, documents, chunks = make_indexer()

    count = await indexer.index(verified)

    documents.insert.assert_called_once()
    _, rows = chunks.insert_many.call_args.args
    assert count == len(rows) == 1
    assert rows[0].chunk_type == "figure_caption"
    captioner.caption.assert_called_once()


async def test_still_indexes_text_when_captioning_is_unreachable(tmp_path):
    build_pdf(tmp_path / "envy.pdf")
    doc = VerifiedDocument(name="envy.pdf", path=tmp_path / "envy.pdf", sha256="a" * 64)
    indexer, _, captioner, documents, chunks = make_indexer()
    captioner.caption.side_effect = httpx.ConnectError("connection refused")

    count = await indexer.index(doc)

    documents.insert.assert_called_once()
    document_id, rows = chunks.insert_many.call_args.args
    assert count == len(rows) == 1
    assert rows[0].chunk_type == "text"


async def test_one_failed_caption_does_not_drop_the_other_figures(tmp_path):
    doc_path = tmp_path / "envy.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(
        fitz.Rect(72, 100, 272, 300), pixmap=solid_pixmap(200, 200, (255, 0, 0))
    )
    page.insert_image(
        fitz.Rect(300, 100, 500, 300), pixmap=solid_pixmap(200, 200, (0, 0, 255))
    )
    doc.save(str(doc_path))
    verified = VerifiedDocument(name="envy.pdf", path=doc_path, sha256="a" * 64)
    indexer, _, captioner, _, chunks = make_indexer()
    captioner.caption.side_effect = [
        httpx.ConnectError("connection refused"),
        "A diagram of the hinge assembly.",
    ]

    count = await indexer.index(verified)

    _, rows = chunks.insert_many.call_args.args
    figure_rows = [r for r in rows if r.chunk_type == "figure_caption"]
    assert count == len(rows)
    assert len(figure_rows) == 1
    assert figure_rows[0].content == "A diagram of the hinge assembly."
