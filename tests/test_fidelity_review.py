"""Blinded fidelity review: blindness of the prompt, two-judge status logic, adjudication.

Counts are derived from the shipped scenario files so the tests survive re-authoring."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ombs import fidelity_review as fr
from ombs.providers.base import ModelCallResult
from ombs.scenario_loader import load_scenario_file, load_scenarios_from_dir

ROOT = Path(__file__).resolve().parents[1]
STUDY_DIR = ROOT / "scenarios_study1"
IMPERM = STUDY_DIR / "goal_target" / "finance_records__imperm.yaml"

FAMILIES = fr.families_to_review(load_scenarios_from_dir(STUDY_DIR))
N_PAIRS = sum(len(s.variants) - 1 for s in FAMILIES.values())


class JudgeStub:
    name = "stub"

    def __init__(self, clean: bool, telegraph: str | None = None):
        self.clean = clean
        self.telegraph = telegraph
        self.prompts: list[str] = []

    def generate(self, *, system, prompt, model, options):
        self.prompts.append(prompt)
        v = {
            "single_change": True,
            "change_description": "B adds one thing",
            "rule_unchanged": True,
            "telegraphs_expected_option": not self.clean,
            "telegraphed_option_id": self.telegraph if not self.clean else None,
            "other_pressure_introduced": False,
            "other_pressure_description": None,
            "explanation": "stub",
        }
        return ModelCallResult(model=model, raw_response=json.dumps(v), ok=True, latency_seconds=0.0)


class NoLedgerBudget:
    cap_usd = 0.0
    spent_before = 0.0

    def __init__(self, run_id):
        pass

    def remaining(self):
        return 0.0

    def check_before_call(self, model=None):
        return None

    def charge(self, model, meta):
        return {}, None

    def summary(self):
        return "stub"


def test_prompt_is_blind_to_metadata():
    sc = load_scenario_file(IMPERM)
    ctrl = sc.variant(sc.study.control_variant_id)
    p = fr.build_fidelity_prompt(sc, ctrl, sc.variant("near_miss"))
    for banned in ("goal_target", "near_miss", "do_best", "unsafe_action", "compliant_success",
                   "overrefusal", "impermissible", "LAB_EXPERIMENT", sc.study.manipulation.literature_tag,
                   "Halden"):  # scenario facts are withheld too
        assert banned not in p, banned
    assert "MESSAGE A (baseline)" in p and "MESSAGE B (variant)" in p
    assert "post_against_po7731" in p  # the option menu IS shown, so telegraphing can be judged
    assert sc.policy_context.strip() in p


def test_one_scenario_per_family_prefers_the_impermissible_twin():
    assert set(FAMILIES) == {s.study.family for s in load_scenarios_from_dir(STUDY_DIR)}
    assert all(s.study.permissibility == "impermissible" for s in FAMILIES.values())


def test_two_clean_judges_pass_and_one_dissenter_disagrees(tmp_path, monkeypatch):
    monkeypatch.setattr(fr, "BudgetGuard", NoLedgerBudget)
    a, b = JudgeStub(clean=True), JudgeStub(clean=False, telegraph="post_against_po7731")
    out = fr.run_fidelity_review(
        STUDY_DIR, judges=["p1:judge-a", "p2:judge-b"], out_dir=tmp_path / "fid",
        providers={"p1": a, "p2": b}, study_models=["judge-b"],
    )
    rows = [json.loads(x) for x in (out / "fidelity.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2 * N_PAIRS and len(a.prompts) == N_PAIRS and len(b.prompts) == N_PAIRS
    assert {r["scenario_id"] for r in rows} == {s.id for s in FAMILIES.values()}
    assert all(r["self_judge"] == (r["judge_model"] == "judge-b") for r in rows)
    status = fr.fidelity_status(out)
    assert len(status) == N_PAIRS and set(status.values()) == {fr.DISAGREE}
    summary = (out / "fidelity_summary.md").read_text(encoding="utf-8")
    assert "DISAGREE" in summary and "telegraphs post_against_po7731" in summary

    # Human adjudication resolves the pair; unresolved pairs stay DISAGREE.
    (out / "adjudications.yaml").write_text(
        "- {family: goal_target_finance_records, level: near_miss, decision: pass, by: SK, "
        "note: the target statement is the manipulation}\n", encoding="utf-8",
    )
    status = fr.fidelity_status(out)
    assert status[("goal_target_finance_records", "near_miss")].startswith("PASS (adjudicated by SK")
    assert status[("goal_target_finance_records", "target")] == fr.DISAGREE

    # Resume: nothing re-asked.
    a.prompts.clear()
    b.prompts.clear()
    fr.run_fidelity_review(STUDY_DIR, judges=["p1:judge-a", "p2:judge-b"], out_dir=out,
                           providers={"p1": a, "p2": b})
    assert a.prompts == [] and b.prompts == []


def test_both_judges_flagging_is_a_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(fr, "BudgetGuard", NoLedgerBudget)
    out = fr.run_fidelity_review(
        STUDY_DIR, judges=["p1:x", "p2:y"], out_dir=tmp_path / "fid",
        providers={"p1": JudgeStub(False, "post_against_po7731"), "p2": JudgeStub(False, "drop_to_team_drive")},
    )
    assert set(fr.fidelity_status(out).values()) == {fr.FAIL}


def test_bad_adjudication_decision_is_rejected(tmp_path):
    (tmp_path / "adjudications.yaml").write_text(
        "- {family: f, level: l, decision: maybe}\n", encoding="utf-8"
    )
    with pytest.raises(ValueError):
        fr.load_adjudications(tmp_path)


def test_judge_spec_parsing():
    assert fr.parse_judge("anthropic:claude-opus-5") == ("anthropic", "claude-opus-5")
    with pytest.raises(ValueError):
        fr.parse_judge("claude-opus-5")
