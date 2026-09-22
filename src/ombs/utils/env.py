"""Minimal ``.env`` loader (no external dependency).

Reads ``KEY=VALUE`` lines from a ``.env`` file and populates ``os.environ`` for
any key that is not already set (real environment variables win). This is how the
Anthropic provider picks up ``ANTHROPIC_API_KEY`` without exporting it in the
shell. Supports ``#`` comments, blank lines, optional ``export`` prefix, and
single/double-quoted values.
"""

from __future__ import annotations

import os
from pathlib import Path


def _find_dotenv(start: Path) -> Path | None:
    """Walk up from ``start`` looking for a ``.env`` file."""
    for directory in [start, *start.parents]:
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None


def load_dotenv(path: str | Path | None = None) -> bool:
    """Load a ``.env`` file into ``os.environ`` (without overriding existing vars).

    Returns True if a file was found and read. ``path`` may point at a file or be
    omitted to auto-discover ``.env`` from the current working directory upward.
    """
    if path is None:
        found = _find_dotenv(Path.cwd())
    else:
        p = Path(path)
        found = p if p.is_file() else None
    if found is None:
        return False

    for raw in found.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
    return True
