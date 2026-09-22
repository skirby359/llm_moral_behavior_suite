"""Wave 7 domain-effect analysis, from the committed arm records. No model, no spend.

    uv run python scenarios_sandbox/wave7_analysis.py [--outputs outputs]
    make wave7

Prints exactly the contrasts PREREG_WAVE7_DOMAIN_EFFECT.md fixed: each variant against its
anchor's COMMITTED Wave 5 baseline arm (read from that arm's own directory, never re-sampled and
never pooled), a one-sided Fisher exact in the pre-specified direction with a Newcombe interval,
Holm-adjusted p beside the raw values, the pre-registered pattern classification, and the
co-readouts (re-attempt, protected re-attempt, depth, terminals, routes). It also checks that the
vendor-reported model id (`model_digest`) is the same across anchor and variant runs, since the
contrast is cross-wave.

The interpretation is frozen in the preregistration and repeated here: Wave 7 identifies context
features associated with elicitation; it does not identify a psychological mechanism.
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ombs.analysis.sandbox import (  # noqa: E402
    build_sandbox_report,
    fisher_exact_two_sided,
    fisher_exact_two_sided_exact,
)
from ombs.scorers.discrimination import newcombe_diff_ci, wilson_ci  # noqa: E402

COMBINED = "sandbox7_domain_effect_combined"
#: label -> (run directory, family). Order is the preregistered running order.
VARIANTS = {
    "V3": ("sandbox7_contract_goal_swap_gpt", "sandbox_contract_goal_swap"),
    "V1": ("sandbox7_grant_goal_swap_gpt", "sandbox_grant_goal_swap"),
    "V4": ("sandbox7_contract_party_swap_gpt", "sandbox_contract_party_swap"),
    "V2": ("sandbox7_grant_party_swap_gpt", "sandbox_grant_party_swap"),
}
ANCHORS = {
    "grant": ("sandbox5_grant_baseline_gpt", "sandbox_grant_disbursement"),
    "contract": ("sandbox5_contract_baseline_gpt", "sandbox_contract_execution"),
}
#: contrast -> (high arm, low arm, dimension); direction pre-specified as high > low.
CONTRASTS = {
    "C1": ("V1", "grant", "G"),
    "C2": ("V2", "grant", "P"),
    "C3": ("contract", "V3", "G"),
    "C4": ("contract", "V4", "P"),
}
FIELDS = ("crossings", "reattempt", "protected_reattempt")
FROZEN_INTERPRETATION = ("Wave 7 identifies context features associated with elicitation; "
                         "it does not identify a psychological mechanism.")


def two_sided_fisher(a: int, b: int, c: int, d: int) -> float | None:
    """The committed 4-dp test, exact rational arithmetic when it rounds to 0 (wave6 convention)."""
    p = fisher_exact_two_sided(a, b, c, d)
    if p == 0.0:
        return fisher_exact_two_sided_exact(a, b, c, d)
    return p


def one_sided_fisher(a: int, b: int, c: int, d: int) -> float | None:
    p = two_sided_fisher(a, b, c, d)
    return None if p is None else min(1.0, p / 2)


def _p(p: float | None) -> str:
    if p is None:
        return "n/a"
    return f"{p:.2e}" if p < 1e-4 else f"{p:.4g}"


def holm(pvals: dict[str, float], alpha: float = 0.05) -> dict[str, tuple[float, bool]]:
    """Holm step-down: returns {name: (adjusted p, rejected at alpha)}."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    out: dict[str, tuple[float, bool]] = {}
    running = 0.0
    stop = False
    for i, (name, p) in enumerate(items):
        adj = min(1.0, (m - i) * p)
        running = max(running, adj)
        rejected = (not stop) and running <= alpha
        if not rejected:
            stop = True
        out[name] = (running, rejected)
    return out


def classify(sig: dict[str, bool]) -> str:
    """The preregistered pattern rule over the four one-sided tests (raw p < 0.05, predicted
    direction). A dimension is a driver only if BOTH its variants move."""
    g = sig.get("C1", False) and sig.get("C3", False)
    p = sig.get("C2", False) and sig.get("C4", False)
    any_g = sig.get("C1", False) or sig.get("C3", False)
    any_p = sig.get("C2", False) or sig.get("C4", False)
    if g and p:
        return "both"
    if g and not any_p:
        return "G-driver"
    if p and not any_g:
        return "P-driver"
    if not any_g and not any_p:
        return "neither"
    return "asymmetric"


def _read_rows(path: pathlib.Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def arm_row(outputs: pathlib.Path, run_dir: str, family: str) -> dict | None:
    """The baseline blocked-cell persistence row of ONE run directory, matched on family so a
    directory carrying another family's row is not accepted."""
    path = outputs / run_dir / "persistence.csv"
    if not path.exists():
        return None
    for r in _read_rows(path):
        if (r["model"] == "gpt-5.5" and r["solvability"] == "stuck" and r["family"] == family
                and r["task_framing"] == "baseline" and r["defer_available"] == "off"):
            return r
    return None


def kn(row: dict, field: str) -> tuple[int, int]:
    return int(row[field]), int(row["n"])


def fmt(k: int, n: int) -> str:
    lo, hi = wilson_ci(k, n)
    return f"{k}/{n} = {k / n:.3f} [{lo:.3f}, {hi:.3f}]"


def model_digests(outputs: pathlib.Path, run_dir: str) -> set[str]:
    path = outputs / run_dir / "sandbox.jsonl"
    if not path.exists():
        return set()
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line).get("model_digest")
            if d:
                out.add(d)
    return out


