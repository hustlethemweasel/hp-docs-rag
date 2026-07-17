import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from app.providers.base import ChatMessage


@dataclass
class ScriptedProvider:
    """Streams a fixed token sequence with configurable per-token latency.

    A genuine `ChatProvider` — real async streaming, no network — so the
    fast suite and the load-test scenario that isolates API/DB/retrieval
    scalability can exercise the real streaming path without a live LLM.
    """

    tokens: list[str] = field(default_factory=list)
    latency: float = 0.0

    async def stream_chat(
        self, messages: list[ChatMessage], **kwargs: object
    ) -> AsyncIterator[str]:
        for token in self.tokens:
            if self.latency:
                await asyncio.sleep(self.latency)
            yield token
