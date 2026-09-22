from pathlib import Path

import pytest

from ombs.scenario_loader import ScenarioError, load_scenarios_from_dir, select_scenarios

SCENARIO_DIR = Path(__file__).resolve().parents[1] / "scenarios" / "administrative"


def test_loads_all_bundled_scenarios():
    scenarios = load_scenarios_from_dir(SCENARIO_DIR)
    assert len(scenarios) == 10
    for s in scenarios:
        assert len(s.variants) == 6
        assert s.scoring.primary_boundary


def test_select_by_id_preserves_order():
    ids = ["unapproved_external_email", "client_delay_disclosure"]
    selected = select_scenarios(scenario_dir=SCENARIO_DIR, scenario_ids=ids)
    assert [s.id for s in selected] == ids


def test_missing_id_raises():
    with pytest.raises(ScenarioError):
        select_scenarios(scenario_dir=SCENARIO_DIR, scenario_ids=["does_not_exist"])


def test_invalid_yaml_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("id: x\ncategory: administrative\n", encoding="utf-8")  # missing fields
    with pytest.raises(ScenarioError):
        load_scenarios_from_dir(tmp_path)


def test_duplicate_variant_ids_rejected(tmp_path):
    dupe = tmp_path / "dupe.yaml"
    dupe.write_text(
        "id: d\ncategory: c\ntitle: t\nrole: r\n"
        "base_facts: f\npolicy_context: p\nexpected_boundary: b\n"
        "variants:\n"
        "  - {id: neutral, pressure_type: neutral, user_message: a}\n"
        "  - {id: neutral, pressure_type: authority, user_message: b}\n"
        "scoring: {primary_boundary: x}\n",
        encoding="utf-8",
    )
    with pytest.raises(ScenarioError):
        load_scenarios_from_dir(tmp_path)
