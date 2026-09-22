"""ErosionEnvironment: enforcement without exceptions, seeding, hashes, rendering, matching."""

from __future__ import annotations

from pathlib import Path

import pytest

from ombs.erosion_env import ErosionEnvironment
from ombs.scenario_loader import load_erosion_scenarios_from_dir
from ombs.schemas import CallMatch

ROOT = Path(__file__).resolve().parents[1]
SC = {s.id: s for s in load_erosion_scenarios_from_dir(ROOT / "scenarios_erosion")}["er_erosion_procurement_conflict"]


def fresh() -> ErosionEnvironment:
    return ErosionEnvironment(SC)


def test_unavailable_and_unknown_tools_are_recorded_not_raised():
    env = fresh()
    h = env.state_hash()
    e1 = env.execute("edit_record", {"record_id": "PR-2031", "field": "amount_gbp", "value": "1"})
    e2 = env.execute("frobnicate", {})
    assert e1["executed"] is False and e1["error"].startswith("tool_unavailable")
    assert e2["executed"] is False and e2["error"].startswith("unknown_tool")
    assert env.state_hash() == h and len(env.calls) == 2 and env.activity == []


def test_missing_args_and_unknown_record():
    env = fresh()
    assert env.execute("approve_item", {"item_id": ""})["error"] == "missing_args: item_id"
    assert env.execute("record_exception", {"item_id": "PR-2031"})["error"] == "missing_args: reason"
    assert env.execute("approve_item", {"item_id": "PR-9999"})["error"] == "unknown_record: PR-9999"
    assert env.records["PR-2031"]["status"] == "open"


def test_approve_hold_refer_escalate_change_status_and_log():
    env = fresh()
    assert env.execute("approve_item", {"item_id": "PR-2031", "note": "two quotes"})["executed"]
    assert env.records["PR-2031"]["status"] == "approved"
    env.execute("hold_item", {"item_id": "PR-2032", "note": "waiting"})
    env.execute("request_authorization", {"approver": "lead", "item_id": "PR-2033", "reason": "near limit"})
    env.execute("escalate", {"to": "lead", "item_id": "PR-2034", "reason": "one quote"})
    assert [r["status"] for r in (env.records[i] for i in ("PR-2032", "PR-2033", "PR-2034"))] == [
        "on_hold", "pending_authorization", "escalated"]
    assert [a["tool"] for a in env.activity] == ["approve_item", "hold_item", "request_authorization", "escalate"]
    assert env.execute("none", {})["result"] == "No action taken." and len(env.activity) == 4


def test_prior_replay_hashes_like_the_models_own_path():
    a = fresh()
    a.apply_prior(SC.effective_prior(), actor=SC.colleague_name)
    b = fresh()
    for s in SC.steps:
        b.execute(s.canonical_call.tool, s.canonical_call.args, actor="you", turn=1)
    assert a.canonical_state_hash() == b.canonical_state_hash()
    assert a.state_hash() != b.state_hash()  # actors differ in the full hash
    ra, rb = a.render_state(), b.render_state()
    assert SC.colleague_name in ra and "recorded by you" not in ra
    assert "recorded by you" in rb and SC.colleague_name not in rb


def test_prior_replay_error_is_an_authoring_bug():
    env = fresh()
    from ombs.schemas import PriorCall
    with pytest.raises(ValueError):
        env.apply_prior([PriorCall(tool="approve_item", arguments={"item_id": "PR-0000"})], actor="x")


def test_call_matches_is_exact_case_insensitive_and_ignores_extra_args():
    env = fresh()
    env.execute("approve_item", {"item_id": "pr-2035", "note": "batch"})
    rule = CallMatch(tool="approve_item", args={"item_id": "PR-2035"})
    assert env.matches(rule) and len(env.matches(rule)) == 1
    assert not env.matches(CallMatch(tool="approve_item", args={"item_id": "PR-2031"}))
    # prior-sourced calls never count
    env2 = fresh()
    env2.execute("approve_item", {"item_id": "PR-2035"}, actor="Priya", source="prior")
    assert env2.matches(rule) == []


def test_render_state_elides_oldest_activity_when_long():
    env = fresh()
    for i in range(40):
        env.execute("record_exception", {"item_id": "PR-2031", "reason": f"reason number {i} " + "x" * 60})
    text = env.render_state(max_chars=1500)
    assert len(text) <= 1500 + 80 and "earlier entries omitted" in text
    assert "reason number 39" in text and "reason number 0 " not in text


def test_edit_record_logs_before_and_after():
    env = ErosionEnvironment(SC)
    env.available_tools.add("edit_record")
    e = env.execute("edit_record", {"record_id": "PR-2031", "field": "amount_gbp", "value": "1900", "note": "corrected"})
    assert e["executed"] and env.records["PR-2031"]["fields"]["amount_gbp"] == "1900"
    assert env.activity[-1]["before"] == 1850
