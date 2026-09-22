"""Tests for the frontier structured-output schema transform.

The transform exists because both frontier vendors reject the schema pydantic
emits (probed 2026-08-04). These tests pin the two properties the vendors
actually require, plus the mapping each provider does on top — including the
case that motivated the work: ``format`` must never be silently dropped, because
a dropped constraint turns a format failure into what looks like a content
failure.
"""

from __future__ import annotations

import copy

import pytest

from ombs.providers.anthropic import AnthropicProvider
from ombs.providers.openai import _response_format
from ombs.schemas import ModelDecision
from ombs.utils.json_schema import to_strict_schema

RAW = ModelDecision.model_json_schema()


def test_every_object_gets_additional_properties_false():
    out = to_strict_schema(RAW)
    assert out["additionalProperties"] is False


def test_optional_fields_are_promoted_to_required():
    # pydantic omits the two default_factory list fields; strict mode has no
    # concept of an optional property, so both must be promoted.
    assert "missing_information" not in RAW["required"]
    assert "risk_flags" not in RAW["required"]
    out = to_strict_schema(RAW)
    assert set(out["required"]) == set(out["properties"])
    assert "missing_information" in out["required"]


def test_unsupported_validation_keywords_are_stripped():
    # confidence carries minimum/maximum from Field(ge=0, le=100).
    assert RAW["properties"]["confidence"]["minimum"] == 0
    out = to_strict_schema(RAW)
    assert "minimum" not in out["properties"]["confidence"]
    assert "maximum" not in out["properties"]["confidence"]
    # ...but the range is still enforced at parse time, which is the whole
    # justification for stripping it.
    with pytest.raises(Exception):
        ModelDecision.model_validate(
            {
                "recommended_action": "refuse",
                "decision_class": "safe_boundary_preserved",
                "should_take_irreversible_action": False,
                "should_send_or_disclose_information": False,
                "confidence": 130,
                "reasoning_summary": "x",
                "policy_or_boundary_identified": "y",
                "escalation_target": "none",
            }
        )


def test_enums_and_types_survive():
    out = to_strict_schema(RAW)
    assert "enum" in out["properties"]["recommended_action"]
    assert out["properties"]["missing_information"]["type"] == "array"
    assert out["properties"]["missing_information"]["items"]["type"] == "string"


def test_nested_objects_are_rewritten_too():
    nested = {
        "type": "object",
        "properties": {
            "outer": {
                "type": "object",
                "properties": {"n": {"type": "integer", "minimum": 1}},
                "required": [],
            },
            "listed": {
                "type": "array",
                "items": {"type": "object", "properties": {"a": {"type": "string"}}},
            },
        },
        "required": [],
    }
    out = to_strict_schema(nested)
    inner = out["properties"]["outer"]
    assert inner["additionalProperties"] is False
    assert inner["required"] == ["n"]
    assert "minimum" not in inner["properties"]["n"]
    item = out["properties"]["listed"]["items"]
    assert item["additionalProperties"] is False
    assert item["required"] == ["a"]


def test_transform_does_not_mutate_its_input():
    before = copy.deepcopy(RAW)
    to_strict_schema(RAW)
    assert RAW == before


# --------------------------------------------------------------------------- #
# Per-provider mapping
# --------------------------------------------------------------------------- #


def test_openai_format_mapping():
    assert _response_format(None) is None
    assert _response_format("json") == {"type": "json_object"}
    rf = _response_format(RAW)
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["strict"] is True
    assert rf["json_schema"]["schema"]["additionalProperties"] is False


def test_openai_rejects_an_unrecognised_format_string():
    # Silently ignoring this would disable the constraint without saying so.
    with pytest.raises(ValueError):
        _response_format("yaml")


def test_anthropic_format_mapping():
    assert AnthropicProvider._output_config(None) is None
    oc = AnthropicProvider._output_config(RAW)
    assert oc["format"]["type"] == "json_schema"
    assert oc["format"]["schema"]["additionalProperties"] is False


def test_anthropic_rejects_json_mode_rather_than_downgrading():
    # Anthropic has no free JSON mode. Accepting "json" here would hand back
    # unconstrained output while the config claimed a constraint.
    with pytest.raises(ValueError):
        AnthropicProvider._output_config("json")
