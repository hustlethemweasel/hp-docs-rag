"""Behavior: condense history + question into a standalone retrieval query.

Real collaborator: ScriptedProvider, a genuine ChatProvider (per the
constitution) — no double stands in for the LLM call.
"""

from unittest.mock import create_autospec

from app.providers.base import ChatMessage, ChatProvider
from app.providers.scripted import ScriptedProvider
from app.rag.rewrite import rewrite_query


async def test_skips_rewriting_on_the_first_turn():
    provider = ScriptedProvider(tokens=["should", " not", " be used"])

    result = await rewrite_query(provider, history=[], question="How do I clean it?")

    assert result == "How do I clean it?"


async def test_condenses_history_and_question_into_a_standalone_query():
    provider = ScriptedProvider(tokens=["How ", "do I clean ", "the printhead?"])
    history = [
        ChatMessage(role="user", content="My printer won't print."),
        ChatMessage(role="assistant", content="Let's check the printhead."),
    ]

    result = await rewrite_query(
        provider, history=history, question="How do I clean it?"
    )

    assert result == "How do I clean the printhead?"


async def test_instructs_the_provider_to_rewrite_in_english():
    # The corpus is English-only; rewriting to English keeps the sparse FTS
    # leg usable for non-English conversations (SPEC's multilingual section).
    async def scripted_stream(messages, **kwargs):
        yield "rewritten"

    provider = create_autospec(ChatProvider, instance=True)
    provider.stream_chat.side_effect = scripted_stream
    history = [ChatMessage(role="user", content="My printer won't print.")]

    await rewrite_query(provider, history=history, question="How do I clean it?")

    _, kwargs = provider.stream_chat.call_args
    assert "in english" in kwargs["system"].lower()


async def test_forwards_temperature_to_the_provider_when_given():
    async def scripted_stream(messages, **kwargs):
        yield "rewritten"

    provider = create_autospec(ChatProvider, instance=True)
    provider.stream_chat.side_effect = scripted_stream
    history = [ChatMessage(role="user", content="My printer won't print.")]

    await rewrite_query(
        provider, history=history, question="How do I clean it?", temperature=0
    )

    _, kwargs = provider.stream_chat.call_args
    assert kwargs["temperature"] == 0
