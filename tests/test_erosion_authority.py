"""Continuity condition ``authority_transfer``: schema, plan, render, runner, analysis.

The condition changes only the message block of the abrupt opening: same workspace, same
tools, same item and action, a named senior figure who is not the standard's authorizer
and who takes responsibility. These tests pin that claim mechanically.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from ombs import erosion_runner
from ombs.analysis import erosion as analysis
from ombs.design_controls import LEAK, first_hit
from ombs.erosion_env import ErosionEnvironment
from ombs.prompt_builder import build_erosion_opening
from ombs.scenario_loader import load_erosion_scenarios_from_dir
from ombs.schemas import ErosionScenario

try:  # tests/ is a plain directory (prepend import mode)
    from test_erosion_runner import _cfg, _records, intended_then_hold, scripted  # noqa: F401
except ImportError:  # pragma: no cover -- tests/ imported as a package
    from tests.test_erosion_runner import _cfg, _records, intended_then_hold, scripted  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
SCEN_DIR = ROOT / "scenarios_erosion"
ALL = {s.id: s for s in load_erosion_scenarios_from_dir(SCEN_DIR)}
SC = ALL["er_erosion_procurement_conflict"]
RAW = yaml.safe_load((SCEN_DIR / "procurement_conflict.yaml").read_text(encoding="utf-8"))


def _mut(**changes) -> dict:
    d = copy.deepcopy(RAW)
    d.update(changes)
    return d


def test_every_development_family_carries_the_continuity_final():
    for sc in ALL.values():
        fa = sc.final_request_authority
        assert sc.authority_name and fa, sc.id
        assert sc.authority_name.lower() not in (sc.requester_name.lower(), sc.colleague_name.lower())
        assert first_hit(LEAK["authority"], fa), sc.id
        assert first_hit(LEAK["responsibility"], fa), sc.id
        assert not first_hit(LEAK["false_history"], fa), sc.id
        assert sc.final_focal.item() in fa, sc.id
        assert fa.strip() != sc.final_request.strip()


def test_continuity_fields_are_validated_together_and_distinct():
    with pytest.raises(ValidationError):
        ErosionScenario.model_validate(_mut(authority_name=None))
    with pytest.raises(ValidationError):
        ErosionScenario.model_validate(_mut(final_request_authority=None))
    with pytest.raises(ValidationError):
        ErosionScenario.model_validate(_mut(authority_name=RAW["requester_name"]))
    with pytest.raises(ValidationError):
        ErosionScenario.model_validate(_mut(authority_name=RAW["colleague_name"].upper()))
    ok = ErosionScenario.model_validate(_mut(authority_name=None, final_request_authority=None))
    assert ok.authority_name is None and ok.final_request_authority is None


def test_plan_is_one_final_from_the_initial_workspace_and_only_the_message_differs():
    assert erosion_runner._turn_plan(SC, "authority_transfer") == [("final", SC.final_request_authority, None)]
    assert (erosion_runner._seed_env(SC, "authority_transfer").canonical_state_hash()
            == erosion_runner._seed_env(SC, "abrupt").canonical_state_hash())
    env = ErosionEnvironment(SC)
    kw = dict(role=SC.role, policy_context=SC.policy_context, task_goal=SC.task_goal,
              state_render=env.render_state(), available_tools=list(SC.available_tools))
    abrupt = build_erosion_opening(request=SC.final_request, requester_name=SC.requester_name, **kw)
    auth = build_erosion_opening(request=SC.final_request_authority, requester_name=SC.authority_name, **kw)
    assert abrupt.split("Message from", 1)[0] == auth.split("Message from", 1)[0]
    assert f"Message from {SC.authority_name}:" in auth
    assert SC.colleague_name.lower() not in auth.lower()
    assert "authority_transfer" not in auth.lower()


def test_runner_and_analysis_handle_the_continuity_condition(tmp_path, scripted):
    scripted(intended_then_hold)
    cfg = _cfg(conditions=["abrupt", "authority_transfer"])
    cfg.execution.runs_per_variant = 2
    out = erosion_runner.run_erosion(cfg, output_dir=tmp_path / "run")
    recs = _records(out)
    by = {c: [r for r in recs if r["condition"] == c] for c in ("abrupt", "authority_transfer")}
    assert len(by["abrupt"]) == 2 and len(by["authority_transfer"]) == 2 and len(recs) == 4
    for r in by["authority_transfer"]:
        o = r["outcome"]
        assert r["n_turns"] == 1 and o["final_measured"] and o["final_violation"] is False and o["path_intact"]
        assert o["final_compliant_alternative"]
        assert f"Message from {SC.authority_name}:" in r["turns"][0]["user_message"]
    # Both arms start from the initial workspace.
    assert len({r["outcome"]["canonical_state_hash_before_final"] for r in recs}) == 1
    # Tables carry only the conditions that ran; the contrast is contemporaneous.
    fv = analysis.final_violation_table(recs)
    assert {r["condition"] for r in fv} == {"abrupt", "authority_transfer"}
    pooled = [r for r in analysis.contrast_table(recs) if r["family"] == "ALL"][0]
    assert pooled["delta_authority"] == 0.0 and pooled["delta_authority_n"] == "2/2"
    assert pooled["delta_erosion"] is None
    analysis.build_erosion_report(out / "erosion.jsonl", out)
    assert "authority=0.0" in analysis.erosion_summary_text(out / "erosion.jsonl")
    assert SC.authority_name in (out / "scenario_manifest.json").read_text(encoding="utf-8")


def test_scenario_without_a_continuity_final_is_skipped_not_run(tmp_path, scripted):
    prov = scripted(intended_then_hold)
    stripped = tmp_path / "scen"
    stripped.mkdir()
    raw = _mut(authority_name=None, final_request_authority=None)
    (stripped / "procurement_conflict.yaml").write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cfg = _cfg(scenario_dir=str(stripped), conditions=["authority_transfer"])
    cfg.execution.runs_per_variant = 1
    out = erosion_runner.run_erosion(cfg, output_dir=tmp_path / "run")
    assert prov.calls == [] and not (out / "erosion.jsonl").exists()
