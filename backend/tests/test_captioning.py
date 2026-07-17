"""Behavior: caption figures via the vision-capable local model (SPEC §7.4).

Real collaborator: a real httpx.Client against httpx.MockTransport — a
genuine request/response round trip through httpx's own real HTTP stack,
just without a live socket. Not a double of our own code.
"""

import base64
import json
from typing import Any

import httpx
import pytest

from app.ingest.captioning import OllamaCaptioner


def test_sends_the_image_and_captioning_prompt_to_ollama():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": "A close-up of a cartridge.",
                }
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://ollama:11434"
    )
    captioner = OllamaCaptioner(client=client, model="qwen3.5:4b")

    caption = captioner.caption(b"fake-png-bytes")

    assert captured["url"] == "http://ollama:11434/api/chat"
    assert captured["body"]["model"] == "qwen3.5:4b"
    assert captured["body"]["stream"] is False
    assert captured["body"]["think"] is False
    [message] = captured["body"]["messages"]
    assert message["images"] == [base64.b64encode(b"fake-png-bytes").decode()]
    assert caption == "A close-up of a cartridge."


def test_raises_on_a_failed_request():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="model not loaded")

    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://ollama:11434"
    )
    captioner = OllamaCaptioner(client=client, model="qwen3.5:4b")

    with pytest.raises(httpx.HTTPStatusError):
        captioner.caption(b"fake-png-bytes")
