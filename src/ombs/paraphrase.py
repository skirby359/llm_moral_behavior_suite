"""Paraphrase generation for robustness testing (brief §16).

Generate N paraphrases of a variant's user message that preserve every material
fact and the request itself, changing only wording/structure/tone. Running the
model on the original plus its paraphrases measures whether decisions are driven
by the situation or by surface wording.
"""

from __future__ import annotations

import json

from .providers.base import GenerationOptions, ProviderClient
from .utils.json_extract import strip_reasoning

_SYSTEM = "You are a careful paraphraser. You never add, drop, or change facts."


def build_paraphrase_prompt(text: str, n: int) -> str:
    return (
        f"Rewrite the following workplace request in {n} different ways. Keep ALL "
        "facts, names, numbers, the specific request, and its meaning identical — "
        "change only wording, sentence structure, and tone. Do not add or remove "
        "any fact, and do not answer the request.\n\n"
        f"Return a JSON array of exactly {n} strings, JSON only.\n\n"
        f"Request:\n{text.strip()}"
    )


def _extract_json_array(raw: str) -> list[str] | None:
    cleaned = strip_reasoning(raw).strip()
    # Try whole-string, then the first [...] span.
    for candidate in (cleaned, _first_array_span(cleaned)):
        if candidate is None:
            continue
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, list):
            return [str(x) for x in obj if str(x).strip()]
    return None


def _first_array_span(text: str) -> str | None:
    start = text.find("[")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def generate_paraphrases(
    provider: ProviderClient, *, model: str, text: str, n: int, options: GenerationOptions
) -> list[str]:
    """Return up to ``n`` paraphrases (empty list on failure — caller decides)."""
    result = provider.generate(
        system=_SYSTEM, prompt=build_paraphrase_prompt(text, n), model=model, options=options
    )
    if not result.ok:
        return []
    arr = _extract_json_array(result.raw_response)
    return arr[:n] if arr else []
