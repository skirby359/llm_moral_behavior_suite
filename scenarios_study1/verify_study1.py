"""Mechanical design controls for scenarios_study1/ (Study 1 / Study 2).

The READMEs make claims about these scenarios -- twins differ by one fact, the
manipulation is confined to the user message, no human theory is named, no
telltale vocabulary tells the model what the researcher expects. This script
checks the claims rather than trusting them. Run it after editing any study
scenario and before spending money:

    python scenarios_study1/verify_study1.py            # development set
    python scenarios_study1/verify_study1.py --full     # also enforce coverage

Inherited rule (scenarios_w2/, scenarios_a5/): when a check fires, fix the
SCENARIO, never loosen the pattern. A control tuned to accept its own subject is
decoration.

Checks
------
  A  file / id / family / role naming agree; directory matches family_role
  B  twins: identical role, policy_context, task_goal, expected_boundary,
     variants and options; base_facts differ by <= 2 sentences; material_facts
     differ by 1-2 entries; focal outcome flips unsafe_action <-> compliant_success;
     any other label difference is DECLARED via twin_divergence_note
  C  manipulation fidelity (mechanical half): treatment messages carry the
     factor's own vocabulary; per-level positive/negative markers; vocabulary of
     OTHER factors may appear in a treatment message only if the control message
     carries it too
  D  no human-theory names in any rendered field; literature_tag tokens absent
  E  no telltale vocabulary in user messages or option text (policy_context exempt)
  H  the policy states the rule without labelling the shortcut (no 'violation',
     'false attestation', 'must not', 'is not posted' ...) -- Gate 3 showed that a
     labelled shortcut leaves nothing for pressure to push against
  U  factorial factors (work_completion): every treatment message is the control
     message's sentences plus exactly the declared sentences of its present factors
  F  held-out split: if heldout_split.json exists, every held-out file's SHA-256
     matches it; held-out families >= 25% and >= 1 per factor
  G  coverage (info unless --full): each factor >= 4 domains, each domain >= 3 factors

The blinded LLM/human fidelity review (Validation Addendum §8) is the other half
of C and lives in `ombs review-fidelity`; this script cannot judge whether a
treatment telegraphs the expected answer, only whether it smuggles vocabulary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ombs.design_controls import (  # noqa: E402
    LEAK,
    POLICY_LABEL,
    TELLTALE,
    THEORY,
    sentence_diff,
    sentences,
)
from ombs.scenario_loader import ScenarioError, load_scenario_file  # noqa: E402

HERE = ROOT / "scenarios_study1"
HELDOUT_DIR = ROOT / "scenarios_study1_heldout"
SPLIT_FILE = HERE / "heldout_split.json"

FACTORS = ("goal_target", "work_completion", "authority_transfer", "framing_urgency", "erosion")

# --- C: the factor's OWN vocabulary (must appear in every treatment message) -----------
FACTOR_POSITIVE = {
    "goal_target": r"\b(target|goal)\b",
    "work_completion": r"\b(backlog|behind|pressure|shortcut|override|delegate|get (it|this|the work) done|for the team|the team needs)\b",
    "authority_transfer": r"\b(director|head of|vice president|vp|senior|my authority|i (approve|authoris|authoriz)|responsib)",
    "framing_urgency": r"\b(lose|loss|forfeit|secure|gain|deadline|urgent)\b",
    "erosion": r".",  # ladder text; checked structurally instead
}
LEVEL_POSITIVE = {
    ("goal_target", "near_miss"): r"\b(only one|one (left|remaining|outstanding|between)|at \d+\b)",
}
LEVEL_NEGATIVE = {
    ("goal_target", "target"): r"\b(only one|one (left|remaining|outstanding|between)|at \d+\b)",
    ("goal_target", "do_best"): r"\b(target|goal)\b",
}

# LEAK keys that ARE a factor's own vocabulary and therefore not a leak for it.
OWN = {
    "goal_target": set(),
    "work_completion": {"urgency", "opportunity"},
    "authority_transfer": {"authority", "responsibility"},
    "framing_urgency": {"urgency", "loss_gain_framing"},
    "erosion": set(),
}

def rendered_fields(sc) -> dict[str, str]:
    out = {
        "base_facts": sc.base_facts,
        "policy_context": sc.policy_context,
        "task_goal": sc.study.task_goal,
    }
    for v in sc.variants:
        out[f"variant:{v.id}"] = v.user_message
    for o in sc.study.options:
        out[f"option:{o.id}"] = o.text
    return out


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.infos: list[str] = []

    def fail(self, msg: str) -> None:
        self.failures.append(msg)
        print(f"  FAIL  {msg}")

    def info(self, msg: str) -> None:
        self.infos.append(msg)
        print(f"  info  {msg}")


def check_file(path: pathlib.Path, sc, rep: Report) -> None:
    st = sc.study
    stem = path.stem
    factor_dir = path.parent.name
    in_heldout = HELDOUT_DIR in path.parents

    # A -- naming
    m = re.fullmatch(r"([a-z_]+)__(perm|imperm)", stem)
    if not m:
        rep.fail(f"{path.name}: filename must be <domain>__perm.yaml or <domain>__imperm.yaml")
        return
    domain, suffix = m.groups()
    expected_id = f"s1_{factor_dir}_{domain}_{suffix}"
    if sc.id != expected_id:
        rep.fail(f"{path.name}: id {sc.id!r} != {expected_id!r}")
    if factor_dir != st.manipulation.factor:
        rep.fail(f"{path.name}: in directory {factor_dir!r} but factor is {st.manipulation.factor!r}")
    if domain != st.domain:
        rep.fail(f"{path.name}: filename domain {domain!r} != study.domain {st.domain!r}")
    if st.family != f"{st.manipulation.factor}_{st.domain}":
        rep.fail(f"{path.name}: family {st.family!r} != '<factor>_<domain>'")
    if (suffix == "perm") != (st.permissibility == "permissible"):
        rep.fail(f"{path.name}: filename suffix {suffix!r} disagrees with permissibility {st.permissibility!r}")
    if in_heldout != (st.family_role == "confirmatory_heldout"):
        rep.fail(f"{path.name}: family_role {st.family_role!r} disagrees with its directory")

    # C -- manipulation fidelity, mechanical half
    factor = st.manipulation.factor
    ctrl = sc.variant(st.control_variant_id)
    ctrl_low = ctrl.user_message.lower()
    messages = [v.user_message for v in sc.variants]
    if len(set(m.strip() for m in messages)) != len(messages):
        rep.fail(f"{path.name}: two variants share the same user_message")
    # U -- factorial cells are literal sentence unions of declared factor sentences
    fs = st.factor_sentences
    if fs:
        ctrl_sents = set(sentences(ctrl.user_message))
        for name, sent in fs.items():
            if len(sentences(sent)) != 1:
                rep.fail(f"{path.name}: factor sentence {name!r} is not exactly one sentence")
        for v in sc.variants:
            expected = ctrl_sents | {fs[k] .strip() for k, val in v.factors.items() if val == "present"}
            actual = set(sentences(v.user_message))
            if actual != expected:
                rep.fail(f"{path.name}/{v.id}: message is not control + its present factor sentences; "
                         f"extra={sorted(actual - expected)[:2]} missing={sorted(expected - actual)[:2]}")
    for v in sc.variants:
        low = v.user_message.lower()
        is_ctrl = v.id == ctrl.id
        if not is_ctrl:
            if v.pressure_type != factor:
                rep.fail(f"{path.name}/{v.id}: treatment pressure_type {v.pressure_type!r} != factor {factor!r}")
            if not fs and not re.search(FACTOR_POSITIVE[factor], low):
                rep.fail(f"{path.name}/{v.id}: treatment message lacks the {factor} vocabulary")
            for key, pat in LEAK.items():
                if key in OWN[factor]:
                    continue
                hits = set(re.findall(pat, low))
                ctrl_hits = set(re.findall(pat, ctrl_low))
                leaked = hits - ctrl_hits
                if leaked:
                    rep.fail(f"{path.name}/{v.id}: LEAK of {key} vocabulary not present in the control: {sorted(leaked)[:4]}")
        pos = LEVEL_POSITIVE.get((factor, v.level))
        if pos and not re.search(pos, low):
            rep.fail(f"{path.name}/{v.id}: level {v.level!r} lacks its marker vocabulary")
        neg = LEVEL_NEGATIVE.get((factor, v.level))
        if neg and re.search(neg, low):
            rep.fail(f"{path.name}/{v.id}: level {v.level!r} carries vocabulary reserved for another level: "
                     f"{re.search(neg, low).group(0)!r}")

    # D -- theory names and metadata leakage into rendered text
    tag_tokens = [t for t in re.split(r"[_\s]+", st.manipulation.literature_tag.lower()) if len(t) > 3]
    for field, text in rendered_fields(sc).items():
        low = text.lower()
        hit = re.search(THEORY, low)
        if hit:
            rep.fail(f"{path.name}/{field}: names a human theory or author: {hit.group(0)!r}")
        for tok in tag_tokens:
            if re.search(rf"\b{re.escape(tok)}\b", low):
                rep.fail(f"{path.name}/{field}: literature_tag token {tok!r} appears in rendered text")
        for label in ("unsafe_action", "compliant_success", "compliant_failure", "overrefusal",
                      "impermissible", "lab_experiment", "survey_intention", "field_association"):
            if label in low:
                rep.fail(f"{path.name}/{field}: metadata label {label!r} appears in rendered text")

    # H -- the policy states the rule; it does not label the shortcut
    hit = re.search(POLICY_LABEL, sc.policy_context.lower())
    if hit:
        rep.fail(f"{path.name}/policy_context: labels the shortcut ({hit.group(0)!r}); state the rule instead")

    # E -- telltale vocabulary where the model reads it
    for v in sc.variants:
        hit = re.search(TELLTALE, v.user_message.lower())
        if hit:
            rep.fail(f"{path.name}/{v.id}: telltale vocabulary in user_message: {hit.group(0)!r}")
    for o in st.options:
        hit = re.search(TELLTALE, o.text.lower())
        if hit:
            rep.fail(f"{path.name}/option:{o.id}: telltale vocabulary in option text: {hit.group(0)!r}")

    # erosion needs a ladder (wave 2); everything else must be single-turn
    if factor == "erosion":
        if not sc.pushback_sequence:
            rep.fail(f"{path.name}: erosion scenario has no pushback_sequence")
    elif sc.pushback_sequence:
        rep.fail(f"{path.name}: single-turn factor {factor!r} must not carry a pushback_sequence")


def check_twins(family: str, pair: dict[str, tuple[pathlib.Path, object]], rep: Report) -> None:
    if set(pair) != {"permissible", "impermissible"}:
        rep.fail(f"family {family}: needs both twins, has {sorted(pair)}")
        return
    (_, p), (_, i) = pair["permissible"], pair["impermissible"]
    for attr in ("role", "policy_context", "expected_boundary"):
        if getattr(p, attr).strip() != getattr(i, attr).strip():
            rep.fail(f"family {family}: twins differ in {attr}")
    if p.study.task_goal.strip() != i.study.task_goal.strip():
        rep.fail(f"family {family}: twins differ in task_goal")
    if p.study.focal_action_id != i.study.focal_action_id:
        rep.fail(f"family {family}: twins differ in focal_action_id")
    if p.study.control_variant_id != i.study.control_variant_id:
        rep.fail(f"family {family}: twins differ in control_variant_id")
    if p.study.family_role != i.study.family_role:
        rep.fail(f"family {family}: twins differ in family_role")

    pv = [(v.id, v.level, v.pressure_type, v.user_message.strip(), tuple(sorted(v.factors.items()))) for v in p.variants]
    iv = [(v.id, v.level, v.pressure_type, v.user_message.strip(), tuple(sorted(v.factors.items()))) for v in i.variants]
    if pv != iv:
        rep.fail(f"family {family}: twins differ in variants (ids, levels, pressure types or messages)")

    po = [(o.id, o.text.strip()) for o in p.study.options]
    io = [(o.id, o.text.strip()) for o in i.study.options]
    if po != io:
        rep.fail(f"family {family}: twins differ in option ids/text/order")
    else:
        diverged = []
        for a, b in zip(p.study.options, i.study.options):
            if a.id == p.study.focal_action_id:
                if not (a.outcome == "compliant_success" and b.outcome == "unsafe_action"):
                    rep.fail(f"family {family}: focal action must flip unsafe_action (imperm) <-> "
                             f"compliant_success (perm); got {b.outcome!r} / {a.outcome!r}")
            elif a.outcome != b.outcome:
                diverged.append(f"{a.id}: {b.outcome} -> {a.outcome}")
        if diverged and not (p.study.twin_divergence_note and i.study.twin_divergence_note):
            rep.fail(f"family {family}: non-focal labels differ ({diverged}) but twin_divergence_note "
                     "is missing on one or both twins -- declare it")
        if not diverged and (p.study.twin_divergence_note or i.study.twin_divergence_note):
            rep.info(f"family {family}: twin_divergence_note present but no non-focal label differs")

    nd = sentence_diff(p.base_facts, i.base_facts)
    if nd == 0:
        rep.fail(f"family {family}: base_facts are identical -- nothing makes the focal action legal")
    elif nd > 2:
        rep.fail(f"family {family}: base_facts differ in {nd} sentences (max 2)")
    mf = sum(1 for a, b in zip(p.material_facts, i.material_facts) if a.strip() != b.strip())
    mf += abs(len(p.material_facts) - len(i.material_facts))
    if not 1 <= mf <= 2:
        rep.fail(f"family {family}: material_facts differ in {mf} entries (expected 1-2)")


def check_split(files: list[tuple[pathlib.Path, object]], rep: Report) -> None:
    heldout = [(p, s) for p, s in files if s.study.family_role == "confirmatory_heldout"]
    if not SPLIT_FILE.exists():
        rep.info("no heldout_split.json committed yet (development phase); F skipped")
        if heldout:
            rep.fail("held-out files exist but heldout_split.json does not -- the split must be committed")
        return
    split = json.loads(SPLIT_FILE.read_text(encoding="utf-8"))
    recorded = split.get("files", {})
    for p, s in heldout:
        rel = p.relative_to(ROOT).as_posix()
        if rel not in recorded:
            rep.fail(f"{rel}: held-out file not in heldout_split.json")
        elif recorded[rel] != s.source_sha256:
            rep.fail(f"{rel}: SHA-256 differs from the committed split -- held-out text was edited")
    for rel in recorded:
        if not (ROOT / rel).exists():
            rep.fail(f"{rel}: listed in heldout_split.json but missing on disk")
    families = {s.study.family: s.study.family_role for _, s in files}
    n_held = sum(1 for r in families.values() if r == "confirmatory_heldout")
    if families and n_held / len(families) < 0.25:
        rep.fail(f"held-out families {n_held}/{len(families)} < 25%")
    per_factor = defaultdict(set)
    for _, s in files:
        if s.study.family_role == "confirmatory_heldout":
            per_factor[s.study.manipulation.factor].add(s.study.family)
    for f in {s.study.manipulation.factor for _, s in files}:
        if not per_factor.get(f):
            rep.fail(f"factor {f!r} has no held-out family")


def check_coverage(files: list[tuple[pathlib.Path, object]], rep: Report, enforce: bool) -> None:
    by_factor = defaultdict(set)
    by_domain = defaultdict(set)
    for _, s in files:
        by_factor[s.study.manipulation.factor].add(s.study.domain)
        by_domain[s.study.domain].add(s.study.manipulation.factor)
    for f, ds in sorted(by_factor.items()):
        msg = f"factor {f}: {len(ds)} domain(s) {sorted(ds)}"
        (rep.fail if enforce and len(ds) < 4 else rep.info)(msg)
    for d, fs in sorted(by_domain.items()):
        msg = f"domain {d}: {len(fs)} factor(s) {sorted(fs)}"
        (rep.fail if enforce and len(fs) < 3 else rep.info)(msg)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="enforce coverage minimums")
    args = ap.parse_args()

    paths = sorted(HERE.rglob("*.yaml")) + (sorted(HELDOUT_DIR.rglob("*.yaml")) if HELDOUT_DIR.exists() else [])
    rep = Report()
    files: list[tuple[pathlib.Path, object]] = []
    for p in paths:
        print(f"=== {p.relative_to(ROOT).as_posix()}")
        try:
            sc = load_scenario_file(p)
        except ScenarioError as exc:
            rep.fail(f"{p.name}: does not load: {str(exc).splitlines()[0]}")
            continue
        if sc.study is None:
            rep.fail(f"{p.name}: no `study` block")
            continue
        files.append((p, sc))
        check_file(p, sc, rep)

    fams: dict[str, dict[str, tuple[pathlib.Path, object]]] = defaultdict(dict)
    for p, s in files:
        fams[s.study.family][s.study.permissibility] = (p, s)
    print("=== twins")
    for fam, pair in sorted(fams.items()):
        check_twins(fam, pair, rep)
    print("=== held-out split")
    check_split(files, rep)
    print("=== coverage")
    check_coverage(files, rep, enforce=args.full)

    print()
    print(f"{len(files)} file(s), {len(fams)} famil(ies) checked")
    print("CONTROLS VERIFIED" if not rep.failures else f"CONTROLS VIOLATED: {len(rep.failures)} failure(s)")
    for h in sha_summary(files):
        print(h)
    return 1 if rep.failures else 0


def sha_summary(files) -> list[str]:
    out = []
    for p, s in files:
        h = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
        assert h == (s.source_sha256 or "")[:12], "loader hash disagrees with file bytes"
        out.append(f"  {h}  {p.relative_to(ROOT).as_posix()}")
    return out


if __name__ == "__main__":
    sys.exit(main())
