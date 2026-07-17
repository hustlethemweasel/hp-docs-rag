"""Behavior: every request gets a request ID — generated if the caller sent
none, echoed back if they did — returned as X-Request-ID so client and
server logs can be correlated for a single request.
"""

import uuid
from unittest.mock import create_autospec

import httpx

from app.db import Database
from app.main import create_app


def _app():
    app = create_app()
    database = create_autospec(Database, instance=True)
    database.ping.return_value = True
    app.state.database = database
    return app


async def _get(app, headers: dict[str, str] | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/api/health", headers=headers or {})


async def test_generates_a_request_id_when_the_caller_sends_none():
    response = await _get(_app())

    request_id = response.headers["x-request-id"]
    assert uuid.UUID(request_id)


async def test_echoes_back_a_caller_supplied_request_id():
    supplied = str(uuid.uuid4())

    response = await _get(_app(), headers={"X-Request-ID": supplied})

    assert response.headers["x-request-id"] == supplied


async def test_each_request_gets_a_distinct_generated_id():
    app = _app()

    first = await _get(app)
    second = await _get(app)

    assert first.headers["x-request-id"] != second.headers["x-request-id"]
