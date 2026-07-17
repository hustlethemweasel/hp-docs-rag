import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from app.api.sse import done_event, error_event, token_event
from app.providers.base import PROVIDER_ERRORS, ChatMessage, ChatProvider
from app.rag.history import window
from app.rag.prompting import build_system_prompt, page_label
from app.rag.retrieval import HybridRetriever
from app.rag.rewrite import rewrite_query
from app.repositories.chunks import RetrievedChunk
from app.repositories.conversations import ConversationRepository
from app.repositories.messages import MessageRepository, MessageRow

REFUSAL_MESSAGE = "I couldn't find this in the HP documents."
TITLE_MAX_LENGTH = 60


def derive_title(content: str) -> str:
    """First-message title, auto-derived and truncated per the data model."""
    collapsed = " ".join(content.split())
    if len(collapsed) <= TITLE_MAX_LENGTH:
        return collapsed
    return collapsed[: TITLE_MAX_LENGTH - 1].rstrip() + "…"


def build_sources(chunks: list[RetrievedChunk]) -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": c.chunk_id,
            "document": c.document,
            "pages": page_label(c),
            "score": c.score,
        }
        for c in chunks
    ]


@dataclass
class ChatService:
    """Rewrite -> retrieve -> generate -> persist -> stream, per user message."""

    provider: ChatProvider
    provider_name: str
    model: str
    retriever: HybridRetriever
    conversations: ConversationRepository
    messages: MessageRepository

    async def stream_message(
        self, conversation_id: uuid.UUID, content: str
    ) -> AsyncIterator[str]:
        history_rows = await self.messages.list_for_conversation(conversation_id)
        history = [ChatMessage(role=m.role, content=m.content) for m in history_rows]
        windowed_history = window(history)

        user_message_id = await self.messages.insert(
            MessageRow(
                conversation_id=conversation_id,
                role="user",
                content=content,
                sources=None,
                provider=None,
                model=None,
                latency_ms=None,
                status="complete",
            )
        )
        if not history_rows:
            await self.conversations.set_title(conversation_id, derive_title(content))

        search_query = await rewrite_query(self.provider, windowed_history, content)
        chunks = await self.retriever.retrieve(search_query)

        if not chunks:
            async for frame in self._refuse(conversation_id, user_message_id):
                yield frame
            return

        system_prompt = build_system_prompt(chunks)
        answer_messages = [
            *windowed_history,
            ChatMessage(role="user", content=content),
        ]

        collected: list[str] = []
        started = time.monotonic()
        try:
            async for token in self.provider.stream_chat(
                answer_messages, system=system_prompt
            ):
                collected.append(token)
                yield token_event(token)
        except PROVIDER_ERRORS as exc:
            async for frame in self._fail(
                conversation_id, user_message_id, "".join(collected), exc, started
            ):
                yield frame
            return

        latency_ms = self._elapsed_ms(started)
        sources = build_sources(chunks)
        assistant_message_id = await self.messages.insert(
            MessageRow(
                conversation_id=conversation_id,
                role="assistant",
                content="".join(collected),
                sources=sources,
                provider=self.provider_name,
                model=self.model,
                latency_ms=latency_ms,
                status="complete",
            )
        )
        await self.conversations.touch(conversation_id)
        yield done_event(
            sources=sources,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            latency_ms=latency_ms,
        )

    async def _refuse(
        self, conversation_id: uuid.UUID, user_message_id: uuid.UUID
    ) -> AsyncIterator[str]:
        yield token_event(REFUSAL_MESSAGE)
        assistant_message_id = await self.messages.insert(
            MessageRow(
                conversation_id=conversation_id,
                role="assistant",
                content=REFUSAL_MESSAGE,
                sources=[],
                provider=None,
                model=None,
                latency_ms=0,
                status="complete",
            )
        )
        await self.conversations.touch(conversation_id)
        yield done_event(
            sources=[],
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            latency_ms=0,
        )

    async def _fail(
        self,
        conversation_id: uuid.UUID,
        user_message_id: uuid.UUID,
        partial_content: str,
        exc: Exception,
        started: float,
    ) -> AsyncIterator[str]:
        assistant_message_id = await self.messages.insert(
            MessageRow(
                conversation_id=conversation_id,
                role="assistant",
                content=partial_content,
                sources=None,
                provider=self.provider_name,
                model=self.model,
                latency_ms=self._elapsed_ms(started),
                status="error",
            )
        )
        await self.conversations.touch(conversation_id)
        yield error_event(
            message=str(exc),
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
        )

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return int((time.monotonic() - started) * 1000)
