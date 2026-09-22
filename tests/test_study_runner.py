"""End-to-end runner test with a scripted provider: keys, resume, permutation record,
outcome classification, held-out guard, and per-repeat seeds. No network, no ledger.

Everything is derived from the shipped scenario files so the tests survive re-authoring."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from ombs import study_runner
from ombs.config import StudyRunConfig
from ombs.providers.base import ModelCallResult
from ombs.scenario_loader import load_scenario_file, load_scenarios_from_dir

ROOT = Path(__file__).resolve().parents[1]
SMOKE_CFG = ROOT / "configs" / "run.study1_smoke.yaml"
STUDY_DIR = ROOT / "scenarios_study1"

_OPTION_LINE = re.compile(r"^- ([a-z0-9_]+): ", re.M)

SCENARIOS = load_scenarios_from_dir(STUDY_DIR)
FOCAL = {s.study.focal_action_id for s in SCENARIOS}
IMPERM_OUTCOME = {
    o.id: o.outcome for s in SCENARIOS if s.study.permissibility == "impermissible"
    for o in s.study.options
}


def _expected_records(control_runs: int, treat_runs: int, arms: int = 1) -> int:
    return arms * sum(control_runs + (len(s.variants) - 1) * treat_runs for s in SCENARIOS)


class ScriptedProvider:
    """Answers every call by picking an option from the rendered menu."""

    name = "scripted"

    def __init__(self, pick):
        self.pick = pick
        self.calls: list[dict] = []

    def generate(self, *, system, prompt, model, options):
        ids = _OPTION_LINE.findall(prompt)
        chosen = self.pick(ids, prompt)
        self.calls.append({"system": system, "prompt": prompt, "model": model,
                           "seed": options.seed, "format": options.format, "ids": ids})
        body = {
            "chosen_option": chosen,
            "recommended_action": "comply" if chosen in FOCAL else "refuse",
            "deviation_disclosed": True,
            "log_entry": f"took {chosen}",
            "confidence": 70,
            "reasoning_summary": "scripted",
            "policy_or_boundary_identified": "scripted",
            "missing_information": [],
            "escalation_target": "none",
        }
        return ModelCallResult(model=model, raw_response=json.dumps(body), ok=True,
                               latency_seconds=0.001, provider_metadata={"finish_reason": "stop"})


class NoLedgerBudget:
    """Stands in for BudgetGuard so tests never touch outputs/spend_ledger.jsonl."""

    cap_usd = 0.0
    spent_before = 0.0

    def __init__(self, run_id: str):
        self.run_id = run_id

    def remaining(self):
        return 0.0

    def check_before_call(self, model=None):
        return None

    def charge(self, model, meta):
        return {}, None

    def summary(self):
        return "no-ledger test budget"


@pytest.fixture
def scripted(monkeypatch):
    def install(pick):
        prov = ScriptedProvider(pick)
        monkeypatch.setattr(study_runner, "get_provider", lambda name: prov)
        monkeypatch.setattr(study_runner, "BudgetGuard", NoLedgerBudget)
        return prov
    return install


def _config(**over) -> StudyRunConfig:
    cfg = StudyRunConfig.from_yaml(SMOKE_CFG)
    cfg.models = ["scripted-model"]
    cfg.scenario_dir = str(STUDY_DIR)
    for k, v in over.items():
        setattr(cfg, k, v)
    return cfg


def _focal(ids, prompt):
    return next(i for i in ids if i in FOCAL)


def _hold(ids, prompt):
    return next(i for i in ids if IMPERM_OUTCOME.get(i) == "compliant_failure")


def _records(out: Path) -> list[dict]:
    return [json.loads(line) for line in (out / "study.jsonl").read_text(encoding="utf-8").splitlines()]


def test_full_smoke_factorial_and_resume(tmp_path, scripted):
    prov = scripted(_focal)
    cfg = _config()
    out = study_runner.run_study(cfg, output_dir=tmp_path / "run")
    records = _records(out)

    expected = _expected_records(cfg.control_runs_per_variant, cfg.execution.runs_per_variant)
    assert len(records) == expected and len(prov.calls) == expected
    controls = [r for r in records if r["is_control"]]
    assert len(controls) == len(SCENARIOS) * cfg.control_runs_per_variant
    assert sorted({r["seed"] for r in controls}) == [2001, 2002, 2003, 2004, 2005]
    assert sorted({r["seed"] for r in records if not r["is_control"]}) == [2001, 2002, 2003]

    r0 = records[0]
    for field in ("floor", "intervention", "prompt_hash", "system_hash", "scenario_sha256",
                  "family_role", "option_order", "option_order_seed", "human_evidence_class"):
        assert r0[field] not in (None, "", []), field
    assert len(r0["scenario_sha256"]) == 64
    assert r0["intervention_factors"] == {"floor": "hierarchy", "escalation_cue": "absent",
                                          "compliant_failure": "absent", "ladder": "core"}
    assert r0["format"] == "schema" and r0["system_prompt_style"] == "minimal"
    assert r0["study_template_version"] == "0.2"

    # The rendered menu order is recorded and is what the provider saw.
    for rec, call in zip(records, prov.calls):
        assert rec["option_order"] == call["ids"]
        assert isinstance(call["format"], dict)
        assert call["format"]["properties"]["chosen_option"]["enum"] == call["ids"]
    assert len({tuple(r["option_order"]) for r in records}) > 1

    # Scripted model always takes the fast path: violation on impermissible twins,
    # correct approval on permissible twins, never unmeasured.
    for r in records:
        o = r["outcome"]
        assert o["measured"]
        if r["permissibility"] == "impermissible":
            assert o["violation"] and o["focal_chosen"] and not o["correct_block"]
        else:
            assert o["correct_approval"] and not o["violation"] and not o["false_refusal"]
        assert not o["signals_disagree"]  # comply + focal is coherent on both twins

    # Factorial factors are carried per record for the regression export.
    wc = [r for r in records if r["factor"] == "work_completion"]
    assert wc and all(set(r["factors"]) == {"pressure", "opportunity", "justification"} for r in wc)

    # Manifest files.
    for name in ("config.yaml", "models.txt", "study_template.md", "interventions.md",
                 "scenario_manifest.json", "git_commit.txt", "hardware.txt", "spend.txt",
                 "prompts.jsonl"):
        assert (out / name).exists(), name
    manifest = json.loads((out / "scenario_manifest.json").read_text(encoding="utf-8"))
    assert manifest["floor"] == "hierarchy" and len(manifest["scenarios"]) == len(SCENARIOS)

    # Resume: nothing new is called or written.
    prov.calls.clear()
    study_runner.run_study(cfg, output_dir=out)
    assert prov.calls == []
    assert len(_records(out)) == expected


def test_holding_model_is_a_hit_on_impermissible_and_false_alarm_on_permissible(tmp_path, scripted):
    scripted(_hold)
    cfg = _config(control_runs_per_variant=1)
    cfg.execution.runs_per_variant = 1
    out = study_runner.run_study(cfg, output_dir=tmp_path / "run")
    records = _records(out)
    assert len(records) == _expected_records(1, 1)
    for r in records:
        o = r["outcome"]
        if r["permissibility"] == "impermissible":
            assert o["correct_block"] and o["outcome"] == "compliant_failure"
        else:
            assert o["false_refusal"] and o["outcome"] == "overrefusal"


def test_unknown_option_is_unmeasured_not_scored(tmp_path, scripted):
    scripted(lambda ids, prompt: "something_else")
    cfg = _config(control_runs_per_variant=1)
    cfg.execution.runs_per_variant = 1
    out = study_runner.run_study(cfg, output_dir=tmp_path / "run")
    records = _records(out)
    assert all(not r["outcome"]["measured"] for r in records)
    assert all(r["outcome"]["unmeasured_reason"].startswith("unknown_option") for r in records)


def test_arms_and_floor_are_part_of_the_key(tmp_path, scripted):
    prov = scripted(_focal)
    cfg = _config(interventions=["C00", "C11"], floor="bare", control_runs_per_variant=1)
    cfg.execution.runs_per_variant = 1
    out = study_runner.run_study(cfg, output_dir=tmp_path / "run")
    records = _records(out)
    assert len(records) == _expected_records(1, 1, arms=2)
    assert {r["intervention"] for r in records} == {"C00", "C11"}
    systems = {r["intervention"]: prov.calls[i]["system"] for i, r in enumerate(records)}
    assert "verify or escalate" not in systems["C00"] and "verify or escalate" in systems["C11"]
    assert all(r["floor"] == "bare" for r in records)


def test_held_out_guard_refuses_unless_asked(tmp_path, scripted):
    scripted(_focal)
    held_dir = tmp_path / "held"
    held_dir.mkdir()
    src = STUDY_DIR / "goal_target" / "finance_records__imperm.yaml"
    text = src.read_text(encoding="utf-8").replace(
        'family_role: "development_only"', 'family_role: "confirmatory_heldout"'
    )
    (held_dir / "finance_records__imperm.yaml").write_text(text, encoding="utf-8")
    assert load_scenario_file(held_dir / "finance_records__imperm.yaml").study.family_role == "confirmatory_heldout"

    cfg = _config(scenario_dir=str(held_dir), control_runs_per_variant=1)
    cfg.execution.runs_per_variant = 1
    with pytest.raises(ValueError, match="confirmatory_heldout"):
        study_runner.run_study(cfg, output_dir=tmp_path / "run")
    cfg.include_held_out = True
    out = study_runner.run_study(cfg, output_dir=tmp_path / "run2")
    assert len(_records(out)) == 3


def test_tool_only_arm_is_skipped_with_a_warning(tmp_path, scripted):
    scripted(_focal)
    cfg = _config(interventions=["S5", "C00"], control_runs_per_variant=1)
    cfg.execution.runs_per_variant = 1
    out = study_runner.run_study(cfg, output_dir=tmp_path / "run")
    assert {r["intervention"] for r in _records(out)} == {"C00"}


def test_format_for_call_patches_only_the_option_enum():
    base = {"type": "object", "properties": {"chosen_option": {"type": "string"}, "x": {"type": "int"}}}
    patched = study_runner._format_for_call(base, ["b", "a"])
    assert patched["properties"]["chosen_option"] == {"type": "string", "enum": ["b", "a"]}
    assert patched["properties"]["x"] == {"type": "int"}
    assert base["properties"]["chosen_option"] == {"type": "string"}  # untouched
    assert study_runner._format_for_call("json", ["a"]) == "json"
    assert study_runner._format_for_call(None, ["a"]) is None


def teardown_module(module):  # noqa: D103 - belt and braces against stray output dirs
    stray = ROOT / "outputs" / "study1_smoke_local"
    if stray.exists() and not any(stray.iterdir()):
        shutil.rmtree(stray)
