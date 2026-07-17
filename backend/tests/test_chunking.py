"""Behavior: structure-aware recursive chunking with overlap.

Real collaborators: the chunker operates on plain ParsedPage fixtures (the
contract the future pymupdf4llm parser will produce) and a real, explicit
word-count token counter — not the harrier tokenizer, which is wired in via the
real embedder elsewhere — a genuine, deterministic strategy, not a double.
"""

from app.ingest.chunking import Chunk, ParsedPage, chunk_pages


def word_count(text: str) -> int:
    return len(text.split())


def test_single_short_page_yields_one_chunk():
    pages = [
        ParsedPage(number=1, markdown="Turn the printer on and wait for it to warm up.")
    ]

    chunks = chunk_pages(
        pages, chunk_tokens=450, chunk_overlap=80, count_tokens=word_count
    )

    assert chunks == [
        Chunk(
            content="Turn the printer on and wait for it to warm up.",
            section=None,
            page_start=1,
            page_end=1,
            chunk_index=0,
            token_count=11,
        )
    ]


def test_heading_tags_the_chunk_with_its_section():
    pages = [
        ParsedPage(
            number=1,
            markdown=(
                "# Cartridge Replacement\n\n"
                "Open the front cover and slide out the tray."
            ),
        )
    ]

    chunks = chunk_pages(
        pages, chunk_tokens=450, chunk_overlap=80, count_tokens=word_count
    )

    assert len(chunks) == 1
    assert chunks[0].section == "Cartridge Replacement"
    assert chunks[0].content == "Open the front cover and slide out the tray."


def test_chunk_never_spans_two_headings_even_if_both_fit():
    pages = [
        ParsedPage(
            number=1,
            markdown=(
                "# Setup\n\nUnpack the printer.\n\n"
                "# Cleanup\n\nRecycle the packaging."
            ),
        )
    ]

    chunks = chunk_pages(
        pages, chunk_tokens=450, chunk_overlap=80, count_tokens=word_count
    )

    assert [c.section for c in chunks] == ["Setup", "Cleanup"]
    assert [c.content for c in chunks] == [
        "Unpack the printer.",
        "Recycle the packaging.",
    ]
    assert [c.chunk_index for c in chunks] == [0, 1]


def test_multi_page_section_spans_page_start_to_page_end():
    pages = [
        ParsedPage(
            number=3, markdown="# Battery Removal\n\nRemove the four bottom screws."
        ),
        ParsedPage(number=4, markdown="Lift the base panel away from the chassis."),
    ]

    chunks = chunk_pages(
        pages, chunk_tokens=450, chunk_overlap=80, count_tokens=word_count
    )

    assert len(chunks) == 1
    assert chunks[0].page_start == 3
    assert chunks[0].page_end == 4


def test_long_section_splits_into_multiple_chunks_with_overlap():
    # Ten paragraphs of 60 words each -> 600 tokens total; well above the
    # 200-token target, so the section must split, and adjacent chunks must
    # share trailing/leading content worth the configured overlap.
    paragraphs = [f"word{p}-{i} " * 60 for p in range(10) for i in [0]]
    markdown = "# Troubleshooting\n\n" + "\n\n".join(paragraphs)
    pages = [ParsedPage(number=1, markdown=markdown)]

    chunks = chunk_pages(
        pages, chunk_tokens=200, chunk_overlap=60, count_tokens=word_count
    )

    assert len(chunks) > 1
    assert all(c.section == "Troubleshooting" for c in chunks)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert all(c.token_count <= 200 for c in chunks)

    for earlier, later in zip(chunks, chunks[1:], strict=False):
        earlier_tail = earlier.content.split()[-10:]
        later_head = later.content.split()[:10]
        assert set(earlier_tail) & set(later_head), "adjacent chunks must overlap"


def test_blank_lines_between_paragraphs_do_not_produce_empty_chunks():
    pages = [ParsedPage(number=1, markdown="First paragraph.\n\n\n\nSecond paragraph.")]

    chunks = chunk_pages(
        pages, chunk_tokens=450, chunk_overlap=80, count_tokens=word_count
    )

    assert [c.content for c in chunks] == ["First paragraph. Second paragraph."]


def test_blank_page_contributes_no_chunk():
    pages = [
        ParsedPage(number=1, markdown="   \n\n  "),
        ParsedPage(number=2, markdown="Only real content."),
    ]

    chunks = chunk_pages(
        pages, chunk_tokens=450, chunk_overlap=80, count_tokens=word_count
    )

    assert [c.content for c in chunks] == ["Only real content."]
    assert chunks[0].page_start == 2


def test_oversized_paragraph_splits_on_sentence_boundaries():
    sentence = "Replace the cartridge only when the light blinks amber."
    markdown = "# Maintenance\n\n" + " ".join([sentence] * 20)
    pages = [ParsedPage(number=1, markdown=markdown)]

    chunks = chunk_pages(
        pages, chunk_tokens=50, chunk_overlap=10, count_tokens=word_count
    )

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.content.strip().endswith(".")


def test_oversized_block_without_sentence_boundaries_falls_back_to_word_window():
    # A markdown table has no sentence-ending punctuation, so sentence
    # splitting can't break it up; a hard token-window fallback must still
    # keep every resulting chunk within chunk_tokens.
    row = " | ".join(f"cell{i}" for i in range(200))
    markdown = "# Specifications\n\n" + row
    pages = [ParsedPage(number=1, markdown=markdown)]

    chunks = chunk_pages(
        pages, chunk_tokens=50, chunk_overlap=10, count_tokens=word_count
    )

    assert len(chunks) > 1
    assert all(c.token_count <= 50 for c in chunks)
