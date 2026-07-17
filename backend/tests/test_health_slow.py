"""Slow suite: the real application against a real PostgreSQL.

Requires DATABASE_URL pointing at a reachable Postgres with migrations applied.
Run with: pytest -m slow
"""

import os

import httpx
import pytest

from app.config import get_settings
from app.main import create_app, lifespan

pytestmark = pytest.mark.slow


@pytest.mark.skipif("DATABASE_URL" not in os.environ, reason="requires a real database")
async def test_health_ok_against_real_postgres():
    get_settings.cache_clear()
    app = create_app()

    async with lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["checks"]["database"] == "ok"
    get_settings.cache_clear()
