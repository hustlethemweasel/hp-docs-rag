"""Slow suite: the full parse->chunk->embed->caption->write pipeline against
real Postgres, the real harrier embedder, and real Ollama captioning
(SPEC §7, §11).
"""

import os

import fitz
import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from app.ingest.captioning import OllamaCaptioner
from app.ingest.checksums import VerifiedDocument
from app.ingest.embedding import load_embedder
from app.ingest.indexing import index_all
from app.repositories.schema import chunks_table

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        "DATABASE_URL" not in os.environ, reason="requires a real database"
    ),
]


def _ollama_reachable() -> bool:
    try:
        return (
            httpx.get("http://localhost:11434/api/tags", timeout=2).status_code == 200
        )
    except httpx.HTTPError:
        return False


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


@pytest.mark.skipif(
    not _ollama_reachable(), reason="requires a reachable Ollama server"
)
async def test_indexes_a_document_end_to_end_and_is_idempotent(tmp_path):
    build_pdf(tmp_path / "doc.pdf")
    doc = VerifiedDocument(
        name=f"idx-test-{tmp_path.name}.pdf", path=tmp_path / "doc.pdf", sha256="e" * 64
    )
    engine = create_async_engine(os.environ["DATABASE_URL"])
    embedder = load_embedder("microsoft/harrier-oss-v1-270m")
    captioner = OllamaCaptioner(
        client=httpx.Client(base_url="http://localhost:11434", timeout=120),
        model="qwen3.5:4b",
    )

    try:
        first_count = await index_all(
            engine, embedder, captioner, [doc], chunk_tokens=450, chunk_overlap=80
        )
        second_count = await index_all(
            engine, embedder, captioner, [doc], chunk_tokens=450, chunk_overlap=80
        )

        assert first_count == 2  # one text chunk + one figure caption
        assert second_count == 0  # idempotent: already indexed

        async with engine.connect() as connection:
            result = await connection.execute(
                sa.select(sa.func.count())
                .select_from(chunks_table)
                .join(
                    sa.text("documents"), sa.text("chunks.document_id = documents.id")
                )
                .where(sa.text("documents.filename = :f")),
                {"f": doc.name},
            )
            assert result.scalar_one() == 2
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                sa.text(
                    "DELETE FROM chunks WHERE document_id IN "
                    "(SELECT id FROM documents WHERE filename = :f)"
                ),
                {"f": doc.name},
            )
            await connection.execute(
                sa.text("DELETE FROM documents WHERE filename = :f"), {"f": doc.name}
            )
        await engine.dispose()
