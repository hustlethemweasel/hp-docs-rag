from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


class HasPageRange(Protocol):
    """Structural type shared by eval.metrics.RetrievedChunk and the real
    app.repositories.chunks.RetrievedChunk, so these metrics work against
    either without conversion. Declared read-only (properties, not plain
    attributes) so frozen dataclasses satisfy it structurally."""

    @property
    def document(self) -> str: ...
    @property
    def page_start(self) -> int: ...
    @property
    def page_end(self) -> int: ...


@dataclass(frozen=True)
class RetrievedChunk:
    document: str
    page_start: int
    page_end: int


def _overlaps(chunk: HasPageRange, *, document: str, pages: set[int]) -> bool:
    if chunk.document != document:
        return False
    return any(chunk.page_start <= page <= chunk.page_end for page in pages)


def rank_of_first_hit(
    retrieved: Sequence[HasPageRange], *, document: str, pages: set[int]
) -> int | None:
    """1-based rank of the first chunk from `document` overlapping `pages`."""
    for rank, chunk in enumerate(retrieved, start=1):
        if _overlaps(chunk, document=document, pages=pages):
            return rank
    return None


def context_recall(
    retrieved: Sequence[HasPageRange], *, document: str, pages: set[int]
) -> float:
    """Was any expected page retrieved at all?"""
    hit = any(_overlaps(c, document=document, pages=pages) for c in retrieved)
    return 1.0 if hit else 0.0


def context_precision(
    retrieved: Sequence[HasPageRange], *, document: str, pages: set[int]
) -> float:
    """Average precision over the ranks of relevant chunks (RAGAS-style)."""
    relevant_ranks = [
        rank
        for rank, chunk in enumerate(retrieved, start=1)
        if _overlaps(chunk, document=document, pages=pages)
    ]
    if not relevant_ranks:
        return 0.0
    precisions = [hits / rank for hits, rank in enumerate(relevant_ranks, start=1)]
    return sum(precisions) / len(precisions)


def recall_at(ranks: list[int | None], *, k: int) -> float:
    hits = sum(1 for rank in ranks if rank is not None and rank <= k)
    return hits / len(ranks)


def mean_reciprocal_rank(ranks: list[int | None]) -> float:
    return sum(1 / rank for rank in ranks if rank is not None) / len(ranks)
