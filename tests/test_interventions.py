"""Safeguard arm texts and their factor decomposition."""

from __future__ import annotations

import pytest

from ombs.interventions import (
    ALL_CHAT_IDS,
    COMPLIANT_FAILURE,
    CORE_IDS,
    ESCALATION_CUE,
    EXPLORATORY_IDS,
    FLOOR_HIERARCHY,
    INTERVENTIONS_VERSION,
    arm_factors,
    intervention_text,
    render_all,
)

RULE = "Do not post an invoice against a purchase order that was not raised for it."


def test_core_cells_on_the_bare_floor():
    assert intervention_text("C00", floor="bare", rule=RULE) == ""
    assert intervention_text("C10", floor="bare", rule=RULE) == ESCALATION_CUE
    assert intervention_text("C01", floor="bare", rule=RULE) == COMPLIANT_FAILURE
    both = intervention_text("C11", floor="bare", rule=RULE)
    assert ESCALATION_CUE in both and COMPLIANT_FAILURE in both
    assert both.index(ESCALATION_CUE) < both.index(COMPLIANT_FAILURE)


def test_core_cells_on_the_hierarchy_floor_start_with_the_hierarchy():
    for arm in CORE_IDS:
        assert intervention_text(arm, floor="hierarchy", rule=RULE).startswith(FLOOR_HIERARCHY)


def test_escalation_cue_mirrors_the_mount_sinai_wording():
    # externaldocs/citations/CITATIONS.md entry 02: the replication control is only a
    # control if the wording is faithful.
    assert "verify or escalate rather than proceed" in ESCALATION_CUE


def test_exploratory_ladder():
    assert intervention_text("S0", floor="bare", rule=RULE) == ""
    assert RULE in intervention_text("S1", floor="bare", rule=RULE)
    assert intervention_text("S2", floor="bare", rule=RULE) == ESCALATION_CUE
    assert intervention_text("S3", floor="bare", rule=RULE) == FLOOR_HIERARCHY
    s4 = intervention_text("S4", floor="bare", rule=RULE)
    assert s4.startswith(FLOOR_HIERARCHY) and COMPLIANT_FAILURE in s4
    # Exploratory arms ignore the floor argument (they define their own).
    assert intervention_text("S2", floor="hierarchy", rule=RULE) == ESCALATION_CUE


def test_tool_only_and_unknown_arms_raise():
    with pytest.raises(ValueError):
        intervention_text("S5", floor="bare", rule=RULE)
    with pytest.raises(KeyError):
        intervention_text("C99", floor="bare", rule=RULE)
    with pytest.raises(KeyError):
        intervention_text("C00", floor="sideways", rule=RULE)


def test_arm_factors_decompose_the_2x2():
    assert arm_factors("C00", "hierarchy") == {
        "floor": "hierarchy", "escalation_cue": "absent", "compliant_failure": "absent", "ladder": "core",
    }
    assert arm_factors("C11", "bare")["escalation_cue"] == "present"
    assert arm_factors("C11", "bare")["compliant_failure"] == "present"
    assert arm_factors("C10", "bare")["compliant_failure"] == "absent"
    assert arm_factors("S4", "bare") == {
        "floor": "hierarchy", "escalation_cue": "absent", "compliant_failure": "present", "ladder": "S4",
    }
    assert arm_factors("S2", "hierarchy")["escalation_cue"] == "present"


def test_render_all_lists_every_chat_arm_and_the_version():
    text = render_all("hierarchy", rule=RULE)
    assert INTERVENTIONS_VERSION in text
    for arm in ALL_CHAT_IDS:
        assert f"## {arm}" in text
    assert set(CORE_IDS) | set(EXPLORATORY_IDS) == set(ALL_CHAT_IDS)
