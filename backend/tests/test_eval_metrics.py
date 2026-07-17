"""Behavior: retrieval-eval metrics — rank of first hit, recall@k, MRR.

Pure math on real values; no doubles. The eval package lives at the repo
root (see conftest.py).
"""

from eval.metrics import (
    RetrievedChunk,
    mean_reciprocal_rank,
    rank_of_first_hit,
    recall_at,
)


def chunk(document: str, start: int, end: int | None = None) -> RetrievedChunk:
    return RetrievedChunk(document=document, page_start=start, page_end=end or start)


def test_rank_of_first_hit_is_one_based():
    retrieved = [chunk("envy.pdf", 12), chunk("envy.pdf", 86), chunk("envy.pdf", 87)]

    assert rank_of_first_hit(retrieved, document="envy.pdf", pages={86, 87}) == 2


def test_rank_requires_the_right_document_not_just_the_page():
    retrieved = [chunk("omen.pdf", 86), chunk("envy.pdf", 86)]

    assert rank_of_first_hit(retrieved, document="envy.pdf", pages={86}) == 2


def test_a_chunk_spanning_pages_hits_any_expected_page_in_its_range():
    retrieved = [chunk("envy.pdf", 85, 88)]

    assert rank_of_first_hit(retrieved, document="envy.pdf", pages={86}) == 1


def test_rank_is_none_when_nothing_hits():
    retrieved = [chunk("envy.pdf", 12)]

    assert rank_of_first_hit(retrieved, document="envy.pdf", pages={86}) is None


def test_recall_at_k_counts_hits_at_or_above_k():
    ranks = [1, 5, 7, None]

    assert recall_at(ranks, k=6) == 0.5
    assert recall_at(ranks, k=20) == 0.75


def test_mrr_averages_reciprocal_ranks_with_misses_as_zero():
    ranks = [1, 2, None, 4]

    assert mean_reciprocal_rank(ranks) == (1 + 0.5 + 0 + 0.25) / 4
