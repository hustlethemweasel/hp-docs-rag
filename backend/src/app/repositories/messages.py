import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

from app.repositories.schema import messages_table

Role = Literal["user", "assistant"]
Status = Literal["complete", "error"]


@dataclass(frozen=True)
class MessageRow:
    conversation_id: uuid.UUID
    role: Role
    content: str
    sources: list[dict[str, Any]] | None
    provider: str | None
    model: str | None
    latency_ms: int | None
    status: Status


@dataclass(frozen=True)
class StoredMessage:
    id: uuid.UUID
    role: Role
    content: str
    sources: list[dict[str, Any]] | None
    provider: str | None
    model: str | None
    latency_ms: int | None
    status: str
    created_at: datetime


class MessageRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def insert(self, row: MessageRow) -> uuid.UUID:
        result = await self._connection.execute(
            messages_table.insert()
            .values(
                conversation_id=row.conversation_id,
                role=row.role,
                content=row.content,
                sources=row.sources,
                provider=row.provider,
                model=row.model,
                latency_ms=row.latency_ms,
                status=row.status,
            )
            .returning(messages_table.c.id)
        )
        return result.scalar_one()

    async def list_for_conversation(
        self, conversation_id: uuid.UUID
    ) -> list[StoredMessage]:
        result = await self._connection.execute(
            sa.select(messages_table)
            .where(messages_table.c.conversation_id == conversation_id)
            .order_by(messages_table.c.created_at)
        )
        return [self._stored(row) for row in result]

    @staticmethod
    def _stored(row: sa.Row) -> StoredMessage:
        return StoredMessage(
            id=row.id,
            role=row.role,
            content=row.content,
            sources=row.sources,
            provider=row.provider,
            model=row.model,
            latency_ms=row.latency_ms,
            status=row.status,
            created_at=row.created_at,
        )
