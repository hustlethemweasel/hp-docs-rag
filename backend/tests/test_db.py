"""Behavior: the Database boundary pings truthfully.

Real collaborator: an actual SQLAlchemy async engine (in-process SQLite), so
the fast suite stays self-contained without doubling the thing under test.
"""

from sqlalchemy.pool import QueuePool

from app.db import Database


async def test_ping_true_against_reachable_database():
    database = Database.from_url("sqlite+aiosqlite:///:memory:")

    assert await database.ping() is True

    await database.dispose()


async def test_ping_false_when_database_unreachable():
    database = Database.from_url("sqlite+aiosqlite:////nonexistent/nope/x.db")

    assert await database.ping() is False

    await database.dispose()


def test_from_url_applies_a_configured_pool_size():
    """pool_size/max_overflow are QueuePool-only kwargs (SQLite's default
    StaticPool rejects them, per the tests above omitting them) — engine
    construction is lazy, so this doesn't need a live Postgres to verify
    they're actually applied.
    """
    database = Database.from_url(
        "postgresql+asyncpg://user:pass@localhost/db",
        pool_size=20,
        max_overflow=20,
    )

    pool = database.engine.pool
    assert isinstance(pool, QueuePool)
    assert pool.size() == 20


async def test_from_url_ignores_pool_kwargs_for_sqlite():
    """SQLite's StaticPool (a single embedded-file connection) rejects
    pool_size/max_overflow outright; real app startup always passes them
    (from Settings' defaults) regardless of dialect, so this must be a
    silent no-op rather than a crash — not just a test convenience.
    """
    database = Database.from_url(
        "sqlite+aiosqlite:///:memory:", pool_size=20, max_overflow=20
    )

    assert await database.ping() is True

    await database.dispose()
