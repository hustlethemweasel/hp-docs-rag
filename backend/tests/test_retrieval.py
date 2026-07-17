"""Behavior: hybrid retrieval — embed, dense+sparse search, RRF fuse, refusal guard.

Real collaborator: the actual RRF fusion math (app.rag.fusion.fuse), so the
ranking behavior under test is genuine. The embedder and chunk repository are
the real external boundaries (model weights, DB) — doubled with
create_autospec per the constitution.
"""

from unittest.mock import create_autospec

from app.ingest.embedding import Embedder
from app.rag.retrieval import HybridRetriever
from app.repositories.chunks import ChunkRepository, RetrievedChunk


def chunk(
    chunk_id: int, *, score: float, content: str = "chunk text"
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document="ENVY Guide",
        content=content,
        page_start=1,
        page_end=1,
        section="Setup",
        figure_ref=None,
        score=score,
    )


def make_retriever(
    *, candidates: int = 20, top_k: int = 6, refusal_threshold: float = 0.0
):
    embedder = create_autospec(Embedder, instance=True)
    embedder.embed_query.return_value = [0.1] * 640
    chunks = create_autospec(ChunkRepository, instance=True)
    retriever = HybridRetriever(
        embedder=embedder,
        chunks=chunks,
        candidates=candidates,
        top_k=top_k,
        refusal_threshold=refusal_threshold,
    )
    return retriever, embedder, chunks


async def test_embeds_the_query_with_the_query_side_prompt():
    retriever, embedder, chunks = make_retriever()
    chunks.dense_search.return_value = []
    chunks.sparse_search.return_value = []

    await retriever.retrieve("how do I clean the printhead?")

    embedder.embed_query.assert_called_once_with("how do I clean the printhead?")
    embedder.embed_documents.assert_not_called()


async def test_retriever_limits_are_passed_to_both_searches():
    retriever, _, chunks = make_retriever(candidates=20)
    chunks.dense_search.return_value = []
    chunks.sparse_search.return_value = []

    await retriever.retrieve("query")

    chunks.dense_search.assert_called_once_with([0.1] * 640, limit=20)
    chunks.sparse_search.assert_called_once_with("query", limit=20)


async def test_chunks_found_by_both_retrievers_outrank_a_single_retriever_hit():
    retriever, _, chunks = make_retriever(top_k=6)
    chunks.dense_search.return_value = [chunk(1, score=0.9), chunk(2, score=0.5)]
    chunks.sparse_search.return_value = [chunk(2, score=0.8), chunk(3, score=0.3)]

    results = await retriever.retrieve("query")

    assert [c.chunk_id for c in results] == [2, 1, 3]


async def test_top_k_caps_the_number_of_returned_chunks():
    retriever, _, chunks = make_retriever(top_k=2)
    chunks.dense_search.return_value = [chunk(i, score=1.0 / i) for i in range(1, 5)]
    chunks.sparse_search.return_value = []

    results = await retriever.retrieve("query")

    assert len(results) == 2
    assert [c.chunk_id for c in results] == [1, 2]


async def test_returns_empty_when_best_fused_score_is_below_the_refusal_threshold():
    retriever, _, chunks = make_retriever(refusal_threshold=0.9)
    chunks.dense_search.return_value = [chunk(1, score=0.4)]
    chunks.sparse_search.return_value = []

    results = await retriever.retrieve("query")

    assert results == []


async def test_no_results_from_either_retriever_returns_empty():
    retriever, _, chunks = make_retriever()
    chunks.dense_search.return_value = []
    chunks.sparse_search.return_value = []

    results = await retriever.retrieve("query")

    assert results == []
