"""Behavior: caption figures via the configured provider (SPEC §7.4).

Real collaborators: real httpx / anthropic-SDK clients against
httpx.MockTransport — a genuine request/response round trip through each
library's real HTTP stack, just without a live socket. Not doubles of our
own code.
"""

import base64
import json
from typing import Any, Literal

import anthropic
import httpx
import pytest

from app.config import Settings
from app.ingest.captioning import (
    CAPTION_PROMPT,
    AnthropicCaptioner,
    OllamaCaptioner,
    build_captioner,
)


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


def anthropic_client_with(handler) -> anthropic.Anthropic:
    return anthropic.Anthropic(
        api_key="test-key",
        http_client=anthropic.DefaultHttpxClient(
            transport=httpx.MockTransport(handler)
        ),
        max_retries=0,
    )


def test_sends_the_image_and_captioning_prompt_to_anthropic():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["api_key"] = request.headers.get("x-api-key")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "claude-haiku-4-5",
                "content": [{"type": "text", "text": "A close-up of a cartridge."}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 10},
            },
        )

    captioner = AnthropicCaptioner(
        client=anthropic_client_with(handler), model="claude-haiku-4-5"
    )

    caption = captioner.caption(b"fake-png-bytes")

    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["api_key"] == "test-key"
    assert captured["body"]["model"] == "claude-haiku-4-5"
    [message] = captured["body"]["messages"]
    image_block, text_block = message["content"]
    assert image_block["source"]["type"] == "base64"
    assert image_block["source"]["media_type"] == "image/png"
    assert image_block["source"]["data"] == base64.b64encode(b"fake-png-bytes").decode()
    assert text_block["text"] == CAPTION_PROMPT
    assert caption == "A close-up of a cartridge."


def test_anthropic_captioner_raises_on_a_failed_request():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            json={"type": "error", "error": {"type": "api_error", "message": "boom"}},
        )

    captioner = AnthropicCaptioner(
        client=anthropic_client_with(handler), model="claude-haiku-4-5"
    )

    with pytest.raises(anthropic.APIStatusError):
        captioner.caption(b"fake-png-bytes")


def settings_for(
    provider: Literal["anthropic", "openai", "ollama"], **overrides
) -> Settings:
    return Settings(
        llm_provider=provider, database_url="sqlite+aiosqlite://", **overrides
    )


def test_factory_builds_the_anthropic_captioner():
    settings = settings_for(
        "anthropic", llm_model="claude-haiku-4-5", anthropic_api_key="test-key"
    )

    captioner = build_captioner(settings)

    assert isinstance(captioner, AnthropicCaptioner)


def test_factory_builds_the_ollama_captioner():
    settings = settings_for("ollama", llm_model="qwen3.5:4b")

    captioner = build_captioner(settings)

    assert isinstance(captioner, OllamaCaptioner)


def test_factory_fails_fast_on_anthropic_without_an_api_key():
    settings = settings_for("anthropic", anthropic_api_key=None)

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        build_captioner(settings)


def test_factory_fails_fast_on_an_unimplemented_provider():
    settings = settings_for("openai", openai_api_key="test-key")

    with pytest.raises(NotImplementedError, match="openai"):
        build_captioner(settings)
