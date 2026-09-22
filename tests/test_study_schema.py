"""Schema guarantees for study scenarios, and the shipped smoke files."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from pydantic import ValidationError

from ombs.scenario_loader import load_scenarios_from_dir
from ombs.schemas import Scenario

STUDY_DIR = Path(__file__).resolve().parents[1] / "scenarios_study1"


def _minimal(permissibility: str = "impermissible") -> dict:
    focal_outcome = "unsafe_action" if permissibility == "impermissible" else "compliant_success"
    other = "compliant_failure" if permissibility == "impermissible" else "overrefusal"
    return {
        "id": "t", "category": "study1", "title": "t", "role": "administrative_assistant",
        "base_facts": "f.", "policy_context": "p.", "expected_boundary": "b.",
        "scoring": {"primary_boundary": "x", "ideal_decision_class": "other",
                    "expected_escalation": False},
        "variants": [
            {"id": "do_best", "level": "do_best", "pressure_type": "neutral", "user_message": "a"},
            {"id": "target", "level": "target", "pressure_type": "goal_target", "user_message": "b"},
        ],
        "study": {
            "family": "goal_target_finance_records", "domain": "finance_records",
            "permissibility": permissibility,
            "manipulation": {"factor": "goal_target", "literature_tag": "schweitzer_2004_near_miss",
                             "human_evidence_class": "LAB_EXPERIMENT",
                             "anchor_citation_ids": ["07"], "control_level": "do_best"},
            "control_variant_id": "do_best", "focal_action_id": "go",
            "task_goal": "finish",
            "options": [
                {"id": "go", "text": "do it", "outcome": focal_outcome, "reversible": False},
                {"id": "hold", "text": "hold it", "outcome": other},
                {"id": "esc", "text": "escalate it", "outcome": "escalation"},
            ],
        },
    }


def _mutate(path: list, value, permissibility: str = "impermissible") -> dict:
    d = _minimal(permissibility)
    node = d
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return d


def test_minimal_study_scenarios_validate():
    Scenario.model_validate(_minimal("impermissible"))
    Scenario.model_validate(_minimal("permissible"))


@pytest.mark.parametrize(
    "bad, perm, why",
    [
        (["study", "options", 0, "outcome"], "compliant_success", "impermissible"),  # focal must be unsafe
        (["study", "options", 1, "outcome"], "unsafe_action", "impermissible"),  # two unsafe
        (["study", "options", 1, "outcome"], "overrefusal", "impermissible"),  # overrefusal undefined
        (["study", "options", 0, "outcome"], "unsafe_action", "permissible"),  # unsafe on permissible
        (["study", "options", 1, "outcome"], "compliant_success", "permissible"),  # non-focal success
        (["study", "options", 1, "outcome"], "compliant_failure", "permissible"),  # must be overrefusal
        (["study", "focal_action_id"], "nope", "impermissible"),
        (["variants", 1, "level"], None, "impermissible"),  # missing level
        (["variants", 1, "level"], "do_best", "impermissible"),  # duplicate level
        (["study", "manipulation", "control_level"], "target", "impermissible"),  # control mismatch
        (["variants", 0, "pressure_type"], "authority", "impermissible"),  # control not neutral
        (["study", "control_variant_id"], "zzz", "impermissible"),
    ],
)
def test_inconsistent_designs_are_rejected(bad, perm, why):
    with pytest.raises(ValidationError):
        Scenario.model_validate(_mutate(bad, perm, why))


def test_legacy_scenarios_still_validate_without_study_fields():
    d = _minimal()
    del d["study"]
    for v in d["variants"]:
        v.pop("level")
    sc = Scenario.model_validate(d)
    assert sc.study is None and all(v.level is None for v in sc.variants)


def test_shipped_smoke_files_load_with_study_blocks_and_hashes():
    scenarios = load_scenarios_from_dir(STUDY_DIR)
    assert len(scenarios) >= 4
    families = {}
    for s in scenarios:
        assert s.study is not None, s.id
        assert s.source_sha256 and len(s.source_sha256) == 64
        assert s.study.family_role == "development_only"
        families.setdefault(s.study.family, set()).add(s.study.permissibility)
    for fam, perms in families.items():
        assert perms == {"permissible", "impermissible"}, fam


def test_twins_share_options_text_and_flip_only_the_focal_label():
    by_fam = {}
    for s in load_scenarios_from_dir(STUDY_DIR):
        by_fam.setdefault(s.study.family, {})[s.study.permissibility] = s
    for fam, pair in by_fam.items():
        p, i = pair["permissible"], pair["impermissible"]
        assert [(o.id, o.text) for o in p.study.options] == [(o.id, o.text) for o in i.study.options], fam
        assert p.study.focal_action_id == i.study.focal_action_id
        focal_p = next(o for o in p.study.options if o.id == p.study.focal_action_id)
        focal_i = next(o for o in i.study.options if o.id == i.study.focal_action_id)
        assert (focal_i.outcome, focal_p.outcome) == ("unsafe_action", "compliant_success"), fam
        assert copy.deepcopy(p.variants) == p.variants  # sanity: variants are plain data
        assert [v.user_message for v in p.variants] == [v.user_message for v in i.variants], fam


def _factorial(control_factors: dict, treat_factors: dict, sentences: dict | None = None) -> dict:
    d = _minimal()
    d["study"]["factor_sentences"] = sentences if sentences is not None else {"pressure": "We are behind."}
    d["variants"][0]["factors"] = control_factors
    d["variants"][1]["factors"] = treat_factors
    d["variants"][1]["pressure_type"] = "work_completion"
    d["study"]["manipulation"]["factor"] = "work_completion"
    d["study"]["family"] = "work_completion_security"
    d["study"]["domain"] = "security"
    return d


def test_factor_sentences_validation():
    Scenario.model_validate(_factorial({"pressure": "absent"}, {"pressure": "present"}))
    for bad in (
        _factorial({"pressure": "present"}, {"pressure": "present"}),   # control not all absent
        _factorial({"pressure": "absent"}, {"opportunity": "present"}),  # wrong factor key
        _factorial({"pressure": "absent"}, {"pressure": "yes"}),        # bad value
        _factorial({}, {"pressure": "present"}),                        # missing key on control
    ):
        with pytest.raises(ValidationError):
            Scenario.model_validate(bad)


def test_shipped_work_completion_family_declares_its_factor_sentences():
    fams = {s.study.family: s for s in load_scenarios_from_dir(STUDY_DIR)
            if s.study.manipulation.factor == "work_completion"}
    assert fams, "no work_completion scenario shipped"
    for s in fams.values():
        assert set(s.study.factor_sentences) == {"pressure", "opportunity", "justification"}
        assert len(s.variants) == 8  # full 2x2x2 including the control
