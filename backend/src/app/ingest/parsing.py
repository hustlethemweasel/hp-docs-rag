import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf4llm
import structlog

from app.ingest.chunking import ParsedPage

logger = structlog.get_logger(__name__)

_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_LEADING_PAGE_NUM_RE = re.compile(r"^\s*(\d+)\b")
_TRAILING_PAGE_NUM_RE = re.compile(r"\b(\d+)\s*$")


@dataclass(frozen=True)
class ParsedDocument:
    pages: list[ParsedPage]
    page_offset: int
    """Physical page index minus the document's own printed page number —
    exposed so figure page numbers (extracted separately, via raw PyMuPDF,
    not pymupdf4llm) can be corrected the same way as text pages."""


def parse_pdf(path: Path, *, boilerplate_threshold: float = 0.5) -> ParsedDocument:
    """Parse a PDF into per-page markdown with light cleaning.

    Heading/structure detection and hyphenation repair are handled by
    pymupdf4llm's layout analysis; this module drops repeated headers/footers
    (detected by line repetition across pages) and collapses whitespace.
    """
    raw_pages = pymupdf4llm.to_markdown(str(path), page_chunks=True)
    assert isinstance(raw_pages, list)  # page_chunks=True always returns a list
    boilerplate = _detect_boilerplate_lines(raw_pages, boilerplate_threshold)
    offset = _detect_page_offset(raw_pages)
    logger.info(
        "pdf_parsed",
        path=str(path),
        pages=len(raw_pages),
        boilerplate_lines=len(boilerplate),
        page_offset=offset,
    )
    pages = [
        ParsedPage(
            number=max(1, page["metadata"]["page_number"] - offset),
            markdown=_clean(page["text"], boilerplate),
        )
        for page in raw_pages
    ]
    return ParsedDocument(pages=pages, page_offset=offset)


def _detect_page_offset(raw_pages: list[dict]) -> int:
    """Physical page index minus the document's own printed page number.

    Front matter (cover, notices, table of contents) sits before a manual's
    own "page 1", so pymupdf4llm's physical page_number doesn't match what a
    reader sees printed on the page — and would type into a citation. The
    offset is constant across a document's body (confirmed against both
    attached HP manuals, including their appendices/index), so it's detected
    once via majority vote across pages whose printed number can be read
    from the text, then applied uniformly. Falls back to 0 (physical index
    used as-is) when too few pages yield a confident reading to trust it.
    """
    offsets: dict[int, int] = {}
    for page in raw_pages:
        printed = _printed_page_number(page["text"])
        if printed is not None:
            offset = page["metadata"]["page_number"] - printed
            offsets[offset] = offsets.get(offset, 0) + 1
    if not offsets:
        return 0
    best_offset, votes = max(offsets.items(), key=lambda item: item[1])
    # A regex misread (a table value, a part number) can produce a bogus
    # offset with only a page or two "voting" for it; require a real
    # majority before trusting one. The `// 4` scales the bar with document
    # length (2 agreeing pages means nothing in a 500-page manual); `max(3, ...)`
    # floors it for short documents, where that scaled value could be 0-2.
    if votes < max(3, len(raw_pages) // 4):
        return 0
    return best_offset


def _printed_page_number(text: str) -> int | None:
    """Best-effort read of the page's own printed number.

    It's the trailing element of the page: either the very last line (e.g.
    "Getting to know your computer 5") or, when a repeating running footer
    follows it (e.g. a company name printed on every page), the line just
    before that — checked as a leading token ("40 Chapter 4 ...") or a
    trailing one ("... overview 3"). Returns None if neither of the last
    two non-blank lines holds a standalone number.
    """
    lines = [line for line in text.splitlines() if line.strip()]
    for line in reversed(lines[-2:]):
        match = _LEADING_PAGE_NUM_RE.match(line) or _TRAILING_PAGE_NUM_RE.search(line)
        if match:
            return int(match.group(1))
    return None


def _detect_boilerplate_lines(raw_pages: list[dict], threshold: float) -> set[str]:
    counts: dict[str, int] = {}
    for page in raw_pages:
        lines = {line.strip() for line in page["text"].splitlines() if line.strip()}
        for line in lines:
            counts[line] = counts.get(line, 0) + 1
    minimum = max(2, int(len(raw_pages) * threshold))
    return {line for line, count in counts.items() if count >= minimum}


def _clean(text: str, boilerplate: set[str]) -> str:
    lines = [line for line in text.splitlines() if line.strip() not in boilerplate]
    text = "\n".join(lines)
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _MULTI_BLANK_RE.sub("\n\n", text)
    return text.strip()
