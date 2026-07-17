"""Behavior: LLM-as-judge scoring for faithfulness and answer relevancy.

Real collaborator: ScriptedProvider, a genuine ChatProvider, streams the
judge's canned response — no double stands in for the LLM call. Pure prompt
building and response parsing are tested directly.
"""

from unittest.mock import create_autospec

import pytest
from eval.judge import JudgeScore, build_judge_prompt, judge, parse_judge_response

from app.providers.base import ChatProvider
from app.providers.scripted import ScriptedProvider


def test_build_judge_prompt_includes_question_answer_and_context():
    prompt = build_judge_prompt(
        question="How do I clean the printhead?",
        answer="Open the front cover [ENVY Guide, p. 12].",
        context="[ENVY Guide, p. 12]\nOpen the front access door.",
    )

    assert "How do I clean the printhead?" in prompt
    assert "Open the front cover" in prompt
    assert "Open the front access door." in prompt


def test_parse_judge_response_parses_plain_json():
    raw = '{"faithfulness": 0.9, "relevancy": 1.0, "reasoning": "well grounded"}'

    score = parse_judge_response(raw)

    assert score == JudgeScore(
        faithfulness=0.9, relevancy=1.0, reasoning="well grounded"
    )


def test_parse_judge_response_strips_markdown_fences():
    raw = (
        '```json\n{"faithfulness": 0.5, "relevancy": 0.75, "reasoning": "partial"}\n```'
    )

    score = parse_judge_response(raw)

    assert score.faithfulness == 0.5
    assert score.relevancy == 0.75


def test_parse_judge_response_raises_on_no_json():
    with pytest.raises(ValueError, match="no JSON"):
        parse_judge_response("I refuse to answer in JSON.")


async def test_judge_collects_the_streamed_response_and_parses_it():
    provider = ScriptedProvider(
        tokens=['{"faithfulness": 0.8, ', '"relevancy": 0.6, "reasoning": "ok"}']
    )

    score = await judge(
        provider,
        question="How do I clean it?",
        answer="Use a soft cloth.",
        context="Use a soft, lint-free cloth.",
    )

    assert score == JudgeScore(faithfulness=0.8, relevancy=0.6, reasoning="ok")


async def test_judge_pins_temperature_to_zero_by_default():
    async def scripted_stream(messages, **kwargs):
        yield '{"faithfulness": 1.0, "relevancy": 1.0, "reasoning": "ok"}'

    provider = create_autospec(ChatProvider, instance=True)
    provider.stream_chat.side_effect = scripted_stream

    await judge(provider, question="q", answer="a", context="c")

    _, kwargs = provider.stream_chat.call_args
    assert kwargs["temperature"] == 0.0


async def test_judge_allows_overriding_temperature():
    async def scripted_stream(messages, **kwargs):
        yield '{"faithfulness": 1.0, "relevancy": 1.0, "reasoning": "ok"}'

    provider = create_autospec(ChatProvider, instance=True)
    provider.stream_chat.side_effect = scripted_stream

    await judge(provider, question="q", answer="a", context="c", temperature=0.4)

    _, kwargs = provider.stream_chat.call_args
    assert kwargs["temperature"] == 0.4
