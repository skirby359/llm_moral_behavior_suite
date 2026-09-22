"""The exposure-matched cross-family comparison, and the double-count it must not make.

The rescored output directories overlap by design: one holds the frozen cells, another holds
every run of the same family. A loader that concatenates them counts each shared run twice,
which halves every hazard while leaving arithmetic that looks perfectly reasonable -- the first
version of this script reported 8 crossings in 66 runs where the published figure is 4 in 36.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cfh", ROOT / "scenarios_sandbox" / "cross_family_hazard.py")
cfh = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cfh)


def rec(attempt: str, *, family="fam", model="m", steps=12, first=None, **cell) -> dict:
    c = dict(cfh.CELL)
    c.update(cell)
    return {
        "attempt_id": attempt, "family": family, "model": model, "complete": True, "cell": c,
        "outcome": {"measured": True, "steps_used": steps, "first_violation_step": first,
                    "any_boundary_crossing": first is not None},
    }


def _write(dir_path: Path, rows: list[dict]) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "sandbox.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


@pytest.fixture
def outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(cfh, "OUTPUTS", tmp_path)
    return tmp_path


def test_overlapping_rescored_directories_are_not_counted_twice(outputs):
    rows = [rec(f"a{i}", first=9 if i == 0 else None) for i in range(4)]
    _write(outputs / "all_rescored", rows)
    _write(outputs / "frozen_rescored", rows[:2])  # a deliberate subset, as the repo has
    loaded = cfh.load("fam")
    assert len(loaded) == 4
    assert sorted(r["attempt_id"] for r in loaded) == ["a0", "a1", "a2", "a3"]


def test_only_the_shared_cell_and_measured_complete_runs_are_loaded(outputs):
    _write(outputs / "x_rescored", [
        rec("keep"),
        rec("other_cell", solvability="solvable"),
        rec("other_transport", tool_transport="json_schema"),
        {**rec("incomplete"), "complete": False},
        {**rec("unmeasured"), "outcome": {"measured": False, "steps_used": 3, "first_violation_step": None}},
        rec("other_family", family="elsewhere"),
    ])
    assert [r["attempt_id"] for r in cfh.load("fam")] == ["keep"]


def test_hazards_release_a_run_from_the_risk_set_after_its_crossing(outputs):
    rows = [rec("a", first=3, steps=6)] + [rec(f"b{i}", steps=6) for i in range(3)]
    h = cfh.hazards(rows, 6)
    assert h[1] == (0, 4) and h[3] == (1, 4)
    assert h[4] == (0, 3), "the crossed run is no longer at risk of a first crossing"
    assert h[6] == (0, 3)


def test_a_run_that_ended_early_is_not_at_risk_afterwards(outputs):
    rows = [rec("short", steps=4), rec("long", steps=12)]
    h = cfh.hazards(rows, 12)
    assert h[4] == (0, 2) and h[5] == (0, 1)


def test_a_factor_added_after_a_family_was_frozen_does_not_drop_that_family(outputs):
    """Family 1 predates `defer_available`, so its records do not carry it.

    A plain equality test on the cell would exclude every frozen record and leave a script that
    runs, prints, and compares nothing -- the failure mode that looks like success.
    """
    frozen_cell = {k: v for k, v in cfh.CELL.items() if k != "defer_available"}
    assert cfh.in_cell(frozen_cell), "a pre-factor record must still match the cell"
    assert cfh.in_cell(dict(cfh.CELL))
    assert not cfh.in_cell({**cfh.CELL, "defer_available": "on"}), (
        "the defer cell offers an extra terminal and is not the same cell"
    )


def test_the_defer_cell_is_excluded_from_the_matched_comparison(outputs):
    _write(outputs / "x_rescored", [
        rec("core1"), rec("core2"),
        rec("defer1", defer_available="on"), rec("defer2", defer_available="on"),
    ])
    assert sorted(r["attempt_id"] for r in cfh.load("fam")) == ["core1", "core2"]
