from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievedChunk:
    document: str
    page_start: int
    page_end: int


def rank_of_first_hit(
    retrieved: list[RetrievedChunk], *, document: str, pages: set[int]
) -> int | None:
    """1-based rank of the first chunk from `document` overlapping `pages`."""
    for rank, chunk in enumerate(retrieved, start=1):
        if chunk.document != document:
            continue
        if any(chunk.page_start <= page <= chunk.page_end for page in pages):
            return rank
    return None


def recall_at(ranks: list[int | None], *, k: int) -> float:
    hits = sum(1 for rank in ranks if rank is not None and rank <= k)
    return hits / len(ranks)


def mean_reciprocal_rank(ranks: list[int | None]) -> float:
    return sum(1 / rank for rank in ranks if rank is not None) / len(ranks)
