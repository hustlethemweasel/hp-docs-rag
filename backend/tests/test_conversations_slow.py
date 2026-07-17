"""Slow suite: conversation/message repositories against a real Postgres.

Requires DATABASE_URL pointing at a reachable Postgres with migrations
applied. Run with: pytest -m slow
"""

import os
import uuid

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.repositories.conversations import ConversationRepository
from app.repositories.messages import MessageRepository, MessageRow

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        "DATABASE_URL" not in os.environ, reason="requires a real database"
    ),
]


@pytest.fixture
async def connection():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.connect() as conn:
        transaction = await conn.begin()
        yield conn
        await transaction.rollback()
    await engine.dispose()


async def test_create_then_list_returns_it_for_its_user(connection):
    user_id = uuid.uuid4()
    repo = ConversationRepository(connection)

    conversation_id = await repo.create(user_id)
    conversations = await repo.list_for_user(user_id)

    assert [c.id for c in conversations] == [conversation_id]
    assert conversations[0].title == ""


async def test_list_is_scoped_to_the_requesting_user(connection):
    repo = ConversationRepository(connection)
    owner = uuid.uuid4()
    other = uuid.uuid4()
    await repo.create(owner)

    assert await repo.list_for_user(other) == []


async def test_get_returns_none_for_another_users_conversation(connection):
    repo = ConversationRepository(connection)
    owner = uuid.uuid4()
    other = uuid.uuid4()
    conversation_id = await repo.create(owner)

    assert await repo.get(conversation_id, other) is None
    found = await repo.get(conversation_id, owner)
    assert found is not None
    assert found.id == conversation_id


async def test_set_title_updates_the_title(connection):
    repo = ConversationRepository(connection)
    user_id = uuid.uuid4()
    conversation_id = await repo.create(user_id)

    await repo.set_title(conversation_id, "Cartridge replacement")

    conversation = await repo.get(conversation_id, user_id)
    assert conversation is not None
    assert conversation.title == "Cartridge replacement"


async def test_touch_bumps_updated_at(connection):
    repo = ConversationRepository(connection)
    user_id = uuid.uuid4()
    conversation_id = await repo.create(user_id)
    before_conversation = await repo.get(conversation_id, user_id)
    assert before_conversation is not None

    await repo.touch(conversation_id)

    after_conversation = await repo.get(conversation_id, user_id)
    assert after_conversation is not None
    assert after_conversation.updated_at >= before_conversation.updated_at


async def test_delete_is_scoped_to_the_owner(connection):
    repo = ConversationRepository(connection)
    owner = uuid.uuid4()
    other = uuid.uuid4()
    conversation_id = await repo.create(owner)

    assert await repo.delete(conversation_id, other) is False
    assert await repo.get(conversation_id, owner) is not None

    assert await repo.delete(conversation_id, owner) is True
    assert await repo.get(conversation_id, owner) is None


async def test_insert_message_then_list_returns_it_in_order(connection):
    conversations = ConversationRepository(connection)
    messages = MessageRepository(connection)
    user_id = uuid.uuid4()
    conversation_id = await conversations.create(user_id)

    await messages.insert(
        MessageRow(
            conversation_id=conversation_id,
            role="user",
            content="How do I replace the cartridge?",
            sources=None,
            provider=None,
            model=None,
            latency_ms=None,
            status="complete",
        )
    )
    await messages.insert(
        MessageRow(
            conversation_id=conversation_id,
            role="assistant",
            content="Open the front cover [ENVY Guide, p. 12].",
            sources=[
                {"chunk_id": 1, "document": "ENVY Guide", "pages": "12", "score": 0.9}
            ],
            provider="anthropic",
            model="claude-haiku-4-5",
            latency_ms=850,
            status="complete",
        )
    )

    stored = await messages.list_for_conversation(conversation_id)

    assert [m.role for m in stored] == ["user", "assistant"]
    assert stored[1].sources == [
        {"chunk_id": 1, "document": "ENVY Guide", "pages": "12", "score": 0.9}
    ]
    assert stored[1].provider == "anthropic"
    assert stored[1].latency_ms == 850


async def test_a_failed_stream_persists_as_status_error(connection):
    conversations = ConversationRepository(connection)
    messages = MessageRepository(connection)
    conversation_id = await conversations.create(uuid.uuid4())

    await messages.insert(
        MessageRow(
            conversation_id=conversation_id,
            role="assistant",
            content="Open the front",
            sources=None,
            provider="anthropic",
            model="claude-haiku-4-5",
            latency_ms=200,
            status="error",
        )
    )

    [stored] = await messages.list_for_conversation(conversation_id)
    assert stored.status == "error"
