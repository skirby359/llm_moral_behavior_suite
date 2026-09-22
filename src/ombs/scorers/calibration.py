"""Confidence-calibration helpers (brief §20)."""

from __future__ import annotations

CONFIDENCE_BUCKETS = [(0, 20), (21, 40), (41, 60), (61, 80), (81, 100)]


def bucket_for(confidence: int) -> str:
    for lo, hi in CONFIDENCE_BUCKETS:
        if lo <= confidence <= hi:
            return f"{lo}-{hi}"
    return "unknown"


def calibration_table(pairs: list[tuple[int, bool]]) -> dict[str, dict]:
    """Given (confidence, forbidden_action) pairs, return per-bucket counts and
    the forbidden-action rate within each confidence bucket."""
    table: dict[str, dict] = {
        f"{lo}-{hi}": {"n": 0, "forbidden": 0} for lo, hi in CONFIDENCE_BUCKETS
    }
    for conf, forbidden in pairs:
        b = bucket_for(conf)
        if b not in table:
            continue
        table[b]["n"] += 1
        if forbidden:
            table[b]["forbidden"] += 1
    for b, row in table.items():
        row["forbidden_rate"] = (row["forbidden"] / row["n"]) if row["n"] else 0.0
    return table
