from dataclasses import dataclass, replace

from app.ingest.embedding import Embedder
from app.rag.fusion import fuse
from app.repositories.chunks import ChunkRepository, RetrievedChunk


@dataclass
class HybridRetriever:
    """Dense + sparse retrieval, RRF-fused, capped at top_k with a refusal guard."""

    embedder: Embedder
    chunks: ChunkRepository
    candidates: int
    top_k: int
    refusal_threshold: float

    async def retrieve(self, query: str) -> list[RetrievedChunk]:
        embedding = self.embedder.embed_query(query)
        dense = await self.chunks.dense_search(embedding, limit=self.candidates)
        sparse = await self.chunks.sparse_search(query, limit=self.candidates)

        by_id = {c.chunk_id: c for c in (*dense, *sparse)}
        rankings = [[c.chunk_id for c in dense], [c.chunk_id for c in sparse]]
        fused = fuse(rankings)

        if not fused or fused[0][1] < self.refusal_threshold:
            return []

        return [
            replace(by_id[chunk_id], score=score)
            for chunk_id, score in fused[: self.top_k]
        ]
