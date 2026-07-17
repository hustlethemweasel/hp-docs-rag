"""Behavior: conversation CRUD + SSE chat endpoint, scoped by X-User-Id.

The fast suite is self-contained: FastAPI dependency overrides substitute
create_autospec'd repositories/chat-service for the real Postgres/embedder
boundaries the routes depend on in production.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import create_autospec

import httpx
import pytest

from app.api.deps import get_chat_service, get_conversations, get_messages, get_user_id
from app.main import create_app
from app.rag.chat_service import ChatService
from app.repositories.conversations import ConversationRepository, ConversationSummary
from app.repositories.messages import MessageRepository, StoredMessage


def client_for(app) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def conversations():
    return create_autospec(ConversationRepository, instance=True)


@pytest.fixture
def messages():
    return create_autospec(MessageRepository, instance=True)


@pytest.fixture
def app(conversations, messages):
    app = create_app()
    app.dependency_overrides[get_conversations] = lambda: conversations
    app.dependency_overrides[get_messages] = lambda: messages
    # FastAPI resolves every declared dependency before the route body runs,
    # even on a path (like a 404) that never uses it; override it here so
    # tests that don't care about chat_service don't need app.state wired.
    app.dependency_overrides[get_chat_service] = lambda: create_autospec(
        ChatService, instance=True
    )
    return app


def summary(conversation_id: uuid.UUID, title: str = "") -> ConversationSummary:
    return ConversationSummary(
        id=conversation_id, title=title, updated_at=datetime.now(UTC)
    )


# --- X-User-Id header handling (real get_user_id, no override) --------------


async def test_missing_user_id_header_returns_422(app):
    async with client_for(app) as client:
        response = await client.post("/api/conversations")

    assert response.status_code == 422


async def test_create_conversation_uses_the_real_user_id_header(
    app, conversations, user_id
):
    conversation_id = uuid.uuid4()
    conversations.create.return_value = conversation_id
    conversations.get.return_value = summary(conversation_id)

    async with client_for(app) as client:
        response = await client.post(
            "/api/conversations", headers={"X-User-Id": str(user_id)}
        )

    assert response.status_code == 201
    conversations.create.assert_called_once_with(user_id)


# --- CRUD (get_user_id overridden for brevity) -------------------------------


@pytest.fixture
def app_as(app, user_id):
    app.dependency_overrides[get_user_id] = lambda: user_id
    return app


async def test_create_conversation_returns_the_new_summary(
    app_as, conversations, user_id
):
    conversation_id = uuid.uuid4()
    conversations.create.return_value = conversation_id
    conversations.get.return_value = summary(conversation_id, title="")

    async with client_for(app_as) as client:
        response = await client.post("/api/conversations")

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == str(conversation_id)
    assert body["title"] == ""


async def test_list_conversations_returns_summaries(app_as, conversations):
    ids = [uuid.uuid4(), uuid.uuid4()]
    conversations.list_for_user.return_value = [summary(i) for i in ids]

    async with client_for(app_as) as client:
        response = await client.get("/api/conversations")

    assert response.status_code == 200
    assert [c["id"] for c in response.json()] == [str(i) for i in ids]


async def test_get_conversation_returns_messages(app_as, conversations, messages):
    conversation_id = uuid.uuid4()
    conversations.get.return_value = summary(conversation_id, title="Cartridges")
    messages.list_for_conversation.return_value = [
        StoredMessage(
            id=uuid.uuid4(),
            role="user",
            content="How do I replace it?",
            sources=None,
            provider=None,
            model=None,
            latency_ms=None,
            status="complete",
            created_at=datetime.now(UTC),
        )
    ]

    async with client_for(app_as) as client:
        response = await client.get(f"/api/conversations/{conversation_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Cartridges"
    assert body["messages"][0]["content"] == "How do I replace it?"


async def test_get_conversation_returns_404_when_not_found(app_as, conversations):
    conversations.get.return_value = None

    async with client_for(app_as) as client:
        response = await client.get(f"/api/conversations/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_delete_conversation_returns_204(app_as, conversations):
    conversations.delete.return_value = True

    async with client_for(app_as) as client:
        response = await client.delete(f"/api/conversations/{uuid.uuid4()}")

    assert response.status_code == 204


async def test_delete_conversation_returns_404_when_not_owned(app_as, conversations):
    conversations.delete.return_value = False

    async with client_for(app_as) as client:
        response = await client.delete(f"/api/conversations/{uuid.uuid4()}")

    assert response.status_code == 404


# --- SSE chat endpoint --------------------------------------------------------


async def test_send_message_returns_404_for_an_unknown_conversation(
    app_as, conversations
):
    conversations.get.return_value = None

    async with client_for(app_as) as client:
        response = await client.post(
            f"/api/conversations/{uuid.uuid4()}/messages", json={"content": "hi"}
        )

    assert response.status_code == 404


async def test_send_message_streams_sse_events_from_the_chat_service(
    app_as, conversations
):
    conversation_id = uuid.uuid4()
    conversations.get.return_value = summary(conversation_id)

    async def scripted_events(conv_id, content):
        assert conv_id == conversation_id
        assert content == "How do I open it?"
        yield 'event: token\ndata: {"text": "Open"}\n\n'
        yield 'event: done\ndata: {"sources": []}\n\n'

    chat_service = create_autospec(ChatService, instance=True)
    chat_service.stream_message.side_effect = scripted_events
    app_as.dependency_overrides[get_chat_service] = lambda: chat_service

    async with (
        client_for(app_as) as client,
        client.stream(
            "POST",
            f"/api/conversations/{conversation_id}/messages",
            json={"content": "How do I open it?"},
        ) as response,
    ):
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join([chunk async for chunk in response.aiter_text()])

    assert "event: token" in body
    assert "event: done" in body
