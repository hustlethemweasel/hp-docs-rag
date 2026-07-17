"""Behavior: ingest verifies pinned SHA-256s of the source documents.

Real collaborators: actual files on disk in tmp_path, actual hashing. No doubles.
"""

import hashlib

import pytest

from app.ingest.checksums import ChecksumMismatch, MissingDocument, verify_checksums


def write_checksums_file(directory, entries):
    lines = [f"{digest}  {name}" for name, digest in entries.items()]
    path = directory / "checksums.txt"
    path.write_text("\n".join(lines) + "\n")
    return path


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_passes_when_all_documents_match(tmp_path):
    (tmp_path / "envy.pdf").write_bytes(b"envy contents")
    (tmp_path / "omen.pdf").write_bytes(b"omen contents")
    write_checksums_file(
        tmp_path,
        {
            "envy.pdf": sha256(b"envy contents"),
            "omen.pdf": sha256(b"omen contents"),
        },
    )

    verified = verify_checksums(tmp_path)

    assert sorted(doc.name for doc in verified) == ["envy.pdf", "omen.pdf"]
    assert all(doc.sha256 == sha256(doc.path.read_bytes()) for doc in verified)


def test_fails_fast_on_checksum_mismatch(tmp_path):
    (tmp_path / "envy.pdf").write_bytes(b"tampered")
    write_checksums_file(tmp_path, {"envy.pdf": sha256(b"original")})

    with pytest.raises(ChecksumMismatch) as excinfo:
        verify_checksums(tmp_path)

    assert "envy.pdf" in str(excinfo.value)


def test_fails_fast_on_missing_document(tmp_path):
    write_checksums_file(tmp_path, {"envy.pdf": sha256(b"anything")})

    with pytest.raises(MissingDocument) as excinfo:
        verify_checksums(tmp_path)

    assert "envy.pdf" in str(excinfo.value)


def test_fails_fast_on_missing_checksums_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        verify_checksums(tmp_path)
