from collections import defaultdict
from collections.abc import Sequence

RRF_K = 60


def fuse(rankings: Sequence[Sequence[int]], k: int = RRF_K) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion: score(id) = sum of 1/(k + rank), rank 1-based.

    Returns (id, score) pairs sorted by score descending; ties break by id so
    fusion is deterministic regardless of retriever ordering.
    """
    scores: dict[int, float] = defaultdict(float)
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] += 1 / (k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))
