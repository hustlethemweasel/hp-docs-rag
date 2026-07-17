import re
from collections.abc import Callable
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^#{1,6}\s+(?P<title>.+?)\s*$")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class ParsedPage:
    """A single page of parsed markdown, as pymupdf4llm will produce."""

    number: int
    markdown: str


@dataclass(frozen=True)
class Chunk:
    content: str
    section: str | None
    page_start: int
    page_end: int
    chunk_index: int
    token_count: int


@dataclass(frozen=True)
class _Unit:
    """A piece of text (paragraph or sentence) with the page it came from."""

    page: int
    text: str
    tokens: int


def chunk_pages(
    pages: list[ParsedPage],
    *,
    chunk_tokens: int,
    chunk_overlap: int,
    count_tokens: Callable[[str], int],
) -> list[Chunk]:
    """Structure-aware recursive chunking with overlap.

    Splits first on detected heading boundaries so a chunk never spans two
    sections, then recursively windows paragraphs (falling back to sentences
    for oversized paragraphs) to hit ~chunk_tokens with ~chunk_overlap shared
    between adjacent chunks.
    """
    chunks: list[Chunk] = []
    for heading, paragraphs in _sections(pages):
        units = _split_oversized(paragraphs, chunk_tokens, count_tokens)
        for group in _window(units, chunk_tokens, chunk_overlap):
            content = " ".join(unit.text for unit in group)
            chunks.append(
                Chunk(
                    content=content,
                    section=heading,
                    page_start=group[0].page,
                    page_end=group[-1].page,
                    chunk_index=len(chunks),
                    token_count=count_tokens(content),
                )
            )
    return chunks


def _sections(pages: list[ParsedPage]) -> list[tuple[str | None, list[_Unit]]]:
    sections: list[tuple[str | None, list[_Unit]]] = []
    heading: str | None = None
    body: list[_Unit] = []
    for page in pages:
        for block in re.split(r"\n\s*\n", page.markdown.strip()):
            block = block.strip()
            if not block:
                continue
            match = _HEADING_RE.match(block)
            if match:
                if body:
                    sections.append((heading, body))
                heading = match.group("title")
                body = []
            else:
                body.append(_Unit(page=page.number, text=block, tokens=0))
    if body:
        sections.append((heading, body))
    return sections


def _split_oversized(
    paragraphs: list[_Unit], chunk_tokens: int, count_tokens: Callable[[str], int]
) -> list[_Unit]:
    units: list[_Unit] = []
    for para in paragraphs:
        tokens = count_tokens(para.text)
        if tokens <= chunk_tokens:
            units.append(_Unit(page=para.page, text=para.text, tokens=tokens))
            continue
        for sentence in _SENTENCE_RE.split(para.text):
            sentence = sentence.strip()
            if not sentence:
                continue
            sentence_tokens = count_tokens(sentence)
            if sentence_tokens <= chunk_tokens:
                units.append(
                    _Unit(page=para.page, text=sentence, tokens=sentence_tokens)
                )
            else:
                units.extend(
                    _split_by_word_window(
                        para.page, sentence, chunk_tokens, count_tokens
                    )
                )
    return units


def _split_by_word_window(
    page: int, text: str, chunk_tokens: int, count_tokens: Callable[[str], int]
) -> list[_Unit]:
    """Hard fallback for a unit with no sentence boundary (e.g. a table row).

    Greedily packs whitespace-delimited words into windows, re-measuring with
    the real token counter after each word so it still respects chunk_tokens
    even when tokens don't map 1:1 to words.
    """
    units: list[_Unit] = []
    words = text.split()
    window: list[str] = []
    for word in words:
        candidate = window + [word]
        if window and count_tokens(" ".join(candidate)) > chunk_tokens:
            window_text = " ".join(window)
            units.append(
                _Unit(page=page, text=window_text, tokens=count_tokens(window_text))
            )
            window = [word]
        else:
            window = candidate
    if window:
        window_text = " ".join(window)
        units.append(
            _Unit(page=page, text=window_text, tokens=count_tokens(window_text))
        )
    return units


def _window(
    units: list[_Unit], chunk_tokens: int, chunk_overlap: int
) -> list[list[_Unit]]:
    groups: list[list[_Unit]] = []
    i = 0
    n = len(units)
    while i < n:
        current: list[_Unit] = []
        current_tokens = 0
        j = i
        while j < n:
            unit_tokens = units[j].tokens
            if current and current_tokens + unit_tokens > chunk_tokens:
                break
            current.append(units[j])
            current_tokens += unit_tokens
            j += 1
        groups.append(current)
        if j >= n:
            break

        overlap_tokens = 0
        k = j - 1
        while k > i and overlap_tokens < chunk_overlap:
            overlap_tokens += units[k].tokens
            k -= 1
        i = min(j, max(k + 1, i + 1))
    return groups
