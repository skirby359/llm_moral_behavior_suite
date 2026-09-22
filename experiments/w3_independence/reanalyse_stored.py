"""Re-run `analyse()` over stored runs with the current code — no API calls.

`analyse()` changed: a truncated, refused or unparseable call is now EXCLUDED from
the recall statistics instead of being scored as "found zero defects". Every
`variance_*.json` written before that change carries figures computed the old way, and
the only honest way to know what moved is to re-derive them from the stored per-call
findings.

    python experiments/w3_independence/reanalyse_stored.py            # report only
    python experiments/w3_independence/reanalyse_stored.py --write    # rewrite files

Reports stored vs recomputed for the headline metrics, and which runs contain
non-measurement calls at all. Runs with none are unaffected by definition, and are
recomputed anyway as a control: if their numbers move, this script is wrong.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_w3  # noqa: E402
from defects_xdoc import DEFECTS_XDOC  # noqa: E402
from defects_xdoc_ext import DEFECTS_XDOC_EXT  # noqa: E402
from defects_xdoc_ext2 import DEFECTS_XDOC_EXT2  # noqa: E402
from defects_long import DEFECTS_LONG  # noqa: E402

CORPORA = {
    "_xdoc15_": list(DEFECTS_XDOC) + list(DEFECTS_XDOC_EXT) + list(DEFECTS_XDOC_EXT2),
    "_xdoc9_": list(DEFECTS_XDOC) + list(DEFECTS_XDOC_EXT),
    "_xdoc_": list(DEFECTS_XDOC),
    "_long_": list(DEFECTS_LONG),
}

METRICS = ("mean_per_call", "best_single", "union_recall",
           "marginal_gain_after_first", "mean_pairwise_jaccard")


def defects_for(name: str):
    for tag, d in CORPORA.items():  # xdoc15 before xdoc9 before xdoc: longest first
        if tag in name:
            return d
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="rewrite the variance files with the recomputed analyses")
    args = ap.parse_args()

    files = sorted(
        p for p in HERE.glob("variance_*.json")
        if not p.name.endswith(".sections_recomputed.json")
    )
    moved = 0

    for path in files:
        defects = defects_for(path.name)
        if defects is None:
            continue
        run_w3.DEFECTS = defects
        data = json.loads(path.read_text(encoding="utf-8"))
        reps = data.get("per_repeat") or []
        if not reps:
            continue

        header_done = False
        changed_here = False
        for rep in reps:
            runs = rep.get("runs") or []
            # `failed` was added at the same time as the exclusion, so older files
            # do not carry it. Re-derive from the stored raw text.
            for r in runs:
                if "failed" not in r:
                    r["failed"] = run_w3.is_failed_call(r.get("raw", ""))
            stored = rep["analysis"]
            fresh = run_w3.analyse(runs, stored.get("label", "?"), data.get("model", "?"))
            diffs = {m: (stored.get(m), fresh.get(m))
                     for m in METRICS if stored.get(m) != fresh.get(m)}
            if not header_done:
                nf = sum(1 for r in runs if r.get("failed"))
                print(f"\n=== {path.name}   ({len(defects)} defects in scope)")
                header_done = True
            bad = sum(1 for r in runs if r.get("failed"))
            tag = f"{fresh['k']}/{fresh['k_attempted']} measuring" if bad else "all measuring"
            if diffs:
                changed_here = True
                moved += 1
                print(f"  repeat {rep.get('repeat')}: CHANGED ({tag})")
                for m, (a, b) in diffs.items():
                    print(f"      {m:<28} {a}  ->  {b}")
            else:
                print(f"  repeat {rep.get('repeat')}: unchanged ({tag})")
            rep["analysis"] = fresh

        if args.write and changed_here:
            data["variance"] = run_w3.summarize_variance([r["analysis"] for r in reps])
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            print(f"  rewrote {path.name}")

    print(f"\n{moved} repeat(s) changed.")
    if not args.write and moved:
        print("Re-run with --write to update the files.")
    print("Runs with no non-measurement calls are a CONTROL: they must be unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
