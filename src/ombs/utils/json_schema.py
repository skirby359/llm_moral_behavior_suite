"""Rewrite a pydantic-generated JSON schema for frontier structured output.

Both frontier vendors refuse the schema pydantic emits, and — probed
2026-08-04 — they refuse it for the *same* reason, so this lives here rather
than inside either provider:

    Anthropic (`claude-opus-5`, `output_config.format.type: "json_schema"`)
      HTTP 400: "For 'object' type, 'additionalProperties' must be explicitly
      set to false"

    OpenAI (`gpt-5.5`, `response_format.json_schema.strict: true`)
      requires `additionalProperties: false` on every object and **every**
      property present in `required` — strict mode has no optional fields.

Two consequences worth being explicit about, because both are lossy:

1. ``ModelDecision`` has two list fields carrying defaults
   (``missing_information``, ``risk_flags``) which pydantic therefore leaves out
   of ``required``. They are promoted to required here. Safe: an empty list is a
   valid value for both, so the model can still say "nothing missing".
2. Validation keywords outside the vendors' accepted subset are dropped —
   notably ``minimum``/``maximum``, which ``confidence`` carries from
   ``Field(ge=0, le=100)``. **Nothing goes unenforced as a result**: the response
   is validated against ``ModelDecision`` downstream either way, so the check
   moves from generation time to parse time. A model that returns
   ``confidence: 130`` is recorded as a parse failure rather than being
   prevented from saying it.
"""

from __future__ import annotations

# Keywords the strict/structured-output subsets do not accept.
UNSUPPORTED_KEYWORDS = frozenset(
    {
        "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
        "minLength", "maxLength", "pattern", "format",
        "minItems", "maxItems", "uniqueItems",
        "default", "examples",
    }
)


def to_strict_schema(node):
    """Return ``node`` rewritten into the vendors' shared strict subset.

    Recurses through dicts and lists so nested objects (``$defs`` entries,
    array ``items``, ``anyOf`` branches) are covered too. Pure — the input is
    not mutated.
    """
    if isinstance(node, list):
        return [to_strict_schema(n) for n in node]
    if not isinstance(node, dict):
        return node

    out = {k: to_strict_schema(v) for k, v in node.items() if k not in UNSUPPORTED_KEYWORDS}
    if out.get("type") == "object" and "properties" in out:
        out["additionalProperties"] = False
        out["required"] = list(out["properties"].keys())
    return out
