"""The A5 and tool-family templates are versioned in their own right.

Until 12 September 2026 `FactualRecord`, `ToolRunRecord` and `ToolMultiTurnRecord` stamped only
the global `PROMPT_TEMPLATE_VERSION`, whose changelog is about the boundary template, and carried
no prompt hash. A silent edit to `FACTUAL_TEMPLATE` or `build_tool_prompt` would therefore have
produced records indistinguishable from the ones already committed. These tests pin the rendered
text to a SHA-256 so that the template cannot change without the version changing beside it.

Rule: if a pinned hash below moves, bump the matching `*_TEMPLATE_VERSION` in `prompt_builder.py`
and then update the pin. Never update the pin alone.
"""

from __future__ import annotations

from ombs.prompt_builder import (
    FACTUAL_RESPONSE_SCHEMA_BLOCK,
    FACTUAL_TEMPLATE,
    FACTUAL_TEMPLATE_VERSION,
    TOOL_SIGNATURES,
    TOOL_TEMPLATE_VERSION,
    build_tool_prompt,
    factual_prompt_hash,
    tool_prompt_hash,
)
from ombs.schemas import FactualRecord, ToolMultiTurnRecord, ToolRunRecord
from ombs.utils.hashing import sha256_text

# Pinned at FACTUAL_TEMPLATE_VERSION 0.1 / TOOL_TEMPLATE_VERSION 0.1 (12 Sep 2026).
PINS = {
    ("factual_template", "0.1"): "5e1101f0a7aa059db2407d3b8db0066952c38b80bcbaf95ff2b079432c0bc8ee",
    ("factual_schema", "0.1"): "3cdc634355826e95cdef96734088b9235563796b09db6185d8d3055583e58bfa",
    ("tool_prompt", "0.1"): "93c03350cac56cedec9523790c2afd673dfcaff20cdd1b3d576bb8612cecdc9d",
}


def test_factual_template_is_pinned_to_its_version():
    assert sha256_text(FACTUAL_TEMPLATE) == PINS[("factual_template", FACTUAL_TEMPLATE_VERSION)]
    assert sha256_text(FACTUAL_RESPONSE_SCHEMA_BLOCK) == PINS[("factual_schema", FACTUAL_TEMPLATE_VERSION)]


def test_tool_prompt_is_pinned_to_its_version():
    rendered = build_tool_prompt("administrative_assistant", "Send the file.", sorted(TOOL_SIGNATURES))
    assert sha256_text(rendered) == PINS[("tool_prompt", TOOL_TEMPLATE_VERSION)]


def test_family_hashes_commit_to_their_own_version_and_differ_from_each_other():
    text = "<<SYSTEM>>\nsys\n\n<<USER>>\nuser"
    assert factual_prompt_hash(text) == factual_prompt_hash(text)
    assert factual_prompt_hash(text) != factual_prompt_hash(text + " ")
    assert factual_prompt_hash(text) != tool_prompt_hash(text)
    # The version is part of the fingerprint, so a bump alone moves every hash.
    assert factual_prompt_hash(text) == sha256_text(f"factual-v{FACTUAL_TEMPLATE_VERSION}\n{text}")
    assert tool_prompt_hash(text) == sha256_text(f"tool-v{TOOL_TEMPLATE_VERSION}\n{text}")


def test_provenance_fields_are_additive_so_committed_records_still_parse():
    """Records written before 12 Sep 2026 carry neither field; they must load with None."""
    common = dict(run_id="r", timestamp="t", provider="ollama", model="m", scenario_id="s",
                  scenario_version="0.1", role="administrative_assistant",
                  prompt_template_version="0.4", temperature=1.0)
    f = FactualRecord(system_prompt_style="minimal", top_p=1.0, question="q", true_value="a",
                      false_value="b", **common)
    assert f.factual_template_version is None and f.prompt_hash is None
    t = ToolRunRecord(raw_response="", parsed_ok=False, **common)
    assert t.tool_template_version is None and t.prompt_hash is None
    m = ToolMultiTurnRecord(**common)
    assert m.tool_template_version is None and m.prompt_hash is None
    # and the new fields round-trip when present
    t2 = ToolRunRecord(raw_response="", parsed_ok=False, tool_template_version=TOOL_TEMPLATE_VERSION,
                       prompt_hash="x", **common)
    assert t2.model_dump()["tool_template_version"] == TOOL_TEMPLATE_VERSION
