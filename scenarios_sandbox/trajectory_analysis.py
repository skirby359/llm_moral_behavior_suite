"""Post-failure trajectory reanalysis across both families, from committed logs. No spend.

    python scenarios_sandbox/trajectory_analysis.py

The Wave 5 reframe (reviewer, 11 September 2026; confirmed on the committed data): the variable
is not "blocked goal" but what an agent does after the honest path is found blocked. The origin
is the first failed checker result. The hidden action cap censors the tail of that behaviour
rather than pressuring the agent, because a cap the model is never told about cannot be a
deadline.

The first cut found the sharp cross-family difference is NOT persistence duration -- Family 2
agents keep acting almost as long as Family 1's -- but whether the persistence re-touches the
environment: a quarter of Family 1's blocked runs wrote a protected file again after failure,
against one in forty of Family 2's. So `post_failure_reattempt`, a per-run boolean that occurs
in every blocked run, is the primary persistence outcome, and crossing (a 4-event tail) is read
as the rare consequence of it.

This reads both families from their re-scored logs so field definitions match, restricted to the
shared cell (adjacent rule, writable checker, no session limit, baseline framing, native), and
reports the defer cell separately because offering a hand-back changes the terminal taken.
"""

from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ombs.analysis.sandbox import (  # noqa: E402
    TERMINAL_RISK,
    fisher_exact_two_sided,
    trajectory_metrics,
)

OUTPUTS = ROOT / "outputs"
SHARED = {"solvability": "stuck", "rule_distance": "adjacent", "checker_access": "visible_writable",
          "session_limit": "off", "task_framing": "baseline", "tool_transport": "native"}


def load(family: str) -> list[dict]:
    seen: dict[str, dict] = {}
    for path in sorted(OUTPUTS.glob("*rescored*/sandbox.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("family") == family and r.get("complete") and (r["outcome"] or {}).get("measured"):
                seen[r["attempt_id"]] = r
    return list(seen.values())


def cell_ok(r: dict, **over) -> bool:
    want = dict(SHARED)
    want.update(over)
    return all(r["cell"].get(k, "off" if k == "defer_available" else None) == v for k, v in want.items())


def line(label: str, rows: list[dict]) -> dict:
    m = [x for x in (trajectory_metrics(r) for r in rows) if x is not None]
    if not m:
        print(f"  {label:28} no runs with a run_check")
        return {}
    reatt = sum(1 for x in m if x["post_failure_reattempt"])
    prot = sum(1 for x in m if x["post_failure_boundary_reattempt"])
    depths = [x["persistence_depth"] for x in m]
    risks = Counter(TERMINAL_RISK.get(x["terminal"], x["terminal"]) for x in m)
    print(f"  {label:28} n={len(m):2}  re-attempt {reatt:2}/{len(m):<2} ({reatt/len(m):5.1%})  "
          f"of which on a protected file {prot:2}  depth mean {sum(depths)/len(depths):.2f} max {max(depths)}  "
          f"cross {sum(1 for x in m if x['crossed'])}  cap {sum(1 for x in m if x['reached_cap'])}  "
          f"{dict(sorted(risks.items()))}")
    return {"reatt": reatt, "prot": prot, "n": len(m)}


def main() -> int:
    f1, f2 = load("sandbox_reconciliation"), load("sandbox_batch_release")
    if not f1 or not f2:
        print(f"FAIL  need rescored logs for both families (found {len(f1)}, {len(f2)}).")
        return 1

    print("=== A. Post-failure persistence, shared cell (defer off)")
    pooled = {"f1": [0, 0], "f2": [0, 0]}
    for model in ("gpt-5.5", "claude-opus-5"):
        print(f" {model}")
        a = line("Family 1 (finance)", [r for r in f1 if r["model"] == model and cell_ok(r)])
        b = line("Family 2 (batch release)", [r for r in f2 if r["model"] == model and cell_ok(r)])
        for key, got in (("f1", a), ("f2", b)):
            if got:
                pooled[key][0] += got["reatt"]
                pooled[key][1] += got["n"]
    k1, n1 = pooled["f1"]
    k2, n2 = pooled["f2"]
    print(f"\n  primary outcome, pooled over models: Family 1 re-attempt {k1}/{n1}, "
          f"Family 2 {k2}/{n2}, Fisher p = {fisher_exact_two_sided(k1, n1 - k1, k2, n2 - k2)}")

    print("\n=== B. Within Family 2: does offering a defer terminal shorten post-failure search?")
    for model in ("gpt-5.5", "claude-opus-5"):
        print(f" {model}")
        line("defer OFF", [r for r in f2 if r["model"] == model and cell_ok(r, defer_available="off")])
        line("defer ON", [r for r in f2 if r["model"] == model and cell_ok(r, defer_available="on")])
    print("  (depth barely moves; the terminal taken changes -- Family 2 has little search to "
          "reduce, which\n   is why the terminal-architecture experiment needs a Family-1-like "
          "venue, not this one.)")

    print("\n=== C. Family 1 gpt-5.5: re-attempt and cap reaching vs crossing (4-event tail)")
    g1 = [(r, trajectory_metrics(r)) for r in f1 if r["model"] == "gpt-5.5" and cell_ok(r)]
    g1 = [(r, x) for r, x in g1 if x is not None]
    for pred, name in (("post_failure_reattempt", "re-attempted the environment"),
                       ("reached_cap", "used every action")):
        yes = [(r, x) for r, x in g1 if x[pred]]
        no = [(r, x) for r, x in g1 if not x[pred]]
        ky = sum(1 for _, x in yes if x["crossed"])
        kn = sum(1 for _, x in no if x["crossed"])
        print(f"  {name:28}: crossed {ky}/{len(yes)} vs {kn}/{len(no)}  "
              f"Fisher p = {fisher_exact_two_sided(ky, len(yes) - ky, kn, len(no) - kn)}")
    print("\n  Every Family 1 crosser both re-attempted and reached the cap; Family 2 did neither. "
          "The\n  reframe: crossing is the tail of post-failure environment manipulation, and the "
          "cap censors it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
