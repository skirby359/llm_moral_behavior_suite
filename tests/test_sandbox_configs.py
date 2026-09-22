"""Guards on the sandbox run configs themselves.

The scenario directory holds every family and the loader walks it recursively, so a config
that selects by directory alone widens silently the moment a second family lands -- including
re-running a frozen one. These tests make that class of accident impossible to commit.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ombs.config import SandboxRunConfig
from ombs.utils.budget import BILLING_PROVIDERS, PRICING
from ombs.sandbox_runner import frozen_families, select_sandbox_scenarios
from ombs.scenario_loader import load_sandbox_scenarios_from_dir

ROOT = Path(__file__).resolve().parents[1]
SCEN_DIR = ROOT / "scenarios_sandbox"
CONFIGS = sorted(ROOT.glob("configs/**/run.sandbox*.yaml"))
# Every family a config may pin: the development directory and, from Wave 6, the held-out one.
# Ids are unique across both (the loader rejects duplicates within a directory; the test below
# asserts it across them), so one map serves every config whatever its scenario_dir.
BY_ID = {s.id: s for s in load_sandbox_scenarios_from_dir(SCEN_DIR)}
_HELD_DIR = ROOT / "scenarios_sandbox_heldout"
if _HELD_DIR.exists():
    for _s in load_sandbox_scenarios_from_dir(_HELD_DIR):
        assert _s.id not in BY_ID, f"{_s.id} exists in both the development and held-out directories"
        BY_ID[_s.id] = _s


def _cfgs():
    return [(p, SandboxRunConfig.from_yaml(p)) for p in CONFIGS]


def test_there_are_sandbox_configs():
    assert CONFIGS, "no configs/**/run.sandbox*.yaml found"


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.stem)
def test_every_sandbox_config_pins_resolvable_scenario_ids(path):
    cfg = SandboxRunConfig.from_yaml(path)
    assert cfg.scenario_ids, f"{path.name} does not pin scenario_ids"
    unknown = [i for i in cfg.scenario_ids if i not in BY_ID]
    assert not unknown, f"{path.name} pins unknown ids {unknown}"


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.stem)
def test_one_config_one_family(path):
    cfg = SandboxRunConfig.from_yaml(path)
    families = {BY_ID[i].family for i in cfg.scenario_ids or []}
    assert len(families) == 1, f"{path.name} spans {sorted(families)}"


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.stem)
def test_no_config_overrides_the_technical_step_cap(path):
    # The cap is a property of the authored scenario, so "cap 16 for the new family only" is
    # structurally safe. A run-global override would silently re-cap every family in the run.
    assert SandboxRunConfig.from_yaml(path).technical_step_cap is None, (
        f"{path.name} overrides technical_step_cap; set it in the scenario YAML instead"
    )


def test_frozen_families_are_registered_with_the_hash_they_were_frozen_at():
    """The registry pins materials. `may_run` is the separate question of whether the family's
    pre-registered sampling is still open; a family can be hash-frozen and still running."""
    registry = frozen_families(SCEN_DIR)
    assert registry, "frozen_families.json lists no families"
    for family, entry in registry.items():
        scenario = next((s for s in BY_ID.values() if s.family == family), None)
        assert scenario is not None, f"{family} is registered as frozen but has no scenario file"
        assert scenario.source_sha256 == entry["scenario_sha256"], (
            f"{family} has been edited since it was frozen at {entry['frozen_at_commit']}"
        )
        assert isinstance(entry["may_run"], bool), f"{family}: may_run must be an explicit bool"
        assert entry.get("reason") and entry.get("frozen_on"), family
    assert any(e["may_run"] is False for e in registry.values()), (
        "no family is closed to sampling; the guard below would test nothing"
    )


def test_framing_bank_is_frozen_with_its_committed_hash():
    """A support bank is pinned by bytes exactly as a family is, so a preregistered study cannot
    re-word its manipulation after seeing a result. verify_sandbox.py check I asserts the same."""
    from ombs.utils.hashing import sha256_bytes

    registry = json.loads((SCEN_DIR / "frozen_families.json").read_text(encoding="utf-8"))
    banks = registry.get("banks") or {}
    assert banks, "no banks registered in frozen_families.json"
    for name, entry in banks.items():
        path = SCEN_DIR / entry["file"]
        assert path.exists(), f"registered bank {name} has no file {entry['file']}"
        assert sha256_bytes(path.read_bytes()) == entry["sha256"], (
            f"{entry['file']} has been edited since it was frozen on {entry['frozen_on']}"
        )
        assert entry.get("reason") and entry.get("frozen_on"), name


def test_a_frozen_family_cannot_be_selected_without_the_explicit_flag():
    frozen = frozen_families(SCEN_DIR)
    family = next(f for f, e in frozen.items() if e["may_run"] is False)
    scenario_id = next(s.id for s in BY_ID.values() if s.family == family)
    cfg = SandboxRunConfig(run_id="t", scenario_dir=str(SCEN_DIR), scenario_ids=[scenario_id])
    with pytest.raises(ValueError, match="frozen"):
        select_sandbox_scenarios(cfg)
    assert [s.id for s in select_sandbox_scenarios(cfg, allow_frozen=True)] == [scenario_id]


def test_an_unpinned_sandbox_run_is_refused():
    cfg = SandboxRunConfig(run_id="t", scenario_dir=str(SCEN_DIR))
    with pytest.raises(ValueError, match="must pin scenario_ids"):
        select_sandbox_scenarios(cfg)


def test_frozen_family_configs_pin_only_the_frozen_id():
    closed = {f for f, e in frozen_families(SCEN_DIR).items() if e["may_run"] is False}
    for path, cfg in _cfgs():
        families = {BY_ID[i].family for i in cfg.scenario_ids or []}
        if families & closed:
            assert families <= closed, f"{path.name} mixes a closed family with a live one"


def test_the_registry_is_valid_json_with_a_note():
    data = json.loads((SCEN_DIR / "frozen_families.json").read_text(encoding="utf-8"))
    assert data.get("_note") and "families" in data
#: Steps that were conditional in Family 2's plan (PRERUN_FAMILY2.md), matched as a substring of
#: the config stem so one cannot be added without its gate. These names are conditional only for
#: the batch-release family; the Wave 5 bridge families run a defer arm unconditionally as a
#: pre-registered terminal-architecture factor (PREREG_WAVE5_BRIDGE.md), so the check below is
#: scoped to the family that defined them as gated.
GATED_STEPS = ("ext_stuck", "intervention", "placebo", "incidental", "defer")
GATED_FAMILY = "sandbox_batch_release"


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.stem)
def test_live_family_configs_are_native_only(path):
    """Native by default: Wave 3 Phase D found no between-arm transport difference and the
    advisor asked that the spend stop. Wave 5 reopened it after an audit found the base rates
    were not equal (Family 1 gpt-5.5 5/16 json_schema vs 4/36 native). A json_schema config is
    allowed only if its header records that reversal and the PI approval, and points at the
    pre-run amendment -- the same discipline the gated configs follow."""
    cfg = SandboxRunConfig.from_yaml(path)
    closed = {f for f, e in frozen_families(SCEN_DIR).items() if e["may_run"] is False}
    families = {BY_ID[i].family for i in cfg.scenario_ids or []}
    if families & closed:
        return  # a closed family's committed configs record what was already run
    if cfg.tool_transport == "native":
        return
    head = path.read_text(encoding="utf-8").split("run_id:")[0]
    assert "REVERSES the standing instruction" in head and "PRERUN_FAMILY2.md" in head, (
        f"{path.name} samples {cfg.tool_transport} without documenting the reversal in its header"
    )


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.stem)
def test_conditional_configs_carry_their_gate_in_the_header(path):
    cfg = SandboxRunConfig.from_yaml(path)
    families = {BY_ID[i].family for i in cfg.scenario_ids or []}
    if families & {f for f, e in frozen_families(SCEN_DIR).items() if e["may_run"] is False}:
        return  # a closed family's steps have already run; a gate written now would be fiction
    if cfg.provider == "ollama":
        return  # the gate exists to stop spending; a local run spends nothing
    if GATED_FAMILY not in families:
        return  # these step names are conditional only for the family that defined them so
    if not any(step in path.stem for step in GATED_STEPS):
        return
    head = path.read_text(encoding="utf-8").split("run_id:")[0]
    assert "NOT TO BE RUN" in head, f"{path.name} is a conditional step with no gate in its header"


def test_the_second_family_is_not_registered_frozen():
    """A live family must stay runnable without --allow-frozen, or the wave cannot proceed."""
    cfg = SandboxRunConfig(run_id="t", scenario_dir=str(SCEN_DIR), scenario_ids=["sb_batch_release"])
    assert [s.id for s in select_sandbox_scenarios(cfg)] == ["sb_batch_release"]


def test_a_config_spanning_two_families_is_refused_without_the_flag():
    # development families only: the held-out family lives in another directory
    ids = sorted(i for i, s in BY_ID.items() if s.family_role != "confirmatory_heldout")
    assert len(ids) >= 2, "this guard needs two families"
    cfg = SandboxRunConfig(run_id="t", scenario_dir=str(SCEN_DIR), scenario_ids=ids)
    with pytest.raises(ValueError, match="famil"):
        select_sandbox_scenarios(cfg, allow_frozen=True)
    cfg.allow_multi_family = True
    assert len(select_sandbox_scenarios(cfg, allow_frozen=True)) == len(ids)


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.stem)
def test_billing_configs_name_only_priced_models(path):
    """The cap exempts unpriced models, so a frontier config naming one would spend invisibly.
    The runner refuses it at run time; this refuses it at commit time."""
    cfg = SandboxRunConfig.from_yaml(path)
    if cfg.provider.lower() not in BILLING_PROVIDERS:
        return
    unpriced = [m for m in cfg.models if m not in PRICING]
    assert not unpriced, f"{path.name} names unpriced model(s) {unpriced} on a billing provider"


GEMINI_CONFIGS = sorted(ROOT.glob("configs/run.sandbox5_*_gemini.yaml"))


@pytest.mark.parametrize("path", GEMINI_CONFIGS, ids=lambda p: p.stem)
def test_gemini_configs_are_pinned_priced_preregistered_and_gated(path):
    """The third-vendor arms (PREREG_THIRD_VENDOR_GEMINI.md): the frozen contract family only, the
    google provider, a priced model id, the preregistration named, and an approval or gate phrase
    in the header; the conditional arms say so."""
    cfg = SandboxRunConfig.from_yaml(path)
    assert cfg.provider == "google", path.name
    assert cfg.scenario_ids == ["sb_contract_execution"], path.name
    assert all(m in PRICING for m in cfg.models), path.name
    assert cfg.tool_transport == "native", path.name
    head = path.read_text(encoding="utf-8").split("run_id:")[0]
    assert "PREREG_THIRD_VENDOR_GEMINI.md" in head, path.name
    assert "PI approved" in head or "NOT TO BE RUN" in head, path.name
    if any(arm in path.stem for arm in ("compliant", "authority")):
        assert "CONDITIONAL" in head and ">= 3/20" in head, f"{path.name} is a conditional arm without its gate"
