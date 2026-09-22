"""Stable hashing helpers for prompts and reproducibility metadata."""

from __future__ import annotations

import hashlib


def sha256_text(text: str) -> str:
    """Return the hex SHA-256 of a UTF-8 string. Used for prompt fingerprints."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Return the hex SHA-256 of raw bytes. Used to pin frozen files by their on-disk content."""
    return hashlib.sha256(data).hexdigest()
