from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

from app.repositories.schema import chunks_table, documents_table


def or_websearch(query: str) -> str:
    """Rewrite free text into websearch OR-syntax, one quoted term per word.

    websearch_to_tsquery ANDs every word by default, which defeats
    exact-token lookups: the chunk holding the token must also contain
    every ordinary word around it. Quoting keeps hyphenated tokens like
    part numbers intact as phrase queries; stop words drop out server-side.
    """
    words = [word.replace('"', "") for word in query.split()]
    return " OR ".join(f'"{word}"' for word in words if word)


@dataclass(frozen=True)
class ChunkRow:
    content: str
    embedding: list[float]
    page_start: int
    page_end: int
    section: str | None
    chunk_type: str
    figure_ref: str | None
    token_count: int


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    document: str
    content: str
    page_start: int
    page_end: int
    section: str | None
    figure_ref: str | None
    score: float


class ChunkRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def insert_many(self, document_id: int, rows: list[ChunkRow]) -> None:
        """Bulk-insert chunks, computing tsv server-side.

        chunk_index is assigned from row order, not carried by ChunkRow, so
        callers don't have to keep an external counter in sync.
        """
        if not rows:
            return
        stmt = chunks_table.insert().values(
            document_id=sa.bindparam("document_id"),
            content=sa.bindparam("content"),
            embedding=sa.bindparam("embedding"),
            tsv=sa.func.to_tsvector("english", sa.bindparam("content")),
            page_start=sa.bindparam("page_start"),
            page_end=sa.bindparam("page_end"),
            section=sa.bindparam("section"),
            chunk_type=sa.bindparam("chunk_type"),
            figure_ref=sa.bindparam("figure_ref"),
            token_count=sa.bindparam("token_count"),
            chunk_index=sa.bindparam("chunk_index"),
        )
        params = [
            {
                "document_id": document_id,
                "content": row.content,
                "embedding": row.embedding,
                "page_start": row.page_start,
                "page_end": row.page_end,
                "section": row.section,
                "chunk_type": row.chunk_type,
                "figure_ref": row.figure_ref,
                "token_count": row.token_count,
                "chunk_index": index,
            }
            for index, row in enumerate(rows)
        ]
        await self._connection.execute(stmt, params)

    async def dense_search(
        self, embedding: list[float], *, limit: int
    ) -> list[RetrievedChunk]:
        """Top chunks by cosine similarity (score = 1 - cosine distance)."""
        distance = chunks_table.c.embedding.cosine_distance(embedding)
        result = await self._connection.execute(
            self._retrieval_select((1 - distance).label("score"))
            .order_by(distance, chunks_table.c.id)
            .limit(limit)
        )
        return [self._retrieved(row) for row in result]

    async def sparse_search(self, query: str, *, limit: int) -> list[RetrievedChunk]:
        """Top chunks by Postgres full-text rank, OR-of-words semantics."""
        tsquery = sa.func.websearch_to_tsquery("english", or_websearch(query))
        score = sa.func.ts_rank(chunks_table.c.tsv, tsquery)
        result = await self._connection.execute(
            self._retrieval_select(score.label("score"))
            .where(chunks_table.c.tsv.op("@@")(tsquery))
            .order_by(score.desc(), chunks_table.c.id)
            .limit(limit)
        )
        return [self._retrieved(row) for row in result]

    def _retrieval_select(self, score: sa.ColumnElement[float]) -> sa.Select:
        return sa.select(
            chunks_table.c.id,
            documents_table.c.title,
            chunks_table.c.content,
            chunks_table.c.page_start,
            chunks_table.c.page_end,
            chunks_table.c.section,
            chunks_table.c.figure_ref,
            score,
        ).join_from(
            chunks_table,
            documents_table,
            chunks_table.c.document_id == documents_table.c.id,
        )

    @staticmethod
    def _retrieved(row: sa.Row) -> RetrievedChunk:
        return RetrievedChunk(
            chunk_id=row.id,
            document=row.title,
            content=row.content,
            page_start=row.page_start,
            page_end=row.page_end,
            section=row.section,
            figure_ref=row.figure_ref,
            score=float(row.score),
        )
