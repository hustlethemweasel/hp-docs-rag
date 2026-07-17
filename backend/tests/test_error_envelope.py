"""Behavior: every error response — expected (404s raised as HTTPException)
or unhandled (a bug propagating out of a route) — comes back as the same
structured JSON envelope, `{"error": {"code", "message", "request_id"}}`,
so clients never special-case FastAPI's default shapes and an unhandled
exception never leaks its internals to the caller.
"""

import uuid
from unittest.mock import create_autospec

import httpx

from app.api.deps import get_conversations
from app.db import Database
from app.main import create_app
from app.repositories.conversations import ConversationRepository


async def _request(app, method: str, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(
            method, path, headers={"X-User-Id": str(uuid.uuid4())}
        )


async def test_http_exception_uses_the_structured_envelope():
    app = create_app()
    conversations = create_autospec(ConversationRepository, instance=True)
    conversations.delete.return_value = False
    app.dependency_overrides[get_conversations] = lambda: conversations

    response = await _request(app, "DELETE", f"/api/conversations/{uuid.uuid4()}")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "conversation not found"
    assert uuid.UUID(body["error"]["request_id"])
    assert response.headers["x-request-id"] == body["error"]["request_id"]


async def test_unhandled_exception_returns_a_generic_500_envelope():
    app = create_app()
    database = create_autospec(Database, instance=True)
    database.ping.side_effect = RuntimeError("boom: leaked internals")
    app.state.database = database

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "boom" not in body["error"]["message"]
    assert uuid.UUID(body["error"]["request_id"])
