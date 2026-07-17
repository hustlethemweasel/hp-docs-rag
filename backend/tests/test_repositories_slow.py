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


def unit_vector(axis: int) -> list[float]:
    vector = [0.0] * 640
    vector[axis] = 1.0
    return vector


@pytest.fixture
async def searchable_document(connection):
    documents = DocumentRepository(connection)
    document_id = await documents.insert(
        title="ENVY Guide", filename="envy.pdf", sha256="e" * 64, page_count=3
    )
    rows = [
        ChunkRow(
            content="Replace the cartridge when the ink level is low.",
            embedding=unit_vector(0),
            page_start=1,
            page_end=1,
            section="Cartridges",
            chunk_type="text",
            figure_ref=None,
            token_count=9,
        ),
        ChunkRow(
            content="Connect the printer to a Wi-Fi network.",
            embedding=unit_vector(1),
            page_start=2,
            page_end=2,
            section="Networking",
            chunk_type="text",
            figure_ref=None,
            token_count=8,
        ),
        ChunkRow(
            content="Order replacement part M08117-001 from HP support.",
            embedding=unit_vector(2),
            page_start=3,
            page_end=3,
            section="Parts",
            chunk_type="text",
            figure_ref=None,
            token_count=8,
        ),
    ]
    await ChunkRepository(connection).insert_many(document_id, rows)
    return document_id


async def test_dense_search_ranks_by_cosine_similarity(connection, searchable_document):
    query = [0.0] * 640
    query[1] = 0.9  # nearest the Wi-Fi chunk's axis
    query[0] = 0.1

    hits = await ChunkRepository(connection).dense_search(query, limit=2)

    assert len(hits) == 2
    assert hits[0].content == "Connect the printer to a Wi-Fi network."
    assert hits[0].document == "ENVY Guide"
    assert hits[0].page_start == 2
    assert hits[0].section == "Networking"
    assert hits[0].score > hits[1].score
    assert 0.0 <= hits[1].score <= hits[0].score <= 1.0


async def test_sparse_search_matches_exact_tokens(connection, searchable_document):
    hits = await ChunkRepository(connection).sparse_search("M08117-001", limit=5)

    assert len(hits) == 1
    assert hits[0].content == "Order replacement part M08117-001 from HP support."
    assert hits[0].document == "ENVY Guide"
    assert hits[0].score > 0


async def test_sparse_search_returns_nothing_for_unmatched_terms(
    connection, searchable_document
):
    hits = await ChunkRepository(connection).sparse_search(
        "quantum entanglement", limit=5
    )

    assert hits == []


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
