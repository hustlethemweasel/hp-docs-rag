"""Behavior: the API only allows cross-origin requests from the configured
frontend origin, needed once the browser (a different origin) calls it
directly.

CORS is wired in create_app() itself, not inside lifespan: Starlette locks
its middleware stack on the first ASGI call, including the lifespan
protocol's own dispatch, so these tests drive real HTTP requests through
create_app() (as a real server would) rather than invoking lifespan()
directly as a bare context manager, which would hide that constraint.
"""

from unittest.mock import create_autospec

import httpx

from app.db import Database
from app.main import create_app


def _app_with_database(frontend_origin: str):
    app = create_app(frontend_origin=frontend_origin)
    database = create_autospec(Database, instance=True)
    database.ping.return_value = True
    app.state.database = database
    return app


async def _get(app, origin: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/api/health", headers={"Origin": origin})


async def test_cors_allows_the_configured_frontend_origin():
    app = _app_with_database("http://localhost:3000")

    response = await _get(app, "http://localhost:3000")

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


async def test_cors_rejects_other_origins():
    app = _app_with_database("http://localhost:3000")

    response = await _get(app, "http://evil.example")

    assert "access-control-allow-origin" not in response.headers
