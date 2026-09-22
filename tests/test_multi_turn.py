from pathlib import Path

from ombs.scenario_loader import load_scenarios_from_dir
from ombs.scorers.multi_turn import boundary_survival_depth, pushback_failure_rate

MT_DIR = Path(__file__).resolve().parents[1] / "scenarios" / "administrative"


def test_multi_turn_scenarios_load_with_pushback():
    scenarios = load_scenarios_from_dir(MT_DIR)
    with_pushback = [s for s in scenarios if s.pushback_sequence]
    assert len(with_pushback) == 10
    for s in with_pushback:
        assert len(s.pushback_sequence) == 5
        assert s.pushback_sequence[-1].pressure_type == "responsibility"
        assert s.opening_message().strip()


def test_boundary_survival_depth():
    assert boundary_survival_depth([True, True, True, True]) == 4
    assert boundary_survival_depth([True, True, False, True]) == 2
    assert boundary_survival_depth([False, True, True]) == 0
    assert boundary_survival_depth([]) == 0


def _conv(opening_ok, pushback_flags):
    turns = [{"boundary_preserved": opening_ok}]
    turns += [{"boundary_preserved": f} for f in pushback_flags]
    return {"turns": turns}


def test_pushback_failure_rate():
    records = [
        _conv(True, [True, True, True, True]),   # held -> not a failure
        _conv(True, [True, False, False, False]),  # eroded -> failure
        _conv(False, [False, False, False, False]),  # never started safe -> excluded
    ]
    # eligible = 2 (started safe), failures = 1
    assert pushback_failure_rate(records) == 0.5


def test_pushback_failure_rate_empty():
    assert pushback_failure_rate([]) == 0.0
