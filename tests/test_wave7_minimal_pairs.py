"""Wave 7 minimal pairs: each variant is its anchor plus the preregistered substitutions and
nothing else; the replacement vocabulary comes from the other anchor; G and P commute; the
template invariants hold; configs carry their gate; approval requires a prior freeze.

The design note's warning is that a variant can 'change many things and read one'. These tests
make the manifest (scenarios_sandbox/wave7_pairs.json) the only way a variant can differ from
its anchor, so the preregistered span partition is enforced mechanically rather than by care.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from ombs.config import SandboxRunConfig
from ombs.scenario_loader import load_sandbox_scenarios_from_dir

ROOT = Path(__file__).resolve().parents[1]
SCEN_DIR = ROOT / "scenarios_sandbox"
spec = importlib.util.spec_from_file_location("wave7_pairs", SCEN_DIR / "wave7_pairs.py")
w7 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w7)

MANIFEST = w7.load_manifest()
VARIANTS = MANIFEST["variants"]
FAMILIES = {s.family: s for s in load_sandbox_scenarios_from_dir(SCEN_DIR)}
WAVE7_CONFIGS = sorted(ROOT.glob("configs/run.sandbox7_*_gpt.yaml"))


def _norm(text: str) -> str:
    return " ".join(text.split()).lower()


def _anchor_text(family: str) -> str:
    return (ROOT / MANIFEST["anchors"][family]["file"]).read_text(encoding="utf-8")


def test_manifest_names_four_variants_one_g_and_one_p_per_anchor():
    assert len(VARIANTS) == 4
    by_anchor: dict[str, set[str]] = {}
    for fam, v in VARIANTS.items():
        assert v["dimension"] in ("G", "P"), fam
        assert v["anchor"] in MANIFEST["anchors"], fam
        by_anchor.setdefault(v["anchor"], set()).add(v["dimension"])
        assert fam == f"sandbox_{w7.stem_of(v['file'])}", fam
    assert all(dims == {"G", "P"} for dims in by_anchor.values()), by_anchor


@pytest.mark.parametrize("family", sorted(VARIANTS))
def test_each_variant_is_its_anchor_plus_the_declared_substitutions(family):
    v = VARIANTS[family]
    anchor = _anchor_text(v["anchor"])
    variant_path = ROOT / v["file"]
    assert variant_path.exists(), f"{v['file']} has not been generated (uv run python scenarios_sandbox/wave7_pairs.py)"
    variant = variant_path.read_text(encoding="utf-8")
    expected_body = w7.variant_body_from_anchor(anchor, v, MANIFEST)
    assert w7.body_of(variant, MANIFEST) == expected_body, f"{v['file']} differs from anchor + manifest"
    # the whole file, header included, is what the generator writes
    assert variant == w7.render_variant(anchor, v, family, MANIFEST)
    for src, _dst in v["substitutions"]:
        assert src in anchor, f"{family}: dead substitution {src!r} (not in anchor)"
        assert src not in w7.body_of(variant, MANIFEST), f"{family}: {src!r} survives in the variant"


@pytest.mark.parametrize("family", sorted(VARIANTS))
def test_replacement_vocabulary_comes_from_the_other_anchor(family):
    v = VARIANTS[family]
    other = [a for a in MANIFEST["anchors"] if a != v["anchor"]][0]
    other_text = _norm(_anchor_text(other))
    for _src, dst in v["substitutions"]:
        assert _norm(dst) in other_text, f"{family}: replacement {dst!r} is not vocabulary of {other}"


@pytest.mark.parametrize("anchor", sorted(MANIFEST["anchors"]))
def test_g_and_p_substitutions_commute_on_each_anchor(anchor):
    subs = {v["dimension"]: v["substitutions"] for v in VARIANTS.values() if v["anchor"] == anchor}
    text = _anchor_text(anchor)
    gp = w7.apply_substitutions(w7.apply_substitutions(text, subs["P"]), subs["G"])
    pg = w7.apply_substitutions(w7.apply_substitutions(text, subs["G"]), subs["P"])
    assert gp == pg
    for g_src, _ in subs["G"]:
        for p_src, _ in subs["P"]:
            assert g_src not in p_src and p_src not in g_src, (g_src, p_src)


@pytest.mark.parametrize("family", sorted(VARIANTS))
def test_template_invariants_hold_against_the_anchor(family):
    v = VARIANTS[family]
    var, anc = FAMILIES[family], FAMILIES[v["anchor"]]
    assert var.checker.kind == anc.checker.kind == "approval_gate"
    assert set(var.available_tools) == set(anc.available_tools)
    assert var.technical_step_cap == anc.technical_step_cap == 16
    assert var.session_limit_actions == anc.session_limit_actions
    assert len(var.shortcuts) == len(anc.shortcuts) == 3
    assert {s.id for s in var.shortcuts} == {s.id for s in anc.shortcuts}
    assert var.task_compliant_failure_addendum == anc.task_compliant_failure_addendum
    assert var.task_authority_salience_addendum == anc.task_authority_salience_addendum
    assert 35 <= len(var.rule_text.split()) <= 55
    assert var.rule_text.count(".") == anc.rule_text.count(".")
    assert var.domain == anc.domain, "a variant is a manipulated copy of its anchor's domain, not a new domain"
    assert var.family_role == anc.family_role == "development_only"
    assert (var.literature_tag, var.human_evidence_class, var.anchor_citation_ids) == (
        anc.literature_tag, anc.human_evidence_class, anc.anchor_citation_ids)
    assert var.stuck_blocker.rule == anc.stuck_blocker.rule and var.stuck_blocker.record == anc.stuck_blocker.record
    assert len(var.never_render) == len(anc.never_render)
    assert [q.expect for q in var.remit_questions] == [q.expect for q in anc.remit_questions]
    # the one differing file has the same shape and the same changed line in both
    (vf,), (af,) = var.differing_files(), anc.differing_files()
    vv, av = vf.variants(), af.variants()
    for level in ("solvable", "stuck"):
        assert len(vv[level].splitlines()) == len(av[level].splitlines())
    changed = lambda d: [i for i, (a, b) in enumerate(zip(d["solvable"].splitlines(), d["stuck"].splitlines())) if a != b]  # noqa: E731
    assert changed(vv) == changed(av) and len(changed(vv)) == 1
    if v["dimension"] == "P":
        # a party swap touches rule_text only: every other rendered field is the anchor's
        for field in ("task", "check_description", "role_line", "recipient_name", "handbook_rule_marker"):
            assert getattr(var, field) == getattr(anc, field), field


def test_wave7_configs_pin_one_variant_and_carry_gate_or_approval():
    assert WAVE7_CONFIGS, "no configs/run.sandbox7_*_gpt.yaml"
    pinned = set()
    for p in WAVE7_CONFIGS:
        cfg = SandboxRunConfig.from_yaml(p)
        assert len(cfg.scenario_ids) == 1, p.name
        fam = f"sandbox_{cfg.scenario_ids[0][3:]}"
        assert fam in VARIANTS, p.name
        pinned.add(fam)
        assert cfg.provider == "openai" and cfg.models == ["gpt-5.5"], p.name
        assert cfg.solvability == ["stuck"] and cfg.task_framing == ["baseline"], p.name
        assert cfg.defer_available == ["off"] and cfg.tool_transport == "native", p.name
        assert cfg.execution.runs_per_variant == 20, p.name
        head = p.read_text(encoding="utf-8").split("run_id:")[0]
        assert "PREREG_WAVE7_DOMAIN_EFFECT.md" in head, p.name
        assert "NOT TO BE RUN" in head or "PI approved" in head, f"{p.name} has no gate or approval in its header"
    assert pinned == set(VARIANTS)


def test_approval_requires_a_prior_freeze():
    """A config header may say 'PI approved' only once its family is registered frozen with a
    matching hash. sandbox_runner defaults unregistered families to runnable, so this is the
    guard that makes freeze-before-run mechanical for Wave 7."""
    registry = json.loads((SCEN_DIR / "frozen_families.json").read_text(encoding="utf-8"))["families"]
    for p in WAVE7_CONFIGS:
        head = p.read_text(encoding="utf-8").split("run_id:")[0]
        if "PI approved" not in head:
            continue
        cfg = SandboxRunConfig.from_yaml(p)
        fam = f"sandbox_{cfg.scenario_ids[0][3:]}"
        entry = registry.get(fam)
        assert entry, f"{p.name} is approved but {fam} is not in frozen_families.json"
        assert entry["may_run"] is True
        assert entry["scenario_sha256"] == FAMILIES[fam].source_sha256, f"{fam} edited since it was frozen"


def test_committed_anchor_arms_ran_on_the_current_anchor_bytes():
    """The contrasts read the anchors' Wave 5 arms as committed; those arms must have run on
    exactly the anchor bytes that exist today."""
    for fam, a in MANIFEST["anchors"].items():
        freeze = ROOT / a["baseline_arm"] / "freeze.json"
        if not freeze.exists():
            pytest.skip(f"{a['baseline_arm']} not present in this checkout")
        data = json.loads(freeze.read_text(encoding="utf-8"))
        shas = {s["sha256"] for s in data["scenarios"]}
        assert FAMILIES[fam].source_sha256 in shas, f"{fam}: committed arm ran on different bytes"


def test_variants_are_line_aligned_with_their_anchor_below_the_header():
    """Line alignment is what makes `diff` an audit; the generator preserves it."""
    for fam, v in VARIANTS.items():
        anchor_body = w7.body_of(_anchor_text(v["anchor"]), MANIFEST).splitlines()
        variant_body = w7.body_of((ROOT / v["file"]).read_text(encoding="utf-8"), MANIFEST).splitlines()
        assert len(anchor_body) == len(variant_body), fam
        differing = [i for i, (a, b) in enumerate(zip(anchor_body, variant_body)) if a != b]
        assert differing, fam
        # a P swap changes rule_text lines only (two lines: the owner clause and the wrapped actor)
        if v["dimension"] == "P":
            assert 1 <= len(differing) <= 3, (fam, differing)
        assert re.search(r"^rule_text:", "\n".join(anchor_body), re.M)
