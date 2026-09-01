"""Checksum helpers used to validate downloaded data files."""

from __future__ import annotations

import hashlib
from pathlib import Path

CHUNK_SIZE = 1024 * 1024


class ChecksumMismatch(Exception):
    """Raised when a file's checksum does not match the expected value."""

    def __init__(self, path: Path, expected: str, actual: str) -> None:
        super().__init__(
            f"checksum mismatch for {path}: expected {expected}, got {actual}"
        )
        self.path = path
        self.expected = expected
        self.actual = actual


def md5_file(path: str | Path, chunk_size: int = CHUNK_SIZE) -> str:
    """Return the hex MD5 digest of a file, read incrementally.

    MD5 is used because that is the digest Harvard Dataverse publishes. It
    guards against truncated or corrupted transfers, not against a malicious
    actor, so its weakness as a cryptographic hash is not relevant here.
    """
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_md5(path: str | Path, expected: str) -> str:
    """Verify a file against an expected MD5, returning the digest on success."""
    actual = md5_file(path)
    if actual.lower() != expected.lower():
        raise ChecksumMismatch(Path(path), expected, actual)
    return actual
