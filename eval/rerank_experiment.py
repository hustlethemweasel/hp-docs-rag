"""Re-ranker spike (SPEC §18): does a cross-encoder re-ranker improve on
RRF-fused hybrid retrieval enough to justify its latency?

Compares, for every non-negative golden case, the RRF-fused top-6 (the
production HybridRetriever's output) against a cross-encoder re-ranking of
the same top-20 fused candidates. A one-off decision spike, not wired into
the production HybridRetriever — the evidence lands in eval/REPORT.md.

Run from the repo root against a fully ingested database:

    uv run --project backend python -m eval.rerank_experiment
"""

import asyncio
from dataclasses import replace

from sentence_transformers import CrossEncoder
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.ingest.embedding import Embedder, load_embedder
from app.rag.fusion import fuse
from app.repositories.chunks import ChunkRepository, RetrievedChunk
from eval.golden import load_golden
from eval.metrics import (
    context_precision,
    mean_reciprocal_rank,
    rank_of_first_hit,
    recall_at,
)

RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
CANDIDATES = 20
TOP_K = 6


async def fused_candidates(
    question: str, *, embedder: Embedder, chunks: ChunkRepository
) -> list[RetrievedChunk]:
    """The same dense+sparse+RRF fusion as HybridRetriever, without the
    top_k truncation, so the re-ranker has the full candidate pool to work
    with."""
    embedding = embedder.embed_query(question)
    dense = await chunks.dense_search(embedding, limit=CANDIDATES)
    sparse = await chunks.sparse_search(question, limit=CANDIDATES)
    by_id = {c.chunk_id: c for c in (*dense, *sparse)}
    rankings = [[c.chunk_id for c in dense], [c.chunk_id for c in sparse]]
    fused = fuse(rankings)
    return [replace(by_id[chunk_id], score=score) for chunk_id, score in fused]


def rerank(
    reranker: CrossEncoder, question: str, candidates: list[RetrievedChunk]
) -> list[RetrievedChunk]:
    if not candidates:
        return []
    pairs = [(question, c.content) for c in candidates]
    # pyrefly: ignore [no-matching-overload]
    scores = reranker.predict(pairs)
    scored = [
        replace(c, score=float(s)) for c, s in zip(candidates, scores, strict=True)
    ]
    return sorted(scored, key=lambda c: c.score, reverse=True)


async def run() -> None:
    settings = get_settings()
    embedder = load_embedder(settings.embedding_model)
    reranker = CrossEncoder(RERANKER_MODEL)
    engine = create_async_engine(settings.database_url)
    golden = [c for c in load_golden() if not c.expect_refusal and c.document]

    baseline_ranks: list[int | None] = []
    reranked_ranks: list[int | None] = []
    baseline_precisions: list[float] = []
    reranked_precisions: list[float] = []
    try:
        async with engine.connect() as connection:
            chunk_repository = ChunkRepository(connection)
            for case in golden:
                assert case.document is not None
                candidates = await fused_candidates(
                    case.question, embedder=embedder, chunks=chunk_repository
                )
                baseline_top6 = candidates[:TOP_K]
                reranked_top6 = rerank(reranker, case.question, candidates)[:TOP_K]

                baseline_rank = rank_of_first_hit(
                    baseline_top6, document=case.document, pages=case.pages
                )
                reranked_rank = rank_of_first_hit(
                    reranked_top6, document=case.document, pages=case.pages
                )
                baseline_ranks.append(baseline_rank)
                reranked_ranks.append(reranked_rank)
                baseline_precisions.append(
                    context_precision(
                        baseline_top6, document=case.document, pages=case.pages
                    )
                )
                reranked_precisions.append(
                    context_precision(
                        reranked_top6, document=case.document, pages=case.pages
                    )
                )
                print(
                    f"  {case.id:<28} baseline_rank={baseline_rank!s:>4}  "
                    f"reranked_rank={reranked_rank!s:>4}"
                )
    finally:
        await engine.dispose()

    n = len(golden)
    print()
    print(f"n={n}")
    print(
        "baseline  recall@6={:.3f}  MRR={:.3f}  ctx_precision={:.3f}".format(
            recall_at(baseline_ranks, k=6),
            mean_reciprocal_rank(baseline_ranks),
            sum(baseline_precisions) / n,
        )
    )
    print(
        "reranked  recall@6={:.3f}  MRR={:.3f}  ctx_precision={:.3f}".format(
            recall_at(reranked_ranks, k=6),
            mean_reciprocal_rank(reranked_ranks),
            sum(reranked_precisions) / n,
        )
    )


if __name__ == "__main__":
    asyncio.run(run())
