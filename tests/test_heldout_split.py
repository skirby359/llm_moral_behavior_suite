"""The seeded held-out draw: fidelity gating, stratification, rewrite, hashes, immutability.

Fixtures copy the shipped scenario bank so the tests survive re-authoring."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

from ombs.scenario_loader import load_scenarios_from_dir

ROOT = Path(__file__).resolve().parents[1]
STUDY_DIR = ROOT / "scenarios_study1"

spec = importlib.util.spec_from_file_location("make_heldout_split", STUDY_DIR / "make_heldout_split.py")
mhs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mhs)

SCENARIOS = load_scenarios_from_dir(STUDY_DIR)
FAMILIES = {s.study.family: s.study.manipulation.factor for s in SCENARIOS}
ALL_PASS = {
    (s.study.family, v.level): True
    for s in SCENARIOS for v in s.variants if v.id != s.study.control_variant_id
}


def _fixture(tmp_path: Path, fidelity: dict[tuple[str, str], bool]) -> tuple[Path, Path, Path]:
    dev = tmp_path / "dev"
    dev.mkdir()
    for sub in STUDY_DIR.iterdir():
        if sub.is_dir() and any(sub.glob("*.yaml")):
            shutil.copytree(sub, dev / sub.name)
    fid = dev / "fidelity"
    fid.mkdir()
    rows = []
    for (fam, level), clean in fidelity.items():
        for judge in ("j1", "j2"):
            rows.append({
                "family": fam, "level": level, "judge_model": judge,
                "verdict": {"single_change": True, "change_description": "x", "rule_unchanged": True,
                            "telegraphs_expected_option": not clean, "telegraphed_option_id": None,
                            "other_pressure_introduced": False, "other_pressure_description": None,
                            "explanation": "x"},
            })
    (fid / "fidelity.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return dev, tmp_path / "held", dev / "heldout_split.json"


def test_draw_moves_twins_rewrites_role_and_records_hashes(tmp_path):
    dev, held, split = _fixture(tmp_path, ALL_PASS)
    n_before = len(list(dev.rglob("*.yaml")))
    rc = mhs.main(["--seed", "7", "--fraction", "0.25", "--dev-dir", str(dev),
                   "--heldout-dir", str(held), "--split-file", str(split)])
    assert rc == 0
    record = json.loads(split.read_text(encoding="utf-8"))
    chosen = record["held_out_families"]
    # stratified: at least one family per factor, so >= number of distinct factors
    assert record["seed"] == 7 and len(chosen) >= len(set(FAMILIES.values()))
    assert len(record["files"]) == 2 * len(chosen)  # both twins of every chosen family
    moved = sorted(held.rglob("*.yaml"))
    assert len(moved) == 2 * len(chosen)
    assert len(list(dev.rglob("*.yaml"))) == n_before - len(moved)
    for p in moved:
        text = p.read_text(encoding="utf-8")
        assert 'family_role: "confirmatory_heldout"' in text
        assert 'family_role: "development_only"' not in text
        # hashes recorded are over the rewritten bytes on disk
        assert hashlib.sha256(text.encode("utf-8")).hexdigest() in record["files"].values()
    # Immutable: a second draw is refused.
    rc2 = mhs.main(["--seed", "8", "--dev-dir", str(dev), "--heldout-dir", str(held),
                    "--split-file", str(split)])
    assert rc2 == 2


def test_family_with_unresolved_fidelity_is_ineligible(tmp_path):
    fidelity = dict(ALL_PASS)
    victim = next(iter(FAMILIES))
    level = next(lv for (fam, lv) in fidelity if fam == victim)
    fidelity[(victim, level)] = False  # both judges flag -> FAIL
    dev, held, split = _fixture(tmp_path, fidelity)
    families, reasons = mhs.eligible_families(dev, dev / "fidelity")
    assert victim not in families and set(families) == set(FAMILIES) - {victim}
    assert any(victim in r and "fidelity" in r for r in reasons)


def test_missing_fidelity_review_makes_everything_ineligible(tmp_path):
    dev, held, split = _fixture(tmp_path, {})
    families, reasons = mhs.eligible_families(dev, dev / "fidelity")
    assert families == {} and len(reasons) == len(FAMILIES)


def test_draw_is_seeded_and_stratified():
    fams = {
        "goal_target_a": {"factor": "goal_target"}, "goal_target_b": {"factor": "goal_target"},
        "work_completion_a": {"factor": "work_completion"}, "work_completion_b": {"factor": "work_completion"},
        "authority_transfer_a": {"factor": "authority_transfer"},
    }
    d1 = mhs.draw(fams, fraction=0.25, seed=1)
    d2 = mhs.draw(fams, fraction=0.25, seed=1)
    assert d1 == d2
    # >= 1 per factor forces 3 even though 25% of 5 rounds up to 2
    assert len(d1) == 3 and {fams[f]["factor"] for f in d1} == {"goal_target", "work_completion", "authority_transfer"}
    d3 = mhs.draw(fams, fraction=0.8, seed=1)
    assert len(d3) == 4


def test_dry_run_changes_nothing(tmp_path):
    dev, held, split = _fixture(tmp_path, ALL_PASS)
    before = sorted(p.name for p in dev.rglob("*.yaml"))
    rc = mhs.main(["--seed", "3", "--dry-run", "--dev-dir", str(dev), "--heldout-dir", str(held),
                   "--split-file", str(split)])
    assert rc == 0 and not split.exists() and not held.exists()
    assert sorted(p.name for p in dev.rglob("*.yaml")) == before
