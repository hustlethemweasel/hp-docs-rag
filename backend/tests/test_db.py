"""Behavior: the Database boundary pings truthfully.

Real collaborator: an actual SQLAlchemy async engine (in-process SQLite), so
the fast suite stays self-contained without doubling the thing under test.
"""

from app.db import Database


async def test_ping_true_against_reachable_database():
    database = Database.from_url("sqlite+aiosqlite:///:memory:")

    assert await database.ping() is True

    await database.dispose()


async def test_ping_false_when_database_unreachable():
    database = Database.from_url("sqlite+aiosqlite:////nonexistent/nope/x.db")

    assert await database.ping() is False

    await database.dispose()
