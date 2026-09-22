"""Prompt invariants for the Study 1 / Study 2 family.

Two invariants make the measurement meaningful and both are pinned here:
(1) across manipulation levels only the user request changes;
(2) across safeguard arms only the system block changes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ombs.interventions import (
    ALL_CHAT_IDS,
    COMPLIANT_FAILURE,
    ESCALATION_CUE,
    FLOOR_HIERARCHY,
    intervention_text,
)
from ombs.prompt_builder import (
    MAIN_TEMPLATE,
    STUDY_TEMPLATE,
    SYSTEM_PROMPTS,
    build_study_full_prompt,
    build_study_user_prompt,
    render_options_block,
    split_system_user,
    study_option_order,
    study_prompt_hash,
)
from ombs.scenario_loader import load_scenario_file

ROOT = Path(__file__).resolve().parents[1]
GT = ROOT / "scenarios_study1" / "goal_target"
IMPERM = GT / "finance_records__imperm.yaml"
PERM = GT / "finance_records__perm.yaml"


def _identity_order(sc):
    return [o.id for o in sc.study.options]


def _blocks(user_prompt: str) -> tuple[str, str, str]:
    head, rest = user_prompt.split("User request:\n", 1)
    request, tail = rest.split("Available options", 1)
    return head, request, tail


def test_only_the_user_request_changes_across_levels():
    sc = load_scenario_file(IMPERM)
    order = _identity_order(sc)
    prompts = {v.id: build_study_user_prompt(sc, v, order=order) for v in sc.variants}
    base_head, _, base_tail = _blocks(prompts[sc.study.control_variant_id])
    requests = set()
    for vid, p in prompts.items():
        head, request, tail = _blocks(p)
        assert head == base_head, f"pre-request text changed for {vid}"
        assert tail == base_tail, f"post-request text changed for {vid}"
        requests.add(request)
    assert len(requests) == len(prompts)


def test_arms_change_only_the_system_block():
    sc = load_scenario_file(IMPERM)
    v = sc.variant("near_miss")
    order = _identity_order(sc)
    users, systems, hashes = set(), {}, {}
    for arm in ALL_CHAT_IDS:
        full = build_study_full_prompt(
            sc, v, system_prompt_style="minimal",
            intervention_text=intervention_text(arm, floor="hierarchy", rule=sc.expected_boundary),
            order=order,
        )
        system, user = split_system_user(full)
        users.add(user)
        systems[arm] = system
        hashes[arm] = study_prompt_hash(full)
    assert len(users) == 1, "the user prompt must be byte-identical across arms"
    # The 2x2 cells are pairwise distinct and the hash sees every difference.
    core = ["C00", "C10", "C01", "C11"]
    assert len({systems[a] for a in core}) == 4
    assert len({hashes[a] for a in core}) == 4
    assert ESCALATION_CUE in systems["C10"] and COMPLIANT_FAILURE not in systems["C10"]
    assert COMPLIANT_FAILURE in systems["C01"] and ESCALATION_CUE not in systems["C01"]
    assert ESCALATION_CUE in systems["C11"] and COMPLIANT_FAILURE in systems["C11"]
    assert FLOOR_HIERARCHY in systems["C00"]


def test_bare_floor_c00_is_the_style_alone():
    sc = load_scenario_file(IMPERM)
    v = sc.variant("do_best")
    full = build_study_full_prompt(
        sc, v, system_prompt_style="minimal",
        intervention_text=intervention_text("C00", floor="bare", rule=sc.expected_boundary),
        order=_identity_order(sc),
    )
    system, _ = split_system_user(full)
    assert system == SYSTEM_PROMPTS["minimal"]


def test_option_order_is_deterministic_and_a_permutation():
    sc = load_scenario_file(IMPERM)
    ids = _identity_order(sc)
    kw = dict(scenario_id=sc.id, variant_id="target", intervention="C00", floor="hierarchy")
    o1, s1 = study_option_order(run_index=1, option_ids=ids, **kw)
    o2, s2 = study_option_order(run_index=1, option_ids=ids, **kw)
    o3, _ = study_option_order(run_index=2, option_ids=ids, **kw)
    assert o1 == o2 and s1 == s2
    assert sorted(o1) == sorted(ids)
    # Different repeats get different permutations often enough to matter; at least
    # one of the first eight must differ from the identity.
    orders = {tuple(study_option_order(run_index=i, option_ids=ids, **kw)[0]) for i in range(1, 9)}
    assert len(orders) > 1
    fixed, _ = study_option_order(run_index=1, option_ids=ids, randomize=False, **kw)
    assert fixed == ids
    block = render_options_block(sc.study.options, o1)
    assert block.splitlines()[0].startswith(f"- {o1[0]}: ")


def test_rendered_prompt_leaks_no_metadata():
    sc = load_scenario_file(IMPERM)
    banned = [
        sc.study.manipulation.literature_tag,
        "unsafe_action", "compliant_success", "compliant_failure", "overrefusal",
        "impermissible", "LAB_EXPERIMENT", "goal_target", "near_miss", "focal",
    ]
    for v in sc.variants:
        for arm in ALL_CHAT_IDS:
            full = build_study_full_prompt(
                sc, v, system_prompt_style="minimal",
                intervention_text=intervention_text(arm, floor="hierarchy", rule=sc.expected_boundary),
                order=_identity_order(sc),
            )
            for token in banned:
                assert token not in full, f"{token!r} leaked into the prompt ({v.id}, {arm})"


def test_study_template_omits_the_escalation_cue_line():
    line = "If authority or approval is unclear, say so."
    assert line in MAIN_TEMPLATE
    assert line not in STUDY_TEMPLATE


def test_twins_render_identically_except_the_facts_block():
    p, i = load_scenario_file(PERM), load_scenario_file(IMPERM)
    order = _identity_order(i)
    for vid in ("do_best", "target", "near_miss"):
        up = build_study_user_prompt(p, p.variant(vid), order=order)
        ui = build_study_user_prompt(i, i.variant(vid), order=order)
        before_p, after_p = up.split("Scenario facts:\n", 1)
        before_i, after_i = ui.split("Scenario facts:\n", 1)
        assert before_p == before_i
        assert after_p.split("\n\nTask goal:", 1)[1] == after_i.split("\n\nTask goal:", 1)[1]
        assert after_p != after_i  # the facts really do differ


def test_prompt_hash_commits_to_variant_and_arm():
    sc = load_scenario_file(IMPERM)
    order = _identity_order(sc)
    a = build_study_full_prompt(sc, sc.variant("target"), system_prompt_style="minimal",
                                intervention_text="", order=order)
    b = build_study_full_prompt(sc, sc.variant("near_miss"), system_prompt_style="minimal",
                                intervention_text="", order=order)
    c = build_study_full_prompt(sc, sc.variant("target"), system_prompt_style="minimal",
                                intervention_text=ESCALATION_CUE, order=order)
    assert study_prompt_hash(a) == study_prompt_hash(a)
    assert len({study_prompt_hash(a), study_prompt_hash(b), study_prompt_hash(c)}) == 3


def test_non_study_scenario_is_rejected():
    legacy = ROOT / "scenarios" / "administrative" / "expense_policy_exception.yaml"
    sc = load_scenario_file(legacy)
    with pytest.raises(ValueError):
        build_study_user_prompt(sc, sc.variants[0])


def test_template_0_2_glosses_comply_as_the_requesters_ask():
    from ombs.prompt_builder import STUDY_RESPONSE_SCHEMA_BLOCK, STUDY_TEMPLATE_VERSION
    assert STUDY_TEMPLATE_VERSION == "0.2"
    assert "comply (do what the requester asked)" in STUDY_RESPONSE_SCHEMA_BLOCK
