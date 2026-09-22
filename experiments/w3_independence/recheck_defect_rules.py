"""Re-derive stored runs' defect matches with the CURRENT rules — no API calls.

Ground-truth rules get edited. When they do, every figure already published from a
stored run was computed with the old rules, and the only honest way to know whether a
number moved is to re-derive it from the stored findings rather than to reason about
whether the edit "should" matter.

Written for one specific edit: `X20_payment_terms` was `(45|forty-five)` with no word
boundary, so it matched the "45" inside any longer number. That was invisible until the
15-document corpus introduced a £1,450 day rate. The rule is now anchored; this script
checks what that did to the 4- and 9-document results.

    python experiments/w3_independence/recheck_defect_rules.py

Prints stored vs recomputed per-call recall for every cross-document run. Any
difference is a figure that needs correcting wherever it was published.
"""

from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_w3  # noqa: E402
from defects_xdoc import DEFECTS_XDOC  # noqa: E402
from defects_xdoc_ext import DEFECTS_XDOC_EXT  # noqa: E402
from defects_xdoc_ext2 import DEFECTS_XDOC_EXT2  # noqa: E402

CORPORA = {
    "_xdoc_": list(DEFECTS_XDOC),
    "_xdoc9_": list(DEFECTS_XDOC) + list(DEFECTS_XDOC_EXT),
    "_xdoc15_": list(DEFECTS_XDOC) + list(DEFECTS_XDOC_EXT) + list(DEFECTS_XDOC_EXT2),
}


def main() -> int:
    files = sorted(
        p for p in HERE.glob("variance_*.json")
        if not p.name.endswith(".sections_recomputed.json")
    )
    drift = 0
    checked = 0

    for path in files:
        defects = next((d for tag, d in CORPORA.items() if tag in path.name), None)
        if defects is None:
            continue  # single-document run, different ground truth
        run_w3.DEFECTS = defects
        data = json.loads(path.read_text(encoding="utf-8"))
        print(f"\n=== {path.name}  ({len(defects)} defects in scope)")
        for rep in data.get("per_repeat", []):
            stored = rep["analysis"]["per_call_recall"]
            redone = []
            for r in rep.get("runs", []):
                # Skip non-measurements, because `analyse()` excludes them from
                # per_call_recall. Comparing over all runs against a stored array that
                # excludes them reports every affected repeat as CHANGED purely from a
                # length mismatch -- a false alarm this script raised on itself once the
                # exclusion landed.
                failed = r.get("failed")
                if failed is None:
                    failed = run_w3.is_failed_call(r.get("raw", ""))
                if failed:
                    continue
                matched, _ = run_w3.match_defects(r.get("findings", []))
                redone.append(len(matched))
            checked += 1
            same = stored == redone
            print(f"  repeat {rep.get('repeat')}: {'unchanged' if same else 'CHANGED'}")
            if not same:
                drift += 1
                print(f"      stored     {stored}")
                print(f"      recomputed {redone}")

    print(f"\n{checked} repeat(s) re-derived with the current rules.")
    print("NO PUBLISHED FIGURE MOVED" if not drift else
          f"{drift} repeat(s) CHANGED -- correct every figure derived from them")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
