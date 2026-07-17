from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

logger = structlog.get_logger(__name__)


class Database:
    """Thin boundary around the async engine, kept logic-free per the constitution."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @classmethod
    def from_url(cls, url: str) -> "Database":
        return cls(create_async_engine(url))

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[AsyncConnection]:
        """A transactional connection for one request's unit of work."""
        async with self._engine.begin() as connection:
            yield connection

    async def ping(self) -> bool:
        try:
            async with self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logger.warning("database_ping_failed")
            return False
        return True

    async def dispose(self) -> None:
        await self._engine.dispose()
