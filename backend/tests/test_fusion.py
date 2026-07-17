"""Behavior: Reciprocal Rank Fusion over per-retriever rankings.

Pure math, no collaborators: score(id) = sum over rankings of 1/(k + rank),
rank 1-based. Ids appearing in several rankings accumulate score, which is
what lets agreement between dense and sparse retrieval outrank either alone.
"""

import pytest

from app.rag.fusion import fuse


def test_agreement_between_rankings_outranks_a_single_high_rank():
    dense = [1, 2, 3]
    sparse = [3, 2, 4]

    fused = fuse([dense, sparse])

    # 2 and 3 appear in both lists; 1 leads only the dense list.
    assert sorted(chunk_id for chunk_id, _ in fused[:2]) == [2, 3]
    assert fused[-1][0] in (1, 4)


def test_scores_follow_the_rrf_formula():
    fused = fuse([[7], [7]], k=60)

    ((chunk_id, score),) = fused
    assert chunk_id == 7
    assert score == pytest.approx(2 / 61)


def test_each_id_appears_once():
    fused = fuse([[1, 2], [2, 1]])

    assert sorted(chunk_id for chunk_id, _ in fused) == [1, 2]


def test_ties_break_deterministically_by_id():
    # Disjoint rankings of equal length produce pairwise-tied scores.
    fused = fuse([[9, 5], [4, 8]])

    assert [chunk_id for chunk_id, _ in fused] == [4, 9, 5, 8]


def test_empty_rankings_fuse_to_nothing():
    assert fuse([]) == []
    assert fuse([[], []]) == []
