"""Is Family 2's zero a non-replication, or just less exposure than Family 1 had?

    python scenarios_sandbox/cross_family_hazard.py

A raw "0 of 21 against 4 of 30" compares two numbers that were not measured over the same
actions. Family 1's crossings all fell at actions 9-12; if Family 2's runs had ended at action 8
its zero would mean nothing at all. This script answers the only version of the question the
data can support:

    under Family 1's own per-action hazard, how many crossings should Family 2's exposure have
    produced, and how likely is zero?

Both families are read from their rescored records so the field definitions match. Family 1 is
frozen; re-deriving outcomes from its committed logs is analysis, not sampling. Nothing here
calls a model.

The comparison is restricted to the cell the two families share -- stuck, adjacent rule,
writable checker, no rendered session limit, baseline framing, native transport -- and is
truncated at action 12, the smaller family's cap, exactly as the pre-run record fixed.

**Read the whole output, not the per-action line.** An internal audit on 11 September found
that the per-action figure is the most favourable of several defensible specifications: it
counts every at-risk action as an equal opportunity, including each run's own terminating
`done`, which cannot be a crossing. The run-level binomial and the Fisher exact are printed
beside it for that reason. Where they disagree, the honest summary is the range, not the
smallest number in it.

It also prints the **cap stratification**, which the first version of this script omitted and
which is the strongest association in the committed data: in Family 1's shared cell every
crossing came from a run that used all of its actions.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ombs.analysis.sandbox import (  # noqa: E402
    CROSS_FAMILY_TRUNCATION,
    fisher_exact_two_sided,
)

OUTPUTS = ROOT / "outputs"
CELL = {"solvability": "stuck", "rule_distance": "adjacent", "checker_access": "visible_writable",
        "session_limit": "off", "task_framing": "baseline", "defer_available": "off",
        "tool_transport": "native"}

#: Factors added after a family was frozen are absent from its records, and a plain equality
#: test would then silently drop that family from the comparison entirely -- leaving a script
#: that runs, prints, and compares nothing. The value each factor had before it existed is the
#: level the runs were in fact at.
IMPLIED_BEFORE_THE_FACTOR_EXISTED = {"defer_available": "off"}


def in_cell(cell: dict) -> bool:
    for key, want in CELL.items():
        got = cell.get(key, IMPLIED_BEFORE_THE_FACTOR_EXISTED.get(key))
        if got != want:
            return False
    return True


def load(family: str) -> list[dict]:
    """Every rescored record for a family, so both sides carry the same field definitions.

    Deduplicated by `attempt_id`: the rescored directories overlap on purpose (one holds the
    frozen cells, another holds every run), and counting a run twice halves every hazard while
    leaving the arithmetic looking perfectly reasonable.
    """
    seen: dict[str, dict] = {}
    for path in sorted(OUTPUTS.glob("*rescored*/sandbox.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("family") != family or not r.get("complete"):
                continue
            if not (r.get("outcome") or {}).get("measured"):
                continue
            if in_cell(r["cell"]):
                seen[r["attempt_id"]] = r
    return list(seen.values())


def hazards(rows: list[dict], horizon: int) -> dict[int, tuple[int, int]]:
    """action -> (crossings at that action, runs still at risk at that action)."""
    out: dict[int, tuple[int, int]] = {}
    for k in range(1, horizon + 1):
        at_risk = [r for r in rows
                   if r["outcome"]["steps_used"] >= k
                   and (r["outcome"]["first_violation_step"] or 10**9) >= k]
        events = [r for r in at_risk if r["outcome"]["first_violation_step"] == k]
        out[k] = (len(events), len(at_risk))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", default="sandbox_reconciliation")
    ap.add_argument("--family", default="sandbox_batch_release")
    ap.add_argument("--truncate-at", type=int, default=CROSS_FAMILY_TRUNCATION)
    ap.add_argument("--min-reference", type=int, default=10,
                    help="smallest reference arm a hazard may be estimated from (default 10)")
    args = ap.parse_args()

    ref_rows, new_rows = load(args.reference), load(args.family)
    if not ref_rows or not new_rows:
        print(f"FAIL  need rescored records for both families; found {len(ref_rows)} and {len(new_rows)}.")
        print("      Run scenarios_sandbox/rescore_family1.py --family <f> --write outputs/<f>_rescored")
        return 1

    by_model: dict[str, dict[str, list[dict]]] = defaultdict(dict)
    for label, rows in (("reference", ref_rows), ("family", new_rows)):
        for r in rows:
            by_model[r["model"]].setdefault(label, []).append(r)

    k = args.truncate_at
    print(f"=== exposure-matched comparison, truncated at action {k}")
    print(f"    reference {args.reference} -> {args.family}")
    print(f"    cell: {', '.join(f'{a}={b}' for a, b in CELL.items())}\n")

    any_row = False
    for model in sorted(by_model):
        ref = by_model[model].get("reference", [])
        new = by_model[model].get("family", [])
        if not ref or not new:
            print(f"  {model}: no paired arms (reference {len(ref)}, {args.family} {len(new)}); skipped")
            continue
        if len(ref) < args.min_reference:
            # A single reference run that happened to cross gives a hazard of 1.0 and an
            # "expected" count that is arithmetic, not evidence. Refuse it rather than print it.
            print(f"  {model}: reference arm has {len(ref)} run(s), fewer than "
                  f"{args.min_reference}; no hazard can be estimated from it, skipped\n")
            continue
        any_row = True
        h_ref, h_new = hazards(ref, k), hazards(new, k)
        expected = 0.0
        p_zero = 1.0
        lines = []
        for action in range(1, k + 1):
            ev, at_risk_ref = h_ref[action]
            _, at_risk_new = h_new[action]
            hazard = ev / at_risk_ref if at_risk_ref else 0.0
            expected += hazard * at_risk_new
            p_zero *= (1 - hazard) ** at_risk_new
            if ev or hazard:
                lines.append(f"      action {action:2}: reference hazard {ev}/{at_risk_ref} = {hazard:.4f}"
                             f" | {args.family} at risk {at_risk_new}")
        observed = sum(1 for r in new
                       if (r["outcome"]["first_violation_step"] or 10**9) <= k)
        ref_obs = sum(1 for r in ref if (r["outcome"]["first_violation_step"] or 10**9) <= k)
        print(f"  {model}")
        print(f"    reference: {ref_obs} crossing(s) in {len(ref)} runs within {k} actions")
        for line in lines:
            print(line)
        print(f"    {args.family}: {observed} crossing(s) in {len(new)} runs, "
              f"{sum(h_new[a][1] for a in range(1, k + 1))} at-risk actions")
        print("    -- the band, not a number --")
        print(f"    per-action hazard    : expected {expected:.2f}  P(0) {p_zero:.3f}")
        rate = ref_obs / len(ref)
        print(f"    run-level binomial   : expected {rate * len(new):.2f}  "
              f"P(0) {(1 - rate) ** len(new):.3f}")
        print(f"    Fisher exact, {ref_obs}/{len(ref)} vs {observed}/{len(new)}"
              f"{'':<{max(0, 9 - len(str(ref_obs)) - len(str(len(ref))))}}: "
              f"p = {fisher_exact_two_sided(ref_obs, len(ref) - ref_obs, observed, len(new) - observed)}")
        # The cap stratification. Family 1's crossings are concentrated in runs that ran out of
        # actions; Family 2's runs stopped voluntarily with actions to spare. The two families
        # were run at different caps, which the first write-up did not list as a confound.
        for label, rs in ((args.reference, ref), (args.family, new)):
            capped = [r for r in rs if r["outcome"]["steps_used"] >= (r.get("technical_step_cap") or 0)]
            early = [r for r in rs if r not in capped]
            kc = sum(1 for r in capped if (r["outcome"]["first_violation_step"] or 10**9) <= k)
            ke = sum(1 for r in early if (r["outcome"]["first_violation_step"] or 10**9) <= k)
            caps = sorted({r.get("technical_step_cap") for r in rs})
            print(f"    {label}: cap {caps} | used every action {kc}/{len(capped)} crossed"
                  f" | stopped earlier {ke}/{len(early)} crossed"
                  f" | p = {fisher_exact_two_sided(kc, len(capped) - kc, ke, len(early) - ke)}")
        if ref_obs == 0:
            print("    the reference arm has no crossings either, so this bounds nothing")
        print()

    if not any_row:
        print("  no model appears in both families; nothing to compare")
        return 1
    print("A per-action hazard from a handful of events is itself imprecise; this compares "
          "exposure,\nnot effects, and none of these numbers is a confirmatory estimate. Quote the "
          "range.\nTwo coverage gaps this script cannot see: the reference family's strongest arm "
          "was a\ndifferent tool transport that the compared family never ran, and the two "
          "families ran at\ndifferent action caps.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
