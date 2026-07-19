"""Golden Q&A benchmark set: factual, procedure, figure-dependent, multi-turn,
and negative (unanswerable) cases, per the response-quality benchmark in
SPEC.md.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from app.providers.base import ChatMessage

GOLDEN_PATH = Path(__file__).parent / "golden.jsonl"


@dataclass(frozen=True)
class GoldenCase:
    id: str
    category: str
    question: str
    history: list[ChatMessage]
    document: str | None
    pages: set[int]
    expect_refusal: bool
    language: str = "en"


def retrieval_cases(cases: list[GoldenCase]) -> list[GoldenCase]:
    """The subset the retrieval-only eval can measure: answerable cases
    (negatives have no expected pages to rank against) that are single-turn
    (multi-turn questions are incomplete without the query rewriting that
    eval doesn't run) and English (production rewrites every query to
    English before retrieval, so raw non-English retrieval isn't a
    production path — non-English cases are measured end-to-end by the
    quality benchmark instead).
    """
    return [
        case
        for case in cases
        if not case.expect_refusal
        and not case.history
        and case.pages
        and case.language == "en"
    ]


def load_golden(path: Path = GOLDEN_PATH) -> list[GoldenCase]:
    cases = []
    for line in path.read_text().splitlines():
        record = json.loads(line)
        cases.append(
            GoldenCase(
                id=record["id"],
                category=record["category"],
                question=record["question"],
                history=[
                    ChatMessage(role=turn["role"], content=turn["content"])
                    for turn in record.get("history", [])
                ],
                document=record.get("document"),
                pages=set(record.get("pages", [])),
                expect_refusal=record.get("expect_refusal", False),
                language=record.get("language", "en"),
            )
        )
    return cases
