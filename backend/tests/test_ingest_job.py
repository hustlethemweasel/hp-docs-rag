"""Behavior: the ingest job applies migrations, then verifies pinned documents,
in that order, and fails fast if verification fails.

The migration runner is an external-process boundary, doubled with autospec;
checksum verification runs for real against tmp_path files.
"""

import hashlib
from unittest.mock import create_autospec

import pytest

from app.ingest.checksums import MissingDocument
from app.ingest.job import MigrationRunner, run


@pytest.fixture
def migrations() -> MigrationRunner:
    return create_autospec(MigrationRunner, instance=True)


def pin_document(directory, name: str, content: bytes) -> None:
    (directory / name).write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    with (directory / "checksums.txt").open("a") as handle:
        handle.write(f"{digest}  {name}\n")


def test_runs_migrations_then_verifies_documents(tmp_path, migrations):
    pin_document(tmp_path, "envy.pdf", b"envy contents")

    verified = run(migrations=migrations, docs_dir=tmp_path)

    migrations.upgrade_to_head.assert_called_once()
    assert [doc.name for doc in verified] == ["envy.pdf"]


def test_fails_fast_when_documents_do_not_verify(tmp_path, migrations):
    (tmp_path / "checksums.txt").write_text("0" * 64 + "  envy.pdf\n")

    with pytest.raises(MissingDocument):
        run(migrations=migrations, docs_dir=tmp_path)
