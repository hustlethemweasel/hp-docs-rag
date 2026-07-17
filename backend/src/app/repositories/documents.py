import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

from app.repositories.schema import documents_table


class DocumentRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def is_indexed(self, filename: str, sha256: str) -> bool:
        """Idempotency check: already-indexed documents are skipped."""
        result = await self._connection.execute(
            sa.select(documents_table.c.id).where(
                documents_table.c.filename == filename,
                documents_table.c.sha256 == sha256,
            )
        )
        return result.first() is not None

    async def insert(
        self, *, title: str, filename: str, sha256: str, page_count: int
    ) -> int:
        result = await self._connection.execute(
            documents_table.insert()
            .values(
                title=title, filename=filename, sha256=sha256, page_count=page_count
            )
            .returning(documents_table.c.id)
        )
        return result.scalar_one()
