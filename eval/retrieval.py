"""Retrieval eval runner: recall@k + MRR for dense retrieval.

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

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from app.ingest.embedding import load_embedder
from eval.metrics import (
    RetrievedChunk,
    mean_reciprocal_rank,
    rank_of_first_hit,
    recall_at,
)

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


async def run() -> None:
    database_url = os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://app:app@localhost:5432/hpdocs"
    )
    model_name = os.environ.get("EMBEDDING_MODEL", "microsoft/harrier-oss-v1-270m")
    embedder = load_embedder(model_name)
    engine = create_async_engine(database_url)
    golden = load_golden()

    ranks: list[int | None] = []
    try:
        async with engine.connect() as connection:
            for item in golden:
                query_vec = embedder.embed_query(item.question)
                result = await connection.execute(
                    sa.text(
                        "SELECT d.filename, c.page_start, c.page_end "
                        "FROM chunks c JOIN documents d ON d.id = c.document_id "
                        "ORDER BY c.embedding <=> :query LIMIT :k"
                    ),
                    {"query": str(query_vec), "k": CANDIDATES},
                )
                retrieved = [
                    RetrievedChunk(document=row[0], page_start=row[1], page_end=row[2])
                    for row in result
                ]
                rank = rank_of_first_hit(
                    retrieved, document=item.document, pages=item.pages
                )
                ranks.append(rank)
                shown = rank if rank is not None else "miss"
                print(f"  rank={shown:>4}  {item.question}")
    finally:
        await engine.dispose()

    print()
    print(f"model:     {model_name}")
    print(f"questions: {len(golden)}")
    print(f"recall@6:  {recall_at(ranks, k=6):.3f}")
    print(f"recall@20: {recall_at(ranks, k=20):.3f}")
    print(f"MRR:       {mean_reciprocal_rank(ranks):.3f}")


if __name__ == "__main__":
    asyncio.run(run())
