"""Slow suite: repositories against a real Postgres + pgvector.

Requires DATABASE_URL pointing at a reachable Postgres with migrations
applied. Run with: pytest -m slow
"""

import os

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from app.repositories.chunks import ChunkRepository, ChunkRow
from app.repositories.documents import DocumentRepository
from app.repositories.schema import chunks_table

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        "DATABASE_URL" not in os.environ, reason="requires a real database"
    ),
]


@pytest.fixture
async def connection():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.connect() as conn:
        transaction = await conn.begin()
        yield conn
        await transaction.rollback()
    await engine.dispose()


async def test_insert_document_then_reports_it_as_indexed(connection):
    repo = DocumentRepository(connection)

    document_id = await repo.insert(
        title="ENVY Guide", filename="envy.pdf", sha256="a" * 64, page_count=135
    )

    assert isinstance(document_id, int)
    assert await repo.is_indexed("envy.pdf", "a" * 64) is True
    assert await repo.is_indexed("envy.pdf", "b" * 64) is False
    assert await repo.is_indexed("other.pdf", "a" * 64) is False


async def test_insert_many_chunks_populates_tsv_and_embedding(connection):
    documents = DocumentRepository(connection)
    document_id = await documents.insert(
        title="ENVY Guide", filename="envy.pdf", sha256="c" * 64, page_count=1
    )
    rows = [
        ChunkRow(
            content="Open the front cover and slide out the tray.",
            embedding=[0.1] * 640,
            page_start=1,
            page_end=1,
            section="Setup",
            chunk_type="text",
            figure_ref=None,
            token_count=9,
        ),
        ChunkRow(
            content="A photo of the printer's cartridge access door.",
            embedding=[0.2] * 640,
            page_start=2,
            page_end=2,
            section=None,
            chunk_type="figure_caption",
            figure_ref="page-2-fig-0",
            token_count=8,
        ),
    ]

    await ChunkRepository(connection).insert_many(document_id, rows)

    result = await connection.execute(
        sa.select(
            chunks_table.c.content,
            chunks_table.c.chunk_index,
            chunks_table.c.chunk_type,
            chunks_table.c.tsv,
        )
        .where(chunks_table.c.document_id == document_id)
        .order_by(chunks_table.c.chunk_index)
    )
    stored = result.all()
    assert [row.chunk_index for row in stored] == [0, 1]
    assert [row.chunk_type for row in stored] == ["text", "figure_caption"]
    assert all(row.tsv is not None for row in stored)


async def test_insert_many_is_a_no_op_for_an_empty_list(connection):
    documents = DocumentRepository(connection)
    document_id = await documents.insert(
        title="ENVY Guide", filename="envy.pdf", sha256="d" * 64, page_count=1
    )

    await ChunkRepository(connection).insert_many(document_id, [])

    result = await connection.execute(
        sa.select(sa.func.count())
        .select_from(chunks_table)
        .where(chunks_table.c.document_id == document_id)
    )
    assert result.scalar_one() == 0
