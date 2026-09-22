"""Compliant-failure wording-robustness study: the framing_variant axis, the paraphrase bank,
and the guards that keep it from touching any earlier run.

Preregistered in scenarios_sandbox/PREREG_WORDING_ROBUSTNESS.md; mechanics per the design note's
approach (b). The invariants pinned here are the ones the freeze rule depends on: a canonical cell
is byte-identical to a pre-bank cell, a paraphrase run cannot start unless the bank is pinned to the
family, and the generic pipeline refuses to pool paraphrase arms.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import pathlib

import pytest

from ombs.analysis.sandbox import _flat
from ombs.config import SandboxRunConfig
from ombs.sandbox_runner import (
    cells_from_config,
    framing_addendum_for,
    resolve_framing_bank,
    select_sandbox_scenarios,
)
from ombs.schemas import SandboxCell

ROOT = pathlib.Path(__file__).resolve().parents[1]
GPT_CONFIG = ROOT / "configs" / "run.sandbox_wording_contract_compliant_gpt.yaml"


def _config() -> SandboxRunConfig:
    return SandboxRunConfig.from_yaml(GPT_CONFIG)


# --- the axis leaves every earlier run byte-identical ---------------------------------------

def test_canonical_cell_label_and_key_unchanged():
    canon = SandboxCell(solvability="stuck", task_framing="compliant_failure")
    assert canon.framing_variant == "canonical"
    assert canon.label() == "stuckxadjacentxvisible_writablexlimit_offxcompliant_failurexdefer_offxnative"
    assert len(canon.key()) == 7  # no eighth element for canonical


def test_non_canonical_cell_appends_only_when_set():
    cell = SandboxCell(solvability="stuck", task_framing="compliant_failure", framing_variant="para1")
    assert cell.label().endswith("xnativexframing_para1")
    assert cell.key()[-1] == "para1" and len(cell.key()) == 8


# --- cells_from_config -----------------------------------------------------------------------

def test_cells_from_config_one_cell_per_variant():
    cells = cells_from_config(_config())
    assert [c.framing_variant for c in cells] == ["para1", "para2", "para3"]
    assert len({c.label() for c in cells}) == 3


def test_non_canonical_variant_skipped_for_non_compliant_framing():
    cfg = _config()
    cfg.task_framing = ["baseline", "compliant_failure"]
    cfg.framing_variant = ["canonical", "para1"]
    labels = {c.label() for c in cells_from_config(cfg)}
    # baseline x para1 is meaningless and must not be emitted
    assert not any("baseline" in lbl and "framing_para1" in lbl for lbl in labels)
    assert any(lbl.endswith("compliant_failurexdefer_offxnativexframing_para1") for lbl in labels)


# --- resolve_framing_bank: happy path and every refusal --------------------------------------

def test_resolve_bank_renders_the_three_paraphrases():
    cfg = _config()
    scs = select_sandbox_scenarios(cfg)
    bank = resolve_framing_bank(cfg, scs, cfg.scenario_dir)
    assert sorted(bank["rendered"]) == ["para1", "para2", "para3"]
    assert bank["sha256"] and bank["canonical_sha256"]
    # each rendered sentence is what the cell substitutes in
    for variant, entry in bank["rendered"].items():
        cell = SandboxCell(solvability="stuck", task_framing="compliant_failure", framing_variant=variant)
        assert framing_addendum_for(cell, scs[0], bank) == entry["text"]


def test_canonical_only_needs_no_bank():
    cfg = _config()
    cfg.framing_variant = ["canonical"]
    scs = select_sandbox_scenarios(cfg)
    assert resolve_framing_bank(cfg, scs, cfg.scenario_dir) is None


def test_bank_refused_when_framing_not_exactly_compliant_failure():
    cfg = _config()
    cfg.task_framing = ["baseline", "compliant_failure"]
    scs = select_sandbox_scenarios(cfg)
    with pytest.raises(ValueError, match="only valid with task_framing"):
        resolve_framing_bank(cfg, scs, cfg.scenario_dir)


def test_bank_refused_for_unknown_variant():
    cfg = _config()
    cfg.framing_variant = ["para9"]
    scs = select_sandbox_scenarios(cfg)
    with pytest.raises(ValueError, match="not found"):
        resolve_framing_bank(cfg, scs, cfg.scenario_dir)


def test_bank_refused_when_canonical_does_not_match_family():
    cfg = _config()
    scs = select_sandbox_scenarios(cfg)
    tampered = copy.deepcopy(scs[0])
    tampered.task_compliant_failure_addendum = "some other sentence entirely"
    with pytest.raises(ValueError, match="does not match|not pinned"):
        resolve_framing_bank(cfg, [tampered], cfg.scenario_dir)


# --- framing_addendum_for falls back to the family for canonical / authority -----------------

def test_addendum_for_canonical_and_authority_use_the_family():
    scs = select_sandbox_scenarios(_config())
    sc = scs[0]
    canon = SandboxCell(solvability="stuck", task_framing="compliant_failure")
    auth = SandboxCell(solvability="stuck", task_framing="authority_salience")
    assert framing_addendum_for(canon, sc, None) == sc.task_compliant_failure_addendum
    assert framing_addendum_for(auth, sc, None) == sc.task_authority_salience_addendum


# --- the generic pipeline refuses to pool paraphrase arms ------------------------------------

def test_generic_flat_refuses_non_canonical_records():
    rec = {"complete": True, "cell": {"solvability": "stuck", "task_framing": "compliant_failure",
                                       "framing_variant": "para1"}, "outcome": {"measured": True}}
    with pytest.raises(ValueError, match="framing_variant"):
        _flat([rec])


def test_generic_flat_accepts_canonical_and_pre_bank_records():
    # a pre-bank record has no framing_variant key at all
    rec = {"complete": True, "cell": {"solvability": "stuck", "task_framing": "baseline"},
           "outcome": {"measured": True}}
    assert _flat([rec])  # does not raise


# --- verify_sandbox check I passes on the committed bank -------------------------------------

def _load_verify_module():
    spec = importlib.util.spec_from_file_location(
        "verify_sandbox", ROOT / "scenarios_sandbox" / "verify_sandbox.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_check_i_passes_on_committed_bank():
    from ombs.scenario_loader import load_sandbox_scenarios_from_dir
    vs = _load_verify_module()
    scs = load_sandbox_scenarios_from_dir(ROOT / "scenarios_sandbox")
    files = [(None, s) for s in scs]
    rep = vs.Report()
    vs.check_framing_bank(files, rep)
    assert rep.failures == []


# --- wording_analysis: grouping and the decision helpers -------------------------------------

def _load_wording_module():
    spec = importlib.util.spec_from_file_location(
        "wording_analysis", ROOT / "scenarios_sandbox" / "wording_analysis.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_study(dir_: pathlib.Path, per_variant: dict[str, int], n: int = 10) -> None:
    """A study sandbox.jsonl: `per_variant` crossings out of n measured for each variant."""
    dir_.mkdir(parents=True, exist_ok=True)
    lines = []
    for variant, crossings in per_variant.items():
        for i in range(n):
            crossed = i < crossings
            lines.append({
                "complete": True,
                "cell": {"solvability": "stuck", "task_framing": "compliant_failure",
                         "framing_variant": variant},
                "outcome": {"measured": True, "any_boundary_crossing": crossed,
                            "crossing_routes": ["relaxed_check"] if crossed else []},
                "turns": [],
            })
    (dir_ / "sandbox.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")


def _write_committed(dir_: pathlib.Path, model: str, framing: str, k: int, n: int) -> None:
    dir_.mkdir(parents=True, exist_ok=True)
    header = ["model", "family", "solvability", "task_framing", "defer_available", "crossings", "n"]
    row = [model, "sandbox_contract_execution", "stuck", framing, "off", str(k), str(n)]
    (dir_ / "persistence.csv").write_text(",".join(header) + "\n" + ",".join(row) + "\n", encoding="utf-8")


def test_holm_adjusts_and_orders():
    wa = _load_wording_module()
    adj = wa.holm({"a": 0.01, "b": 0.04, "c": None})
    assert adj["a"] == pytest.approx(0.02)   # 2 * 0.01
    assert adj["b"] == pytest.approx(0.04)   # 1 * 0.04, monotone up from a
    assert adj["c"] is None


def test_verdict_arm_bands():
    wa = _load_wording_module()
    assert wa.verdict_arm(0, 10, 1e-6) == "suppressed"
    assert wa.verdict_arm(9, 10, 1.0).startswith("not suppressed")
    assert "grey" in wa.verdict_arm(6, 10, 0.5)
    assert wa.verdict_arm(0, 0, None) == "NOT SAMPLED"


def test_study_arm_groups_by_variant(tmp_path):
    wa = _load_wording_module()
    _write_study(tmp_path / "study", {"para1": 0, "para2": 9})
    a1 = wa.study_arm(tmp_path, "study", "para1")
    a2 = wa.study_arm(tmp_path, "study", "para2")
    assert (a1["measured"], a1["crossings"]) == (10, 0)
    assert (a2["measured"], a2["crossings"]) == (10, 9)
    assert a2["routes"]["relaxed_check"] == 9


def test_committed_matches_model_and_framing(tmp_path):
    wa = _load_wording_module()
    _write_committed(tmp_path / "base", "gpt-5.5", "baseline", 19, 20)
    assert wa.committed(tmp_path, "base", "gpt-5.5", "baseline") == (19, 20)
    assert wa.committed(tmp_path, "base", "other-model", "baseline") is None


def test_vendor_reading_incomplete_beats_exact_wording():
    wa = _load_wording_module()
    full = ["para1", "para2"]
    # every full paraphrase sampled and suppressed -> semantic policy
    assert wa.vendor_reading(["para1", "para2"], full, []) is True
    # a sampled full paraphrase not suppressed -> exact wording
    assert wa.vendor_reading(["para1", "para2"], full, ["para2"]) is False
    # a full paraphrase not sampled (quota) -> incomplete, NOT exact wording
    assert wa.vendor_reading(["para1"], full, []) is None
    assert wa.vendor_reading([], full, []) is None
