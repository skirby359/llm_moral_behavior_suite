"""Wave 6 confirmatory analysis, from the committed arm records. No model, no spend.

    uv run python scenarios_sandbox/wave6_analysis.py [--outputs outputs]

Builds `outputs/sandbox6_procurement_combined/` from the arm directories and prints every contrast
`PREREG_WAVE6_CONFIRMATORY.md` (and its Amendment 1) fixed in advance, using only estimators that
predate the wave:

  PRIMARY (confirmatory)   baseline - compliant-failure on `any_boundary_crossing`, Newcombe 95%
                           interval and a ONE-SIDED Fisher exact (direction pre-specified:
                           baseline > compliant-failure). `final_violation` reported beside it.
  CO-PRIMARY               post-failure re-attempt by arm, the pathway reported rather than
                           adjusted away (the Wave 3 correction).
  SECONDARY (amendment)    the authority-salience arm against both, and the two-pathway contrast.

The pilot (`sandbox6_procurement_pilot_gpt`) is the pre-registered elicitation gate. It is copied
into the combined directory so the record is in one place but is NEVER pooled into the baseline
arm: pooling the runs that qualified the family into the arm that estimates its rate is the
peeking the preregistration forbids. Every table below reads `run_id`, so the separation is
mechanical rather than remembered.
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ombs.analysis.sandbox import (  # noqa: E402
    build_sandbox_report,
    fisher_exact_two_sided,
    fisher_exact_two_sided_exact,
)
from ombs.scorers.discrimination import newcombe_diff_ci, wilson_ci  # noqa: E402

COMBINED = "sandbox6_procurement_combined"
ARMS = {
    "baseline": "sandbox6_procurement_baseline_gpt",
    "compliant_failure": "sandbox6_procurement_compliant_gpt",
    "authority_salience": "sandbox6_procurement_authority_gpt",
}
PILOT = "sandbox6_procurement_pilot_gpt"
FIELDS = ("crossings", "reattempt", "protected_reattempt")


def two_sided_fisher(a: int, b: int, c: int, d: int) -> float | None:
    """The committed 4-dp test, falling back to exact rational arithmetic when it rounds to 0,
    so a very small p is printed as the value the test gives rather than as 0 or as a bound the
    rounding cannot support."""
    p = fisher_exact_two_sided(a, b, c, d)
    if p == 0.0:
        return fisher_exact_two_sided_exact(a, b, c, d)
    return p


def one_sided_fisher(a: int, b: int, c: int, d: int) -> float | None:
    """Two-sided p halved, valid here because the pre-specified direction is the observed one and
    the table is 2x2 with the conservative two-sided sum. Printed as one-sided only when the
    observed difference runs the pre-specified way; otherwise the two-sided value is reported."""
    p = two_sided_fisher(a, b, c, d)
    return None if p is None else min(1.0, p / 2)


def _p(p: float) -> str:
    """Never print 0: below 1e-4 the value comes from the exact rational computation and is shown
    in scientific notation (the Wave 6 primary is about 4e-13 one-sided)."""
    return f"{p:.2e}" if p < 1e-4 else f"{p:.4g}"


def load_records(path: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_combined(outputs: pathlib.Path) -> pathlib.Path:
    out = outputs / COMBINED
    out.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    present = []
    for run in list(ARMS.values()) + [PILOT]:
        src = outputs / run / "sandbox.jsonl"
        if not src.exists():
            continue
        present.append(run)
        records.extend(load_records(src))
    if not records:
        raise SystemExit("no Wave 6 arm records found; run the arms first")
    (out / "sandbox.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")
    (out / "README.txt").write_text(
        "Combined records of " + ", ".join(present) + " (Wave 6, held-out confirmatory family "
        "sandbox_procurement_award, gpt-5.5, native, blocked cell). Built by "
        "scenarios_sandbox/wave6_analysis.py. The pilot's 10 runs are the pre-registered "
        "elicitation gate and are NOT pooled into the baseline arm; every table separates them by "
        "run_id and task_framing.\n", encoding="utf-8")
    for name in ("config.yaml", "git_commit.txt"):
        src = outputs / ARMS["baseline"] / name
        if src.exists():
            shutil.copy(src, out / f"baseline_{name}")
    build_sandbox_report(out / "sandbox.jsonl", out)
    return out


def arm_rows(outputs: pathlib.Path) -> dict[str, dict]:
    """One persistence row per arm, read from each arm's own report so the pilot cannot leak in."""
    rows: dict[str, dict] = {}
    for framing, run in ARMS.items():
        path = outputs / run / "persistence.csv"
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                if r["model"] == "gpt-5.5" and r["solvability"] == "stuck" and r["task_framing"] == framing:
                    rows[framing] = r
    path = outputs / PILOT / "persistence.csv"
    if path.exists():
        with path.open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                if r["model"] == "gpt-5.5" and r["solvability"] == "stuck":
                    rows["pilot"] = r
    return rows


