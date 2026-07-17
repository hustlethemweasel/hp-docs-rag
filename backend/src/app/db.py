from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from sqlalchemy import make_url, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

logger = structlog.get_logger(__name__)


class Database:
    """Thin boundary around the async engine, kept logic-free per the constitution."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @classmethod
    def from_url(
        cls,
        url: str,
        *,
        pool_size: int | None = None,
        max_overflow: int | None = None,
    ) -> "Database":
        # pool_size/max_overflow tune QueuePool, meaningless for SQLite's
        # StaticPool (a single embedded-file connection, not a server pool)
        # — SQLite rejects the kwargs outright, so they're only applied for
        # dialects that actually pool connections.
        pool_kwargs: dict[str, int] = {}
        if make_url(url).get_dialect().name != "sqlite":
            if pool_size is not None:
                pool_kwargs["pool_size"] = pool_size
            if max_overflow is not None:
                pool_kwargs["max_overflow"] = max_overflow
        # pool_pre_ping: discard a connection silently closed underneath the
        # pool (e.g. by a cancelled/disconnected request) instead of
        # surfacing InterfaceError on the next checkout — see loadtest/REPORT.md.
        return cls(create_async_engine(url, pool_pre_ping=True, **pool_kwargs))

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
