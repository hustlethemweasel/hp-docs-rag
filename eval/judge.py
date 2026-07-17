"""LLM-as-judge scoring: faithfulness and answer relevancy (RAGAS-style).

One provider call per question scores both metrics together, to keep judge
cost to a single LLM round trip per case.
"""

import json
import re
from dataclasses import dataclass

from app.providers.base import ChatMessage, ChatProvider

JUDGE_SYSTEM_PROMPT = (
    "You are an impartial evaluator of a RAG chatbot's answer. Given a "
    "question, the retrieved context, and the chatbot's answer, score two "
    "things on a 0.0-1.0 scale:\n"
    "- faithfulness: is every claim in the answer supported by the context "
    "(no hallucination)?\n"
    "- relevancy: does the answer actually address the question?\n"
    'Reply with ONLY a JSON object: {"faithfulness": <0-1>, "relevancy": '
    '<0-1>, "reasoning": "<one sentence>"}.'
)

JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(frozen=True)
class JudgeScore:
    faithfulness: float
    relevancy: float
    reasoning: str


def build_judge_prompt(question: str, answer: str, context: str) -> str:
    return (
        f"Question: {question}\n\n"
        f"Retrieved context:\n{context}\n\n"
        f"Chatbot answer:\n{answer}"
    )


def parse_judge_response(raw: str) -> JudgeScore:
    match = JSON_OBJECT.search(raw)
    if not match:
        raise ValueError(f"judge response contained no JSON object: {raw!r}")
    data = json.loads(match.group(0))
    return JudgeScore(
        faithfulness=float(data["faithfulness"]),
        relevancy=float(data["relevancy"]),
        reasoning=str(data.get("reasoning", "")),
    )


async def judge(
    provider: ChatProvider,
    *,
    question: str,
    answer: str,
    context: str,
    temperature: float | None = 0.0,
) -> JudgeScore:
    messages = [
        ChatMessage(role="user", content=build_judge_prompt(question, answer, context))
    ]
    kwargs: dict[str, object] = {"system": JUDGE_SYSTEM_PROMPT}
    if temperature is not None:
        kwargs["temperature"] = temperature
    tokens = [token async for token in provider.stream_chat(messages, **kwargs)]
    return parse_judge_response("".join(tokens))
