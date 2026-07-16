import hashlib
from dataclasses import dataclass
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

CHECKSUMS_FILENAME = "checksums.txt"


class ChecksumMismatch(Exception):
    """A source document's content does not match its pinned SHA-256."""


class MissingDocument(Exception):
    """A pinned source document is absent from the docs directory."""


@dataclass(frozen=True)
class VerifiedDocument:
    name: str
    path: Path
    sha256: str


def verify_checksums(docs_dir: Path) -> list[VerifiedDocument]:
    """Verify every pinned document in docs_dir against checksums.txt.

    Fails fast (constitution §2, item 4): any mismatch or missing file raises
    before ingestion touches the database.
    """
    checksums_path = docs_dir / CHECKSUMS_FILENAME
    pinned = _parse_checksums_file(checksums_path)

    verified = []
    for name, expected in pinned.items():
        path = docs_dir / name
        if not path.is_file():
            raise MissingDocument(f"pinned document not found: {name}")
        actual = _sha256_of(path)
        if actual != expected:
            raise ChecksumMismatch(f"{name}: expected {expected}, got {actual}")
        verified.append(VerifiedDocument(name=name, path=path, sha256=actual))
        logger.info("document_verified", document=name, sha256=actual)
    return verified


def _parse_checksums_file(path: Path) -> dict[str, str]:
    pinned = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        digest, name = line.split(maxsplit=1)
        pinned[name.strip()] = digest
    return pinned


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()
