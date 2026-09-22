"""Recompute section-signature metrics from stored findings — no API calls.

WHY THIS EXISTS. `XDOC_SECTION_RE` was written with a *capturing* group. `re.findall`
returns only the groups when a pattern has any, so every clause number matched by the
first alternative came back as `''` and was discarded, and each call's signature
collapsed to the set of document names. Every cross-document run therefore reported
`sections_union = 4.00` and section Jaccard exactly `1.000` — which reads as a
finding ("all eight calls looked in exactly the same places") and was a regex bug.

The fix is one character, but the affected runs cost real money. They do not need to
be repeated: `variance_*.json` stores every call's raw `findings` list, so the
signatures can be re-derived offline against the corrected pattern.

    python experiments/w3_independence/recompute_sections.py

Writes `<file>.sections_recomputed.json` beside each input and prints the before/after
so the size of the error is visible rather than quietly patched.
"""

from __future__ import annotations

import json
import statistics
import sys
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from run_w3 import SECTION_RE, XDOC_SECTION_RE, jaccard  # noqa: E402


def signature(findings: list[str], pattern) -> set[str]:
    sig: set[str] = set()
    for f in findings:
        for m in pattern.findall(f):
            if isinstance(m, tuple):
                m = next((x for x in m if x), "")
            if m:
                sig.add(m.lower().replace("section ", "s").strip())
    return sig


def analyse_sections(runs: list[dict], pattern) -> dict:
    sigs = [signature(r.get("findings", []), pattern) for r in runs]
    pairs = [jaccard(a, b) for a, b in combinations(sigs, 2)]
    union, curve = set(), []
    for s in sigs:
        union |= s
        curve.append(len(union))
    return {
        "sections_per_call": [len(s) for s in sigs],
        "sections_union": len(union),
        "sections_union_curve": curve,
        "mean_pairwise_jaccard_sections": (
            round(statistics.mean(pairs), 3) if pairs else None
        ),
        "sections_seen": sorted(union),
    }


def main() -> int:
    # Exclude this script's own output. `variance_*.json` matched
    # `variance_*.sections_recomputed.json` on the second run, and it crashed on a
    # missing key -- so it was not idempotent, which for an analysis script that
    # rewrites files beside its inputs is a defect worth fixing rather than
    # working around by running it once.
    files = sorted(
        p for p in HERE.glob("variance_*.json")
        if not p.name.endswith(".sections_recomputed.json")
    )
    if not files:
        print("no variance_*.json files found")
        return 1

    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        reps = data.get("per_repeat") or []
        if not reps:
            continue
        # Which pattern the run *should* have used. The single-document runs used
        # SECTION_RE and were never affected by the bug; they are recomputed anyway
        # as a control -- if their numbers move, this script is wrong.
        #
        # `_xdoc` not `_xdoc_`: the first version missed `variance_*_xdoc9_r2.json`
        # entirely and processed it as a single-document control, applying the narrow
        # pattern and turning a CORRECT stored union of 70 into 40. Anything
        # cross-document must match here, whatever the corpus is called.
        is_xdoc = "_xdoc" in path.name
        pattern = XDOC_SECTION_RE if is_xdoc else SECTION_RE

        print(f"\n=== {path.name}  ({'xdoc' if is_xdoc else 'single-doc control'})")
        out_reps = []
        for rep in reps:
            stored = rep["analysis"]
            fixed = analyse_sections(rep.get("runs", []), pattern)
            print(
                f"  repeat {rep.get('repeat')}: "
                f"union {stored.get('sections_union')} -> {fixed['sections_union']}   "
                f"jaccard {stored.get('mean_pairwise_jaccard_sections')} -> "
                f"{fixed['mean_pairwise_jaccard_sections']}"
            )
            out_reps.append({"repeat": rep.get("repeat"), **fixed})

        unions = [r["sections_union"] for r in out_reps]
        jacs = [r["mean_pairwise_jaccard_sections"] for r in out_reps if
                r["mean_pairwise_jaccard_sections"] is not None]
        summary = {
            "source": path.name,
            "pattern": "XDOC_SECTION_RE" if is_xdoc else "SECTION_RE",
            "affected_by_capturing_group_bug": is_xdoc,
            "sections_union_mean": round(statistics.mean(unions), 2) if unions else None,
            "sections_union_sd": round(statistics.stdev(unions), 2) if len(unions) > 1 else 0.0,
            "section_jaccard_mean": round(statistics.mean(jacs), 3) if jacs else None,
            "section_jaccard_sd": round(statistics.stdev(jacs), 3) if len(jacs) > 1 else 0.0,
            "per_repeat": out_reps,
        }
        out = path.with_suffix(".sections_recomputed.json")
        out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"  -> union {summary['sections_union_mean']} +/- {summary['sections_union_sd']}"
              f"   jaccard {summary['section_jaccard_mean']} +/- {summary['section_jaccard_sd']}")
        print(f"  wrote {out.name}")

    print("\nSingle-document files are recomputed as a CONTROL: their stored and "
          "recomputed numbers should agree, because SECTION_RE has no capturing group. "
          "If they differ, this script is wrong, not the original run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
