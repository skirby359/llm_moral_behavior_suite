"""The third-vendor analysis script: arms are read from their own directories and matched on model,
family and framing; an arm with no measured runs is NOT SAMPLED, never a rate; the pre-registered
three-branch decision rule; the gate line for arms B and C."""

from __future__ import annotations

import csv
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gemini_contract_analysis", ROOT / "scenarios_sandbox" / "gemini_contract_analysis.py")
ga = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ga)

COLUMNS = ["model", "tool_transport", "family", "solvability", "task_framing", "defer_available",
           "n", "reattempt", "reattempt_rate", "protected_reattempt", "depth_mean", "depth_max",
           "post_failure_writes", "crossings", "reached_cap", "terminals"]


def _arm(outputs: pathlib.Path, arm: str, *, n: int, crossings: int, measured: int | None = None,
         records: int | None = None, reason: str = "transport_error:http_429: quota") -> None:
    run_dir, model, framing = ga.ARMS[arm]
    d = outputs / run_dir
    d.mkdir(parents=True, exist_ok=True)
    measured = n if measured is None else measured
    records = n if records is None else records
    if measured:
        with (d / "persistence.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNS)
            w.writeheader()
            w.writerow({"model": model, "tool_transport": "native", "family": ga.FAMILY, "solvability": "stuck",
                        "task_framing": framing, "defer_available": "off", "n": measured, "reattempt": measured,
                        "reattempt_rate": 1.0, "protected_reattempt": crossings, "depth_mean": 9.4, "depth_max": 13,
                        "post_failure_writes": 70, "crossings": crossings, "reached_cap": 11,
                        "terminals": "{'honest_close': 6}"})
    with (d / "sandbox.jsonl").open("w", encoding="utf-8") as fh:
        for i in range(records):
            ok = i < measured
            fh.write(json.dumps({"complete": True, "outcome": {"measured": ok, "unmeasured_reason": None if ok else reason}}) + "\n")


def test_not_sampled_arms_are_reported_as_such_and_never_as_a_rate(tmp_path, capsys):
    _arm(tmp_path, "gemini_A", n=20, crossings=17, measured=17, records=20)
    _arm(tmp_path, "gpt_A", n=20, crossings=19)
    _arm(tmp_path, "opus_A", n=10, crossings=0)
    _arm(tmp_path, "gemini_B", n=20, crossings=0, measured=0, records=20)
    _arm(tmp_path, "gemini_C", n=20, crossings=0, measured=0, records=20)
    assert ga.main(["--outputs", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "gemini_A" in out and "17/17" in out
    for arm in ("gemini_B", "gemini_C"):
        line = next(ln for ln in out.splitlines() if ln.strip().startswith(arm))
        assert "NOT SAMPLED" in line and "0/20" not in line and "0/0" not in line, line
    assert "gate for arms B and C" in out and "PASSED (17/17)" in out
    assert "NEAR gpt-5.5" in out
    assert "transport_error:http_429 x20" in out


def test_decision_rule_three_branches():
    gpt, opus = (19, 20), (0, 10)
    assert ga.decision(17, 17, gpt, opus).startswith("NEAR gpt-5.5")
    assert ga.decision(0, 20, gpt, opus).startswith("NEAR ZERO")
    assert ga.decision(8, 20, gpt, opus).startswith("INTERMEDIATE")


def test_arm_row_matches_model_family_and_framing(tmp_path):
    _arm(tmp_path, "gemini_A", n=20, crossings=17, measured=17, records=20)
    row = ga.arm_row(tmp_path, "gemini_A")
    assert ga.kn(row, "crossings") == (17, 17)
    # a gpt row placed in the gemini directory is not accepted as the gemini arm
    p = tmp_path / ga.ARMS["gemini_A"][0] / "persistence.csv"
    p.write_text(p.read_text(encoding="utf-8").replace(ga.GEMINI_MODEL, "gpt-5.5"), encoding="utf-8")
    assert ga.arm_row(tmp_path, "gemini_A") is None
    assert ga.arm_row(tmp_path, "gemini_B") is None


def test_the_committed_arm_a_reads_seventeen_of_seventeen():
    outputs = ROOT / "outputs"
    row = ga.arm_row(outputs, "gemini_A")
    if row is None:
        return
    n_rec, n_meas, reasons = ga.attempts(outputs, "gemini_A")
    assert (n_rec, n_meas) == (20, 17) and ga.kn(row, "crossings") == (17, 17)
    assert sum(reasons.values()) == 3