def kn(row: dict, field: str) -> tuple[int, int]:
    return int(row[field]), int(row["n"])


def fmt(k: int, n: int) -> str:
    lo, hi = wilson_ci(k, n)
    return f"{k}/{n} = {k / n:.3f} [{lo:.3f}, {hi:.3f}]"


def contrast(label: str, a: tuple[int, int], b: tuple[int, int], *, one_sided: bool) -> None:
    (k1, n1), (k2, n2) = a, b
    ci = newcombe_diff_ci(k1, n1, k2, n2)
    if ci is None:
        print(f"  {label}: an arm has no runs; nothing to contrast")
        return
    lo, hi = ci
    two = two_sided_fisher(k1, n1 - k1, k2, n2 - k2)
    diff = k1 / n1 - k2 / n2
    if one_sided and diff > 0:
        p = one_sided_fisher(k1, n1 - k1, k2, n2 - k2)
        ptxt = f"one-sided Fisher p = {_p(p)}" if p is not None else "Fisher p = n/a"
    else:
        ptxt = f"two-sided Fisher p = {_p(two)}" if two is not None else "Fisher p = n/a"
        if one_sided:
            ptxt += "  (difference does not run the pre-specified way; two-sided reported)"
    print(f"  {label}: delta = {diff:+.3f}  Newcombe 95% [{lo:+.3f}, {hi:+.3f}]  {ptxt}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs", default=str(ROOT / "outputs"))
    args = ap.parse_args(argv)
    outputs = pathlib.Path(args.outputs)

    out = build_combined(outputs)
    print(f"combined report: {out.relative_to(ROOT).as_posix()}\n")
    rows = arm_rows(outputs)

    print("Wave 6 — held-out confirmatory family `sandbox_procurement_award`, gpt-5.5, blocked cell")
    print("(the pilot is the elicitation gate, reported for completeness and pooled into nothing)\n")
    print("  arm                     n   crossing                      re-attempt                    protected re-attempt")
    for key in ("pilot", "baseline", "compliant_failure", "authority_salience"):
        r = rows.get(key)
        if r is None:
            continue
        n = int(r["n"])
        cells = "  ".join(fmt(int(r[f]), n).ljust(28) for f in FIELDS)
        print(f"  {key:<22} {n:>3}  {cells}")
    print()

    base, comp = rows.get("baseline"), rows.get("compliant_failure")
    if base and comp:
        print("PRIMARY (confirmatory): baseline - compliant-failure on any_boundary_crossing")
        contrast("crossing", kn(base, "crossings"), kn(comp, "crossings"), one_sided=True)
        print("CO-PRIMARY: post-failure re-attempt, the pathway reported beside the effect")
        contrast("re-attempt", kn(base, "reattempt"), kn(comp, "reattempt"), one_sided=False)
        contrast("protected re-attempt", kn(base, "protected_reattempt"),
                 kn(comp, "protected_reattempt"), one_sided=False)
        print()

    auth = rows.get("authority_salience")
    if auth and base and comp:
        print("SECONDARY (Amendment 1): the authority-salience arm")
        contrast("crossing, authority vs baseline", kn(auth, "crossings"), kn(base, "crossings"),
                 one_sided=False)
        contrast("crossing, authority vs compliant", kn(auth, "crossings"), kn(comp, "crossings"),
                 one_sided=False)
        print("  the two-pathway contrast (Wave 5 expectation: authority keeps the search, compliant ends it)")
        contrast("re-attempt, authority vs baseline", kn(auth, "reattempt"), kn(base, "reattempt"),
                 one_sided=False)
        contrast("re-attempt, authority vs compliant", kn(auth, "reattempt"), kn(comp, "reattempt"),
                 one_sided=False)
        contrast("protected re-attempt, authority vs baseline", kn(auth, "protected_reattempt"),
                 kn(base, "protected_reattempt"), one_sided=False)
        print()

    print("Terminals and routes by arm (from each arm's own report):")
    for key in ("pilot", "baseline", "compliant_failure", "authority_salience"):
        r = rows.get(key)
        if r is None:
            continue
        print(f"  {key:<22} terminals {r['terminals']}  mean post-failure depth {r['depth_mean']}")
    for framing, run in ARMS.items():
        path = outputs / run / "routes.csv"
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                print(f"  {framing:<22} routes {r['routes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
