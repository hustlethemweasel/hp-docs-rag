import uuid
from dataclasses import dataclass
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

from app.repositories.schema import conversations_table


@dataclass(frozen=True)
class ConversationSummary:
    id: uuid.UUID
    title: str
    updated_at: datetime


class ConversationRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def create(self, user_id: uuid.UUID) -> uuid.UUID:
        result = await self._connection.execute(
            conversations_table.insert()
            .values(user_id=user_id, title="")
            .returning(conversations_table.c.id)
        )
        return result.scalar_one()

    async def list_for_user(self, user_id: uuid.UUID) -> list[ConversationSummary]:
        result = await self._connection.execute(
            self._summary_select()
            .where(conversations_table.c.user_id == user_id)
            .order_by(conversations_table.c.updated_at.desc())
        )
        return [self._summary(row) for row in result]

    async def get(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> ConversationSummary | None:
        result = await self._connection.execute(
            self._summary_select().where(
                conversations_table.c.id == conversation_id,
                conversations_table.c.user_id == user_id,
            )
        )
        row = result.first()
        return self._summary(row) if row is not None else None

    async def set_title(self, conversation_id: uuid.UUID, title: str) -> None:
        await self._connection.execute(
            conversations_table.update()
            .where(conversations_table.c.id == conversation_id)
            .values(title=title)
        )

    async def touch(self, conversation_id: uuid.UUID) -> None:
        await self._connection.execute(
            conversations_table.update()
            .where(conversations_table.c.id == conversation_id)
            .values(updated_at=sa.func.now())
        )

    async def delete(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result = await self._connection.execute(
            conversations_table.delete().where(
                conversations_table.c.id == conversation_id,
                conversations_table.c.user_id == user_id,
            )
        )
        return result.rowcount > 0

    @staticmethod
    def _summary_select() -> sa.Select:
        return sa.select(
            conversations_table.c.id,
            conversations_table.c.title,
            conversations_table.c.updated_at,
        )

    @staticmethod
    def _summary(row: sa.Row) -> ConversationSummary:
        return ConversationSummary(
            id=row.id, title=row.title, updated_at=row.updated_at
        )
