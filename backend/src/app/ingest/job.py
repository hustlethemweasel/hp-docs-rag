from pathlib import Path

import structlog
from alembic import command
from alembic.config import Config

from app.ingest.checksums import VerifiedDocument, verify_checksums

logger = structlog.get_logger(__name__)


class MigrationRunner:
    """Boundary around Alembic (external process semantics)."""

    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path

    def upgrade_to_head(self) -> None:
        command.upgrade(Config(str(self._config_path)), "head")


def run(migrations: MigrationRunner, docs_dir: Path) -> list[VerifiedDocument]:
    """Apply schema migrations, then verify pinned documents.

    Document indexing (parse → chunk → embed) arrives in Milestone 2.
    """
    logger.info("ingest_started", docs_dir=str(docs_dir))
    migrations.upgrade_to_head()
    logger.info("migrations_applied")
    verified = verify_checksums(docs_dir)
    logger.info("documents_verified", count=len(verified))
    return verified
