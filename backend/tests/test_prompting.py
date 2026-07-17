"""Behavior: assemble the system prompt + context block the answer step sends."""

from app.rag.prompting import build_system_prompt, format_context
from app.repositories.chunks import RetrievedChunk


def chunk(
    *, document: str, page_start: int, page_end: int, content: str
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=1,
        document=document,
        content=content,
        page_start=page_start,
        page_end=page_end,
        section="Setup",
        figure_ref=None,
        score=0.9,
    )


def test_format_context_cites_a_single_page():
    chunks = [
        chunk(
            document="ENVY Guide",
            page_start=12,
            page_end=12,
            content="Open the front cover.",
        )
    ]

    context = format_context(chunks)

    assert "[ENVY Guide, p. 12]" in context
    assert "Open the front cover." in context


def test_format_context_cites_a_page_range_when_it_spans_pages():
    chunks = [
        chunk(
            document="OMEN Guide",
            page_start=40,
            page_end=41,
            content="Remove the battery.",
        )
    ]

    context = format_context(chunks)

    assert "[OMEN Guide, p. 40-41]" in context


def test_format_context_separates_multiple_chunks():
    chunks = [
        chunk(document="A", page_start=1, page_end=1, content="first"),
        chunk(document="B", page_start=2, page_end=2, content="second"),
    ]

    context = format_context(chunks)

    assert context.index("first") < context.index("second")


def test_format_context_reports_when_nothing_was_retrieved():
    assert "no relevant" in format_context([]).lower()


def test_build_system_prompt_instructs_grounding_citation_and_refusal():
    prompt = build_system_prompt(
        [chunk(document="ENVY Guide", page_start=5, page_end=5, content="text")]
    )

    assert "ENVY Guide, p. 5" in prompt
    assert (
        "isn't in the documents" in prompt.lower()
        or "not in the documents" in prompt.lower()
    )
