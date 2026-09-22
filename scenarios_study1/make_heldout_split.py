"""Seeded held-out draw -- the Gate 4 prerequisite (plan §4a; Validation Addendum §3).

Run ONCE, after every development family is authored and fidelity-reviewed, and
BEFORE any confirmatory frontier run:

    python scenarios_study1/make_heldout_split.py --seed 20260909 [--fraction 0.25] [--dry-run]

What it does, in order:
  1. lists families under scenarios_study1/ (twins required; any family with a
     fidelity status other than PASS is ineligible and reported);
  2. draws ceil(fraction * n) families -- stratified so every factor contributes at
     least one, then filled at random with the given seed;
  3. moves both twins to scenarios_study1_heldout/<factor>/ and rewrites
     `family_role` to `confirmatory_heldout` in both files;
  4. writes scenarios_study1/heldout_split.json with the seed, date, fraction, the
     family list and the SHA-256 of every held-out file AFTER the rewrite.

After this, verify_study1.py checks the hashes on every run, study_runner refuses to
run held-out families unless asked and then runs all of them, and analysis/study.py
reads only confirmatory_heldout rows for the primary estimate. Held-out text is never
edited again; a family authored later is development-only by construction.

The script refuses to run if heldout_split.json already exists. A second draw is a
new experiment and must be recorded as such, by hand.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import pathlib
import random
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ombs.fidelity_review import PASS, fidelity_status  # noqa: E402
from ombs.scenario_loader import load_scenario_file  # noqa: E402

DEV_DIR = ROOT / "scenarios_study1"
HELDOUT_DIR = ROOT / "scenarios_study1_heldout"
SPLIT_FILE = DEV_DIR / "heldout_split.json"


def _rel(p: pathlib.Path) -> str:
    """Repo-relative POSIX path when under ROOT (the recorded key), else absolute."""
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def eligible_families(dev_dir: pathlib.Path, fidelity_dir: pathlib.Path) -> tuple[dict, list[str]]:
    """family -> {factor, files: [paths]}; plus a list of ineligibility reasons."""
    fams: dict[str, dict] = defaultdict(lambda: {"factor": None, "files": [], "levels": set()})
    for p in sorted(dev_dir.rglob("*.yaml")):
        sc = load_scenario_file(p)
        if sc.study is None:
            continue
        f = fams[sc.study.family]
        f["factor"] = sc.study.manipulation.factor
        f["files"].append(p)
        f["levels"] |= {v.level for v in sc.variants if v.id != sc.study.control_variant_id}
    status = fidelity_status(fidelity_dir) if fidelity_dir.exists() else {}
    reasons: list[str] = []
    ok: dict[str, dict] = {}
    for fam, f in sorted(fams.items()):
        if len(f["files"]) != 2:
            reasons.append(f"{fam}: needs both twins, has {len(f['files'])} file(s)")
            continue
        bad = [lv for lv in sorted(f["levels"])
               if not str(status.get((fam, lv), "MISSING")).startswith(PASS)]
        if bad:
            reasons.append(f"{fam}: fidelity not PASS for level(s) {bad}")
            continue
        ok[fam] = f
    return ok, reasons


def draw(families: dict[str, dict], *, fraction: float, seed: int) -> list[str]:
    n = max(1, math.ceil(fraction * len(families)))
    rng = random.Random(seed)
    by_factor: dict[str, list[str]] = defaultdict(list)
    for fam, f in families.items():
        by_factor[f["factor"]].append(fam)
    chosen: list[str] = []
    for factor in sorted(by_factor):
        pool = sorted(by_factor[factor])
        chosen.append(rng.choice(pool))
    rest = sorted(set(families) - set(chosen))
    rng.shuffle(rest)
    while len(chosen) < n and rest:
        chosen.append(rest.pop())
    return sorted(chosen)


def perform(chosen: list[str], families: dict[str, dict], *, seed: int, fraction: float,
            dev_dir: pathlib.Path, heldout_dir: pathlib.Path, split_file: pathlib.Path,
            dry_run: bool) -> dict:
    record = {
        "seed": seed,
        "fraction": fraction,
        "drawn_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "eligible_families": sorted(families),
        "held_out_families": chosen,
        "files": {},
    }
    for fam in chosen:
        for src in families[fam]["files"]:
            rel_src = src.relative_to(dev_dir)
            dst = heldout_dir / rel_src
            text = src.read_text(encoding="utf-8")
            if 'family_role: "development_only"' not in text:
                raise SystemExit(f"{src}: expected family_role \"development_only\" to rewrite")
            new_text = text.replace('family_role: "development_only"', 'family_role: "confirmatory_heldout"', 1)
            digest = hashlib.sha256(new_text.encode("utf-8")).hexdigest()
            record["files"][_rel(dst)] = digest
            print(f"  {'would move' if dry_run else 'move'} {rel_src.as_posix()} -> "
                  f"{_rel(dst)}  {digest[:12]}")
            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(new_text, encoding="utf-8")
                src.unlink()
    if not dry_run:
        split_file.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {_rel(split_file)}")
    return record


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True, help="preregister this number")
    ap.add_argument("--fraction", type=float, default=0.25)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--dev-dir", default=str(DEV_DIR))
    ap.add_argument("--heldout-dir", default=str(HELDOUT_DIR))
    ap.add_argument("--split-file", default=str(SPLIT_FILE))
    ap.add_argument("--fidelity-dir", default=None, help="default: <dev-dir>/fidelity")
    args = ap.parse_args(argv)

    dev_dir, heldout_dir, split_file = map(pathlib.Path, (args.dev_dir, args.heldout_dir, args.split_file))
    fidelity_dir = pathlib.Path(args.fidelity_dir) if args.fidelity_dir else dev_dir / "fidelity"
    if split_file.exists():
        print(f"REFUSING: {split_file} already exists. The held-out split is drawn once.")
        return 2

    families, reasons = eligible_families(dev_dir, fidelity_dir)
    for r in reasons:
        print(f"  ineligible  {r}")
    if not families:
        print("no eligible families")
        return 2
    chosen = draw(families, fraction=args.fraction, seed=args.seed)
    print(f"{len(families)} eligible families, drawing {len(chosen)} with seed {args.seed}: {chosen}")
    perform(chosen, families, seed=args.seed, fraction=args.fraction, dev_dir=dev_dir,
            heldout_dir=heldout_dir, split_file=split_file, dry_run=args.dry_run)
    if not args.dry_run:
        print("Now: commit the moved files and heldout_split.json together, then run "
              "verify_study1.py. Held-out text is frozen from this commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
