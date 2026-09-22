from pathlib import Path

from ombs.prompt_builder import (
    build_full_prompt,
    build_user_prompt,
    prompt_hash,
    split_system_user,
)
from ombs.scenario_loader import load_scenario_file

SCENARIO = (
    Path(__file__).resolve().parents[1]
    / "scenarios" / "administrative" / "confidential_spreadsheet_external_request.yaml"
)


def _scenario():
    return load_scenario_file(SCENARIO)


def test_only_variant_message_changes_across_variants():
    """The key invariant: material facts/policy are constant; only the variant
    user_message differs across pressure variants."""
    sc = _scenario()
    prompts = {v.id: build_user_prompt(sc, v) for v in sc.variants}

    neutral = prompts["neutral"]
    for vid, text in prompts.items():
        if vid == "neutral":
            continue
        # Everything before the "User request:" block must be identical.
        head_neutral = neutral.split("User request:")[0]
        head_other = text.split("User request:")[0]
        assert head_neutral == head_other, f"non-variant text changed for {vid}"

    # And the variant messages themselves must actually differ.
    assert len({p.split("User request:")[1].split("Task:")[0] for p in prompts.values()}) == 6


def test_prompt_hash_is_stable_and_sensitive():
    sc = _scenario()
    v = sc.variants[0]
    p1 = build_full_prompt(sc, v)
    p2 = build_full_prompt(sc, v)
    assert prompt_hash(p1) == prompt_hash(p2)

    p_other = build_full_prompt(sc, sc.variants[1])
    assert prompt_hash(p1) != prompt_hash(p_other)


def test_system_prompt_style_changes_prompt():
    sc = _scenario()
    v = sc.variants[0]
    minimal = build_full_prompt(sc, v, system_prompt_style="minimal")
    strong = build_full_prompt(sc, v, system_prompt_style="strong_boundary")
    assert prompt_hash(minimal) != prompt_hash(strong)


def test_split_system_user_roundtrips():
    sc = _scenario()
    full = build_full_prompt(sc, sc.variants[0], system_prompt_style="policy_aware")
    system, user = split_system_user(full)
    assert "strict enterprise controls" not in system
    assert "Return valid JSON only" in user
