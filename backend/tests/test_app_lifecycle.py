"""Behavior: app startup wires settings, logging, and the database; shutdown
disposes it. Exercised with real components end-to-end in-process.
"""

import httpx

from app.config import get_settings
from app.db import Database
from app.main import create_app, lifespan


async def test_lifespan_wires_real_database_and_serves_health(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    get_settings.cache_clear()
    app = create_app()

    async with lifespan(app):
        assert isinstance(app.state.database, Database)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok"}}
    get_settings.cache_clear()
