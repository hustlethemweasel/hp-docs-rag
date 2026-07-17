import json
from collections.abc import AsyncIterator

import httpx

from app.providers.base import ChatMessage


class OllamaProvider:
    """Offline chat generation via Ollama's streaming NDJSON `/api/chat`.

    `think: false` matches the captioner: qwen3.5:4b is a reasoning model
    that otherwise spends the call on hidden thinking tokens.
    """

    def __init__(self, client: httpx.AsyncClient, model: str) -> None:
        self._client = client
        self._model = model

    async def stream_chat(
        self, messages: list[ChatMessage], **kwargs: object
    ) -> AsyncIterator[str]:
        payload_messages = []
        system = kwargs.get("system")
        if system:
            payload_messages.append({"role": "system", "content": system})
        payload_messages += [{"role": m.role, "content": m.content} for m in messages]

        async with self._client.stream(
            "POST",
            "/api/chat",
            json={
                "model": self._model,
                "messages": payload_messages,
                "stream": True,
                "think": False,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                content = json.loads(line)["message"]["content"]
                if content:
                    yield content
