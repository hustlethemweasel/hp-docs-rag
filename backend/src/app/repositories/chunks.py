from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

from app.repositories.schema import chunks_table


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
