"""Behavior: GET /api/health reports liveness and database readiness.

The fast suite is self-contained (per the constitution): the database boundary is
replaced with an autospec'd double that honors the real Database interface.
"""

from unittest.mock import create_autospec

import httpx
import pytest

from app.db import Database
from app.main import create_app


def app_with_database(database: Database):
    app = create_app()
    app.state.database = database
    return app


@pytest.fixture
def database() -> Database:
    return create_autospec(Database, instance=True)


async def get_health(app) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/api/health")


async def test_health_ok_when_database_reachable(database):
    database.ping.return_value = True

    response = await get_health(app_with_database(database))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"


async def test_health_degraded_when_database_unreachable(database):
    database.ping.return_value = False

    response = await get_health(app_with_database(database))

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"] == "error"
