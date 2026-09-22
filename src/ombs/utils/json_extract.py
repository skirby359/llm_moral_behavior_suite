"""Robust JSON extraction from messy model output.

Local models — qwen3 in particular — wrap their answer in reasoning blocks
(``<think>...</think>``), markdown code fences, or prose. The model under test
is *asked* to return JSON only, but whether it does is itself a measured signal,
so extraction must be forgiving and must never raise on bad input. Callers get a
parsed ``dict`` or ``None`` plus a human-readable reason.
"""

from __future__ import annotations

import json
import re

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_CODE_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def strip_reasoning(text: str) -> str:
    """Remove ``<think>...</think>`` blocks (and an unterminated trailing one)."""
    text = _THINK_BLOCK.sub("", text)
    # An unterminated <think> (truncated output) — drop everything up to its end.
    lowered = text.lower()
    if "<think>" in lowered and "</think>" not in lowered:
        idx = lowered.index("<think>")
        text = text[:idx]
    return text


def _first_balanced_object(text: str) -> str | None:
    """Return the first balanced ``{...}`` span, respecting strings/escapes."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def extract_json(text: str) -> tuple[dict | None, str | None]:
    """Best-effort parse of a JSON object from raw model output.

    Returns ``(obj, None)`` on success or ``(None, reason)`` on failure. Tries,
    in order: reasoning-stripped whole-string parse, fenced code block, then the
    first balanced ``{...}`` span.
    """
    if text is None or not text.strip():
        return None, "empty_response"

    cleaned = strip_reasoning(text).strip()

    # 1. The whole thing is already JSON.
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj, None
    except json.JSONDecodeError:
        pass

    # 2. A fenced ```json ... ``` block.
    fence = _CODE_FENCE.search(cleaned)
    if fence:
        try:
            obj = json.loads(fence.group(1).strip())
            if isinstance(obj, dict):
                return obj, None
        except json.JSONDecodeError:
            pass

    # 3. The first balanced object embedded in prose.
    span = _first_balanced_object(cleaned)
    if span is not None:
        try:
            obj = json.loads(span)
            if isinstance(obj, dict):
                return obj, None
        except json.JSONDecodeError as exc:
            return None, f"balanced_object_invalid: {exc.msg}"

    return None, "no_json_object_found"
