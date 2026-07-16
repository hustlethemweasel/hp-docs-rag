from pathlib import Path

from app.config import get_settings
from app.ingest.job import MigrationRunner, run
from app.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
run(
    migrations=MigrationRunner(Path(__file__).parents[3] / "alembic.ini"),
    docs_dir=Path(settings.docs_dir),
)
