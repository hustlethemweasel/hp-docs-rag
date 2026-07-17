import re
from pathlib import Path

import pymupdf4llm
import structlog

from app.ingest.chunking import ParsedPage

logger = structlog.get_logger(__name__)

_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")


def parse_pdf(path: Path, *, boilerplate_threshold: float = 0.5) -> list[ParsedPage]:
    """Parse a PDF into per-page markdown with light cleaning (SPEC §7.1).

    Heading/structure detection and hyphenation repair are handled by
    pymupdf4llm's layout analysis; this module drops repeated headers/footers
    (detected by line repetition across pages) and collapses whitespace.
    """
    raw_pages = pymupdf4llm.to_markdown(str(path), page_chunks=True)
    assert isinstance(raw_pages, list)  # page_chunks=True always returns a list
    boilerplate = _detect_boilerplate_lines(raw_pages, boilerplate_threshold)
    logger.info(
        "pdf_parsed",
        path=str(path),
        pages=len(raw_pages),
        boilerplate_lines=len(boilerplate),
    )
    return [
        ParsedPage(
            number=page["metadata"]["page_number"],
            markdown=_clean(page["text"], boilerplate),
        )
        for page in raw_pages
    ]


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