def routes(outputs: pathlib.Path, run_dir: str) -> str:
    path = outputs / run_dir / "routes.csv"
    if not path.exists():
        return "-"
    rows = _read_rows(path)
    return "; ".join(r["routes"] for r in rows) or "-"


def build_combined(outputs: pathlib.Path, present: list[str]) -> pathlib.Path | None:
    """Pool the VARIANT runs only into one report directory. The anchors are never copied in:
    they are Wave 5 arms and stay in their own directories."""
    if not present:
        return None
    out = outputs / COMBINED
    out.mkdir(parents=True, exist_ok=True)
    records: list[str] = []
    for run in present:
        records += [ln for ln in (outputs / run / "sandbox.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    (out / "sandbox.jsonl").write_text("\n".join(records) + "\n", encoding="utf-8")
    (out / "README.txt").write_text(
        "Combined records of the Wave 7 variant runs " + ", ".join(present) + " (gpt-5.5, baseline, blocked cell). "
        "Built by scenarios_sandbox/wave7_analysis.py. The anchors (sandbox5_grant_baseline_gpt, "
        "sandbox5_contract_baseline_gpt) are read from their own Wave 5 directories and are NOT pooled here.\n",
        encoding="utf-8")
    build_sandbox_report(out / "sandbox.jsonl", out)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs", default=str(ROOT / "outputs"))
    args = ap.parse_args(argv)
    outputs = pathlib.Path(args.outputs)

    rows: dict[str, dict] = {}
    for key, (run_dir, family) in {**ANCHORS, **VARIANTS}.items():
        r = arm_row(outputs, run_dir, family)
        if r is not None:
            rows[key] = r
    present = [VARIANTS[k][0] for k in VARIANTS if k in rows]
    out = build_combined(outputs, present)
    if out is not None:
        print(f"combined report (variants only): {out.relative_to(ROOT).as_posix()}\n")

    print("Wave 7 — domain-effect minimal pairs, gpt-5.5, baseline, blocked cell")
    print(f"({FROZEN_INTERPRETATION})\n")
    print("  arm         n   crossing                      re-attempt                    protected re-attempt          depth")
    for key in ("grant", "V1", "V2", "contract", "V3", "V4"):
        r = rows.get(key)
        if r is None:
            print(f"  {key:<10} not run")
            continue
        n = int(r["n"])
        cells = "  ".join(fmt(int(r[f]), n).ljust(28) for f in FIELDS)
        print(f"  {key:<10} {n:>3}  {cells}  {r['depth_mean']}")
    print()

    digests: dict[str, set[str]] = {k: model_digests(outputs, d) for k, (d, _) in {**ANCHORS, **VARIANTS}.items()}
    seen = {k: v for k, v in digests.items() if v}
    if seen:
        all_ids = set().union(*seen.values())
        flag = "" if len(all_ids) == 1 else "  !! vendor model id differs across arms — the cross-wave contrast is not like-for-like"
        print(f"model_digest across arms: {sorted(all_ids)}{flag}\n")

    raw_p: dict[str, float] = {}
    sig: dict[str, bool] = {}
    print("CONTRASTS (pre-specified direction high > low; one-sided Fisher; Newcombe 95%)")
    for name, (hi, lo, dim) in CONTRASTS.items():
        if hi not in rows or lo not in rows:
            print(f"  {name} ({dim}): {hi} vs {lo} — not yet run")
            continue
        (k1, n1), (k2, n2) = kn(rows[hi], "crossings"), kn(rows[lo], "crossings")
        ci = newcombe_diff_ci(k1, n1, k2, n2)
        diff = k1 / n1 - k2 / n2
        if diff > 0:
            p = one_sided_fisher(k1, n1 - k1, k2, n2 - k2)
            ptxt = f"one-sided p = {_p(p)}"
        else:
            p = two_sided_fisher(k1, n1 - k1, k2, n2 - k2)
            ptxt = f"two-sided p = {_p(p)} (difference does not run the pre-specified way)"
        raw_p[name] = 1.0 if p is None else p
        sig[name] = diff > 0 and p is not None and p < 0.05
        lo_ci, hi_ci = ci if ci else (float("nan"), float("nan"))
        print(f"  {name} ({dim}): {hi} {k1}/{n1} vs {lo} {k2}/{n2}: delta = {diff:+.3f} [{lo_ci:+.3f}, {hi_ci:+.3f}]  {ptxt}")
    if raw_p:
        adj = holm(raw_p)
        print("  Holm-adjusted (reported beside, does not alter the rule): " +
              ", ".join(f"{k}: {_p(v[0])}{' *' if v[1] else ''}" for k, v in sorted(adj.items())))
        complete = all(name in raw_p for name in CONTRASTS)
        pattern = classify(sig)
        print(f"\nPATTERN: {pattern}" + ("" if complete else "  (incomplete: not all four contrasts have run; read completed pairs only)"))
    print()
    print("Routes by arm:")
    for key in ("V3", "V1", "V4", "V2"):
        if key in rows:
            print(f"  {key}: {routes(outputs, VARIANTS[key][0])}   terminals {rows[key]['terminals']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
