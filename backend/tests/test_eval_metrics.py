"""Behavior: retrieval-eval metrics — rank of first hit, recall@k, MRR.

Pure math on real values; no doubles. The eval package lives at the repo
root (see conftest.py).
"""

from eval.metrics import (
    RetrievedChunk,
    context_precision,
    context_recall,
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


# --- context precision/recall -------------------------------------------------


def test_context_recall_is_one_when_a_relevant_chunk_was_retrieved():
    retrieved = [chunk("omen.pdf", 1), chunk("envy.pdf", 86)]

    assert context_recall(retrieved, document="envy.pdf", pages={86}) == 1.0


def test_context_recall_is_zero_when_nothing_relevant_was_retrieved():
    retrieved = [chunk("envy.pdf", 12)]

    assert context_recall(retrieved, document="envy.pdf", pages={86}) == 0.0


def test_context_recall_of_an_empty_retrieval_is_zero():
    assert context_recall([], document="envy.pdf", pages={86}) == 0.0


def test_context_precision_rewards_relevant_chunks_ranked_higher():
    # relevant at rank 1 only: precision@1 = 1/1 = 1.0
    top_hit = [chunk("envy.pdf", 86), chunk("envy.pdf", 12), chunk("omen.pdf", 1)]
    assert context_precision(top_hit, document="envy.pdf", pages={86}) == 1.0

    # relevant at rank 3 only: precision@3 = 1/3
    buried_hit = [chunk("omen.pdf", 1), chunk("envy.pdf", 12), chunk("envy.pdf", 86)]
    assert context_precision(buried_hit, document="envy.pdf", pages={86}) == 1 / 3


def test_context_precision_averages_over_every_relevant_rank():
    # relevant at ranks 1 and 4: (1/1 + 2/4) / 2 = 0.75
    retrieved = [
        chunk("envy.pdf", 86),
        chunk("omen.pdf", 1),
        chunk("omen.pdf", 2),
        chunk("envy.pdf", 87),
    ]

    assert context_precision(retrieved, document="envy.pdf", pages={86, 87}) == 0.75


def test_context_precision_is_zero_when_nothing_relevant_was_retrieved():
    retrieved = [chunk("omen.pdf", 1), chunk("omen.pdf", 2)]

    assert context_precision(retrieved, document="envy.pdf", pages={86}) == 0.0


def test_context_precision_of_an_empty_retrieval_is_zero():
    assert context_precision([], document="envy.pdf", pages={86}) == 0.0
