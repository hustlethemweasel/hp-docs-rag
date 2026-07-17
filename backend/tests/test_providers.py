"""Behavior: ChatProvider implementations stream response text.

Real collaborators: real httpx / anthropic-SDK clients against
httpx.MockTransport — a genuine request/response round trip through each
library's real HTTP stack, just without a live socket. ScriptedProvider is
itself a genuine ChatProvider (per the constitution, no fake/mock naming);
its own tests exercise real async streaming and real (monkeypatched)
asyncio.sleep timing.
"""

import asyncio
import json
from typing import Any, Literal

import anthropic
import httpx
import pytest

from app.config import Settings
from app.providers.anthropic import AnthropicProvider
from app.providers.base import ChatMessage
from app.providers.factory import build_provider
from app.providers.ollama import OllamaProvider
from app.providers.scripted import ScriptedProvider


async def collect(provider, messages, **kwargs) -> list[str]:
    return [token async for token in provider.stream_chat(messages, **kwargs)]


# --- ScriptedProvider -------------------------------------------------------


async def test_scripted_provider_streams_its_tokens_in_order():
    provider = ScriptedProvider(tokens=["Hello", ", ", "world"])

    tokens = await collect(provider, [ChatMessage(role="user", content="hi")])

    assert tokens == ["Hello", ", ", "world"]


async def test_scripted_provider_sleeps_between_tokens_for_configured_latency(
    monkeypatch,
):
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    provider = ScriptedProvider(tokens=["a", "b"], latency=0.05)

    await collect(provider, [])

    assert sleeps == [0.05, 0.05]


async def test_scripted_provider_default_latency_never_sleeps(monkeypatch):
    monkeypatch.setattr(
        asyncio, "sleep", lambda *_: pytest.fail("should not sleep by default")
    )
    provider = ScriptedProvider(tokens=["a"])

    await collect(provider, [])


# --- AnthropicProvider -------------------------------------------------------


def anthropic_sse(deltas: list[str]) -> str:
    events: list[tuple[str, dict[str, Any]]] = [
        (
            "message_start",
            {
                "type": "message_start",
                "message": {
                    "id": "msg_test",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-haiku-4-5",
                    "content": [],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": 10, "output_tokens": 0},
                },
            },
        ),
        (
            "content_block_start",
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            },
        ),
    ]
    for delta in deltas:
        events.append(
            (
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": delta},
                },
            )
        )
    events.append(("content_block_stop", {"type": "content_block_stop", "index": 0}))
    events.append(
        (
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                "usage": {"output_tokens": len(deltas)},
            },
        )
    )
    events.append(("message_stop", {"type": "message_stop"}))
    return "".join(
        f"event: {name}\ndata: {json.dumps(payload)}\n\n" for name, payload in events
    )


def anthropic_client_with(handler) -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(
        api_key="test-key",
        http_client=anthropic.DefaultAsyncHttpxClient(
            transport=httpx.MockTransport(handler)
        ),
        max_retries=0,
    )


async def test_anthropic_provider_streams_text_deltas():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=anthropic_sse(["Hello", " world"]),
        )

    provider = AnthropicProvider(
        client=anthropic_client_with(handler), model="claude-haiku-4-5"
    )
    messages = [ChatMessage(role="user", content="hi")]

    tokens = await collect(provider, messages, system="Answer from the docs only.")

    assert tokens == ["Hello", " world"]
    assert captured["body"]["model"] == "claude-haiku-4-5"
    assert captured["body"]["system"] == "Answer from the docs only."
    assert captured["body"]["messages"] == [{"role": "user", "content": "hi"}]


async def test_anthropic_provider_omits_system_when_not_given():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=anthropic_sse(["hi"]),
        )

    provider = AnthropicProvider(
        client=anthropic_client_with(handler), model="claude-haiku-4-5"
    )

    await collect(provider, [ChatMessage(role="user", content="hi")])

    assert "system" not in captured["body"]


# --- OllamaProvider -----------------------------------------------------------


def ollama_ndjson(deltas: list[str]) -> str:
    lines = [
        json.dumps({"message": {"role": "assistant", "content": delta}, "done": False})
        for delta in deltas
    ]
    lines.append(
        json.dumps({"message": {"role": "assistant", "content": ""}, "done": True})
    )
    return "\n".join(lines) + "\n"


async def test_ollama_provider_streams_message_content():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, text=ollama_ndjson(["Hello", " world"]))

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama:11434"
    )
    provider = OllamaProvider(client=client, model="qwen3.5:4b")

    tokens = await collect(
        provider,
        [ChatMessage(role="user", content="hi")],
        system="Answer from the docs only.",
    )

    assert tokens == ["Hello", " world"]
    assert captured["body"]["model"] == "qwen3.5:4b"
    assert captured["body"]["stream"] is True
    assert captured["body"]["think"] is False
    assert captured["body"]["messages"][0] == {
        "role": "system",
        "content": "Answer from the docs only.",
    }
    assert captured["body"]["messages"][1] == {"role": "user", "content": "hi"}


async def test_ollama_provider_skips_blank_lines_in_the_ndjson_stream():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="\n" + ollama_ndjson(["Hello"]))

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama:11434"
    )
    provider = OllamaProvider(client=client, model="qwen3.5:4b")

    tokens = await collect(provider, [ChatMessage(role="user", content="hi")])

    assert tokens == ["Hello"]


async def test_ollama_provider_raises_on_a_failed_request():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="model not loaded")

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama:11434"
    )
    provider = OllamaProvider(client=client, model="qwen3.5:4b")

    with pytest.raises(httpx.HTTPStatusError):
        await collect(provider, [ChatMessage(role="user", content="hi")])


# --- factory -------------------------------------------------------------------


def settings_for(
    provider: Literal["anthropic", "openai", "ollama"], **overrides
) -> Settings:
    return Settings(
        llm_provider=provider, database_url="sqlite+aiosqlite://", **overrides
    )


def test_factory_builds_the_anthropic_provider():
    settings = settings_for(
        "anthropic", llm_model="claude-haiku-4-5", anthropic_api_key="test-key"
    )

    provider = build_provider(settings)

    assert isinstance(provider, AnthropicProvider)


def test_factory_builds_the_ollama_provider():
    settings = settings_for("ollama", llm_model="qwen3.5:4b")

    provider = build_provider(settings)

    assert isinstance(provider, OllamaProvider)


def test_factory_fails_fast_on_anthropic_without_an_api_key():
    settings = settings_for("anthropic", anthropic_api_key=None)

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        build_provider(settings)


def test_factory_fails_fast_on_an_unimplemented_provider():
    settings = settings_for("openai", openai_api_key="test-key")

    with pytest.raises(NotImplementedError, match="openai"):
        build_provider(settings)
