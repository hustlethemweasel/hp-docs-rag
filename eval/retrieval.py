"""Retrieval eval runner: recall@k + MRR, dense-only and full hybrid.

Dense-only numbers gate embedding-model swaps (the retriever a swap actually
changes); hybrid numbers (dense + FTS fused with RRF, via the real
HybridRetriever) show what production retrieves and evidence the hybrid
search rationale in SPEC.md.

Run from the repo root against an ingested database:

    uv run --project backend python -m eval.retrieval

Environment: DATABASE_URL (defaults to the compose-exposed local Postgres),
EMBEDDING_MODEL (defaults to the model pinned in .env.example).
"""

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine

from app.ingest.embedding import load_embedder
from app.rag.retrieval import HybridRetriever
from app.repositories.chunks import ChunkRepository
from eval.metrics import mean_reciprocal_rank, rank_of_first_hit, recall_at

GOLDEN_PATH = Path(__file__).parent / "retrieval.jsonl"
CANDIDATES = 20


@dataclass(frozen=True)
class GoldenQuestion:
    question: str
    document: str
    pages: set[int]


def load_golden() -> list[GoldenQuestion]:
    questions = []
    for line in GOLDEN_PATH.read_text().splitlines():
        record = json.loads(line)
        questions.append(
            GoldenQuestion(
                question=record["question"],
                document=record["document"],
                pages=set(record["pages"]),
            )
        )
    return questions


def _summarize(label: str, ranks: list[int | None]) -> None:
    print(f"{label}:")
    print(f"  recall@6:  {recall_at(ranks, k=6):.3f}")
    print(f"  recall@20: {recall_at(ranks, k=20):.3f}")
    print(f"  MRR:       {mean_reciprocal_rank(ranks):.3f}")


async def run() -> None:
    database_url = os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://app:app@localhost:5432/hpdocs"
    )
    model_name = os.environ.get("EMBEDDING_MODEL", "microsoft/harrier-oss-v1-270m")
    embedder = load_embedder(model_name)
    engine = create_async_engine(database_url)
    golden = load_golden()

    dense_ranks: list[int | None] = []
    hybrid_ranks: list[int | None] = []
    try:
        async with engine.connect() as connection:
            chunks = ChunkRepository(connection)
            # top_k=CANDIDATES (not the production 6) so recall@20 is
            # measurable; ranks within the fused list are unaffected.
            retriever = HybridRetriever(
                embedder=embedder,
                chunks=chunks,
                candidates=CANDIDATES,
                top_k=CANDIDATES,
                refusal_threshold=0.0,
            )
            for item in golden:
                embedding = embedder.embed_query(item.question)
                dense = await chunks.dense_search(embedding, limit=CANDIDATES)
                hybrid = await retriever.retrieve(item.question)
                dense_rank = rank_of_first_hit(
                    dense, document=item.document, pages=item.pages
                )
                hybrid_rank = rank_of_first_hit(
                    hybrid, document=item.document, pages=item.pages
                )
                dense_ranks.append(dense_rank)
                hybrid_ranks.append(hybrid_rank)
                shown_dense = dense_rank if dense_rank is not None else "miss"
                shown_hybrid = hybrid_rank if hybrid_rank is not None else "miss"
                print(
                    f"  dense={shown_dense:>4}  hybrid={shown_hybrid:>4}"
                    f"  {item.question}"
                )
    finally:
        await engine.dispose()

    print()
    print(f"model:     {model_name}")
    print(f"questions: {len(golden)}")
    _summarize("dense", dense_ranks)
    _summarize("hybrid (dense + FTS, RRF)", hybrid_ranks)


if __name__ == "__main__":
    asyncio.run(run())
