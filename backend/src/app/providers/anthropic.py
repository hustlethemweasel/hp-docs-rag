from collections.abc import AsyncIterator

import anthropic

from app.providers.base import ChatMessage

MAX_RESPONSE_TOKENS = 1024


class AnthropicProvider:
    """Cloud chat generation via the Anthropic Messages streaming API."""

    def __init__(self, client: anthropic.AsyncAnthropic, model: str) -> None:
        self._client = client
        self._model = model

    async def stream_chat(
        self, messages: list[ChatMessage], **kwargs: object
    ) -> AsyncIterator[str]:
        system = kwargs.get("system")
        temperature = kwargs.get("temperature")
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=MAX_RESPONSE_TOKENS,
            system=system if isinstance(system, str) else anthropic.omit,
            temperature=(
                temperature if isinstance(temperature, int | float) else anthropic.omit
            ),
            messages=[{"role": m.role, "content": m.content} for m in messages],
        ) as stream:
            async for text in stream.text_stream:
                yield text
