"""Behavior: condense history + question into a standalone retrieval query.

Real collaborator: ScriptedProvider, a genuine ChatProvider (per the
constitution) — no double stands in for the LLM call.
"""

from app.providers.base import ChatMessage
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
