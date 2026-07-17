"""Behavior: load the golden Q&A benchmark set from JSONL.

Pure parsing logic; no doubles needed.
"""

from pathlib import Path

from eval.golden import GoldenCase, load_golden

from app.providers.base import ChatMessage


def write(tmp_path: Path, *lines: str) -> Path:
    path = tmp_path / "golden.jsonl"
    path.write_text("\n".join(lines) + "\n")
    return path


def test_loads_a_minimal_factual_case_with_defaults(tmp_path):
    path = write(
        tmp_path,
        '{"id": "f1", "category": "factual", "question": "How much ink is left?", '
        '"document": "hp-envy-6000-user-guide.pdf", "pages": [62]}',
    )

    [case] = load_golden(path)

    assert case == GoldenCase(
        id="f1",
        category="factual",
        question="How much ink is left?",
        history=[],
        document="hp-envy-6000-user-guide.pdf",
        pages={62},
        expect_refusal=False,
    )


def test_loads_a_case_with_prior_turns(tmp_path):
    path = write(
        tmp_path,
        '{"id": "mt1", "category": "multiturn", '
        '"history": [{"role": "user", "content": "How do I replace the cartridges?"}, '
        '{"role": "assistant", "content": "Open the front door and swap them."}], '
        '"question": "What about after I put the new one in?", '
        '"document": "hp-envy-6000-user-guide.pdf", "pages": [65, 66]}',
    )

    [case] = load_golden(path)

    assert case.history == [
        ChatMessage(role="user", content="How do I replace the cartridges?"),
        ChatMessage(role="assistant", content="Open the front door and swap them."),
    ]
    assert case.pages == {65, 66}


def test_loads_a_negative_case_expecting_refusal(tmp_path):
    path = write(
        tmp_path,
        '{"id": "n1", "category": "negative", '
        '"question": "What tire pressure does this laptop need?", '
        '"expect_refusal": true}',
    )

    [case] = load_golden(path)

    assert case.document is None
    assert case.pages == set()
    assert case.expect_refusal is True


def test_loads_multiple_lines_in_order(tmp_path):
    path = write(
        tmp_path,
        '{"id": "a", "category": "factual", "question": "q1", '
        '"document": "d.pdf", "pages": [1]}',
        '{"id": "b", "category": "factual", "question": "q2", '
        '"document": "d.pdf", "pages": [2]}',
    )

    cases = load_golden(path)

    assert [c.id for c in cases] == ["a", "b"]
