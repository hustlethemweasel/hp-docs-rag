"""Behavior: re-rank fused candidates by cross-encoder relevance score.

The cross-encoder (sentence_transformers.CrossEncoder) is a third-party
model boundary — doubled with create_autospec per the constitution, never
an unspecced mock.
"""

from unittest.mock import create_autospec

from eval.rerank_experiment import rerank
from sentence_transformers import CrossEncoder

from app.repositories.chunks import RetrievedChunk


def chunk(chunk_id: int, content: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document="ENVY Guide",
        content=content,
        page_start=1,
        page_end=1,
        section=None,
        figure_ref=None,
        score=0.0,
    )


def test_rerank_sorts_candidates_by_cross_encoder_score_descending():
    reranker = create_autospec(CrossEncoder, instance=True)
    reranker.predict.return_value = [0.1, 0.9, 0.5]
    candidates = [chunk(1, "a"), chunk(2, "b"), chunk(3, "c")]

    result = rerank(reranker, "question", candidates)

    assert [c.chunk_id for c in result] == [2, 3, 1]
    reranker.predict.assert_called_once_with(
        [("question", "a"), ("question", "b"), ("question", "c")]
    )


def test_rerank_of_no_candidates_is_empty():
    reranker = create_autospec(CrossEncoder, instance=True)

    result = rerank(reranker, "question", [])

    assert result == []
    reranker.predict.assert_not_called()
