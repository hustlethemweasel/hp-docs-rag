"""Behavior: orchestrate rewrite -> retrieve -> generate -> persist -> stream.

Real collaborators: ScriptedProvider (a genuine ChatProvider) drives the real
rewrite/generation/prompting code paths. HybridRetriever and the repositories
are the genuine external boundaries (DB) — doubled with create_autospec.
"""

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import create_autospec

import httpx

from app.providers.base import ChatProvider
from app.providers.scripted import ScriptedProvider
from app.rag.chat_service import REFUSAL_MESSAGE, ChatService
from app.rag.retrieval import HybridRetriever
from app.repositories.chunks import RetrievedChunk
from app.repositories.conversations import ConversationRepository
from app.repositories.messages import MessageRepository, StoredMessage


def parse(frame: str) -> tuple[str, dict]:
    event_line, data_line = frame.strip("\n").split("\n", 1)
    return event_line.removeprefix("event: "), json.loads(
        data_line.removeprefix("data: ")
    )


def chunk(chunk_id: int = 1, content: str = "Open the front cover.") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document="ENVY Guide",
        content=content,
        page_start=12,
        page_end=12,
        section="Setup",
        figure_ref=None,
        score=0.9,
    )


def make_service(*, provider: ChatProvider, history: list[StoredMessage] | None = None):
    retriever = create_autospec(HybridRetriever, instance=True)
    conversations = create_autospec(ConversationRepository, instance=True)
    messages = create_autospec(MessageRepository, instance=True)
    messages.list_for_conversation.return_value = history or []
    messages.insert.side_effect = [uuid.uuid4() for _ in range(10)]
    service = ChatService(
        provider=provider,
        provider_name="anthropic",
        model="claude-haiku-4-5",
        retriever=retriever,
        conversations=conversations,
        messages=messages,
    )
    return service, retriever, conversations, messages


async def collect(service, conversation_id, content) -> list[tuple[str, dict]]:
    return [
        parse(frame) async for frame in service.stream_message(conversation_id, content)
    ]


async def test_first_message_skips_rewriting_and_streams_the_answer():
    provider = ScriptedProvider(tokens=["Open ", "the front ", "cover."])
    service, retriever, conversations, messages = make_service(provider=provider)
    retriever.retrieve.return_value = [chunk()]
    conversation_id = uuid.uuid4()

    events = await collect(service, conversation_id, "How do I open it?")

    retriever.retrieve.assert_called_once_with("How do I open it?")
    assert [e for e, _ in events[:-1]] == ["token"] * 3
    assert "".join(p["text"] for _, p in events[:-1]) == "Open the front cover."
    event, payload = events[-1]
    assert event == "done"
    assert payload["sources"] == [
        {"chunk_id": 1, "document": "ENVY Guide", "pages": "12", "score": 0.9}
    ]
    assert payload["latency_ms"] >= 0

    conversations.set_title.assert_called_once()
    conversations.touch.assert_called_once_with(conversation_id)
    [user_call, assistant_call] = messages.insert.call_args_list
    assert user_call.args[0].role == "user"
    assert user_call.args[0].content == "How do I open it?"
    assert assistant_call.args[0].role == "assistant"
    assert assistant_call.args[0].content == "Open the front cover."
    assert assistant_call.args[0].status == "complete"
    assert assistant_call.args[0].provider == "anthropic"
    assert assistant_call.args[0].model == "claude-haiku-4-5"


async def test_later_message_rewrites_the_query_before_retrieving():
    provider = ScriptedProvider(tokens=["cleaning ", "instructions"])
    history = [
        StoredMessage(
            id=uuid.uuid4(),
            role="user",
            content="My printer won't print.",
            sources=None,
            provider=None,
            model=None,
            latency_ms=None,
            status="complete",
            created_at=datetime.now(UTC),
        ),
        StoredMessage(
            id=uuid.uuid4(),
            role="assistant",
            content="Let's check the printhead.",
            sources=[],
            provider="anthropic",
            model="claude-haiku-4-5",
            latency_ms=500,
            status="complete",
            created_at=datetime.now(UTC),
        ),
    ]
    service, retriever, conversations, messages = make_service(
        provider=provider, history=history
    )
    retriever.retrieve.return_value = [chunk()]
    conversation_id = uuid.uuid4()

    await collect(service, conversation_id, "How do I clean it?")

    retriever.retrieve.assert_called_once_with("cleaning instructions")
    conversations.set_title.assert_not_called()


async def test_no_retrieved_chunks_returns_a_refusal_without_calling_the_provider():
    provider = ScriptedProvider(tokens=["should not be streamed"])
    service, retriever, conversations, messages = make_service(provider=provider)
    retriever.retrieve.return_value = []
    conversation_id = uuid.uuid4()

    events = await collect(service, conversation_id, "What's the capital of France?")

    texts = [p["text"] for e, p in events if e == "token"]
    assert "".join(texts) == REFUSAL_MESSAGE
    event, payload = events[-1]
    assert event == "done"
    assert payload["sources"] == []
    [_, assistant_call] = messages.insert.call_args_list
    assert assistant_call.args[0].content == REFUSAL_MESSAGE
    assert assistant_call.args[0].status == "complete"
    conversations.touch.assert_called_once_with(conversation_id)


async def test_provider_failure_mid_stream_persists_a_partial_message_and_emits_error():
    async def flaky_stream(messages, **kwargs):
        yield "Open "
        yield "the "
        raise httpx.ConnectError("provider unreachable")

    provider = create_autospec(ChatProvider, instance=True)
    provider.stream_chat.side_effect = flaky_stream
    service, retriever, conversations, messages = make_service(provider=provider)
    retriever.retrieve.return_value = [chunk()]
    conversation_id = uuid.uuid4()

    events = await collect(service, conversation_id, "How do I open it?")

    assert [e for e, _ in events] == ["token", "token", "error"]
    event, payload = events[-1]
    assert payload["message"] == "provider unreachable"
    [_, assistant_call] = messages.insert.call_args_list
    assert assistant_call.args[0].content == "Open the "
    assert assistant_call.args[0].status == "error"
    assert assistant_call.args[0].sources is None
    conversations.touch.assert_called_once_with(conversation_id)
