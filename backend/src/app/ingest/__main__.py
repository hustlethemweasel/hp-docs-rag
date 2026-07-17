import asyncio
from pathlib import Path

import httpx
import structlog
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.ingest.captioning import OllamaCaptioner
from app.ingest.embedding import load_embedder
from app.ingest.indexing import index_all
from app.ingest.job import MigrationRunner, run
from app.logging import configure_logging

logger = structlog.get_logger(__name__)

settings = get_settings()
configure_logging(settings.log_level)

verified = run(
    migrations=MigrationRunner(Path(__file__).parents[3] / "alembic.ini"),
    docs_dir=Path(settings.docs_dir),
)


async def _index() -> None:
    engine = create_async_engine(settings.database_url)
    embedder = load_embedder(settings.embedding_model)
    captioner = OllamaCaptioner(
        client=httpx.Client(base_url=settings.ollama_url, timeout=120),
        model=settings.llm_model,
    )
    try:
        total = await index_all(
            engine,
            embedder,
            captioner,
            verified,
            chunk_tokens=settings.chunk_tokens,
            chunk_overlap=settings.chunk_overlap,
        )
        logger.info("ingest_indexing_complete", chunks_written=total)
    finally:
        await engine.dispose()


asyncio.run(_index())
