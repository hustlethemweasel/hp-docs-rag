"""Behavior: the API only allows cross-origin requests from the configured
frontend origin, needed once the browser (a different origin) calls it
directly. Exercised with real components end-to-end in-process, mirroring
test_app_lifecycle.py.
"""

import httpx

from app.config import get_settings
from app.main import create_app, lifespan


async def _get(app, origin: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/api/health", headers={"Origin": origin})


async def test_cors_allows_the_configured_frontend_origin(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:3000")
    get_settings.cache_clear()
    app = create_app()

    async with lifespan(app):
        response = await _get(app, "http://localhost:3000")

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    get_settings.cache_clear()


async def test_cors_rejects_other_origins(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:3000")
    get_settings.cache_clear()
    app = create_app()

    async with lifespan(app):
        response = await _get(app, "http://evil.example")

    assert "access-control-allow-origin" not in response.headers
    get_settings.cache_clear()
