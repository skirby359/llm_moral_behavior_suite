"""The Wave 6 confirmatory held-out family: split hash, refusal without the flag, and the gate.

`scenarios_sandbox_heldout/procurement_award.yaml` is the family PREREG_WAVE6_CONFIRMATORY.md
fixes. Its SHA-256 is committed in `scenarios_sandbox/heldout_split.json`; these tests make the
three properties that give "held out" its meaning mechanical rather than asserted."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ombs.config import SandboxRunConfig
from ombs.sandbox_runner import select_sandbox_scenarios
from ombs.scenario_loader import load_sandbox_scenarios_from_dir

ROOT = Path(__file__).resolve().parents[1]
HELD_DIR = ROOT / "scenarios_sandbox_heldout"
SPLIT = ROOT / "scenarios_sandbox" / "heldout_split.json"
DEV = {s.family: s for s in load_sandbox_scenarios_from_dir(ROOT / "scenarios_sandbox")}
HELD = {s.id: s for s in load_sandbox_scenarios_from_dir(HELD_DIR)}


def test_the_held_out_family_is_registered_at_the_hash_on_disk():
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    assert split["files"], "heldout_split.json lists no files"
    for rel, sha in split["files"].items():
        path = ROOT / rel
        assert path.exists(), rel
        sc = next(s for s in HELD.values() if s.source_sha256 == sha) if any(
            s.source_sha256 == sha for s in HELD.values()) else None
        assert sc is not None, f"{rel} has been edited since its hash was committed to the split"
        assert sc.family_role == "confirmatory_heldout"


def test_the_held_out_family_is_a_fourth_domain_on_the_bridge_template():
    sc = HELD["sb_procurement_award"]
    assert sc.domain not in {s.domain for s in DEV.values()}, "the confirmatory domain was used in development"
    contract = DEV["sandbox_contract_execution"]
    # same template: same checker kind, same tools, same cap, same session limit, three routes
    assert sc.checker.kind == contract.checker.kind == "approval_gate"
    assert set(sc.available_tools) == set(contract.available_tools)
    assert sc.technical_step_cap == contract.technical_step_cap == 16
    assert sc.session_limit_actions == contract.session_limit_actions
    assert len(sc.shortcuts) == 3 and {s.id for s in sc.shortcuts} >= {"relax_check"}
    # byte-identical framing sentences, so the terminal arms are the same manipulation
    assert sc.task_compliant_failure_addendum == contract.task_compliant_failure_addendum
    assert sc.task_authority_salience_addendum == contract.task_authority_salience_addendum
    # terse rule, two named non-assistant ownerships, no worked precedent
    words = len(sc.rule_text.split())
    assert 35 <= words <= 55, words


def test_a_held_out_family_cannot_be_selected_without_the_flag():
    cfg = SandboxRunConfig(run_id="t", scenario_dir=str(HELD_DIR), scenario_ids=["sb_procurement_award"])
    with pytest.raises(ValueError, match="include_held_out"):
        select_sandbox_scenarios(cfg)
    cfg.include_held_out = True
    assert [s.id for s in select_sandbox_scenarios(cfg)] == ["sb_procurement_award"]


def test_every_wave6_config_sets_the_flag_and_pins_the_family():
    paths = sorted(ROOT.glob("configs/run.sandbox6_*.yaml"))
    assert paths, "no Wave 6 configs"
    for p in paths:
        cfg = SandboxRunConfig.from_yaml(p)
        assert cfg.include_held_out, p.name
        assert cfg.scenario_ids == ["sb_procurement_award"], p.name
        assert cfg.scenario_dir == "scenarios_sandbox_heldout", p.name
        assert cfg.tool_transport == "native", p.name
        head = p.read_text(encoding="utf-8").split("run_id:")[0]
        if any(arm in p.stem for arm in ("baseline", "compliant", "defer", "authority")):
            assert "NOT TO BE RUN" in head or "PI approved" in head, (
                f"{p.name} is a confirmatory/secondary arm with neither its gate nor its approval in the header")
