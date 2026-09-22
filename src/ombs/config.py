"""Run-configuration models loaded from ``configs/*.yaml``."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class GenerationConfig(BaseModel):
    temperature: float = 0.2
    top_p: float = 0.9
    max_tokens: int = 800
    seed: int | None = 42
    # qwen3-style "thinking" toggle, forwarded to Ollama when supported.
    think: bool = False
    # When set ("json"), ask the provider for structured output. Left unset by
    # default so the JSON extractor is genuinely exercised (a measured signal).
    format: str | None = None


class ExecutionConfig(BaseModel):
    runs_per_variant: int = 2
    parallel_model_calls: int = 1
    timeout_seconds: int = 90


class RunConfig(BaseModel):
    run_id: str
    provider: str = "ollama"
    models: list[str] = Field(default_factory=list)

    # Either an explicit list of scenario ids, or a directory to load all from.
    scenario_ids: list[str] | None = None
    scenario_dir: str | None = None

    # Optional explicit variant filter; if empty, every scenario's own variants run.
    variants: list[str] = Field(default_factory=list)

    role: str | None = None
    system_prompt_style: str = "policy_aware"

    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "RunConfig":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)


class StudyRunConfig(RunConfig):
    """Run config for Study 1 / Study 2 (``ombs run-study``).

    Subclasses ``RunConfig`` so every existing field keeps its meaning and legacy
    ``config.yaml`` dumps stay byte-identical. ``execution.runs_per_variant`` is the
    repeat count for TREATMENT cells; control cells default to more repeats
    because they are the denominator of every PS_k and of the competence gate
    (>= 4 of 5 correct).
    """

    # Floor for the 2x2 core arms. Decided by a preregistered smoke rule, see
    # scenarios_study1/README.md; recorded on every row.
    floor: Literal["bare", "hierarchy"] = "hierarchy"
    interventions: list[str] = Field(default_factory=lambda: ["C00"])

    # Optional filters over the loaded study scenarios.
    factors: list[str] | None = None
    levels: list[str] | None = None
    permissibility: list[str] | None = None

    # The runner REFUSES to run confirmatory_heldout families unless this is set.
    # It never filters held-out families by outcome; it runs all of them or none.
    include_held_out: bool = False

    control_runs_per_variant: int = 5
    randomize_option_order: bool = True


class ErosionRunConfig(RunConfig):
    """Run config for the gradual-erosion sandbox (``ombs run-erosion``).

    ``execution.runs_per_variant`` is the repeat count per (model, condition, scenario).
    A gradual run is one call per rung plus the final; the other two conditions are a
    single call each.
    """

    conditions: list[Literal["abrupt", "abrupt_state_matched", "gradual", "authority_transfer"]] = Field(
        default_factory=lambda: ["abrupt", "abrupt_state_matched", "gradual"]
    )
    # The runner REFUSES confirmatory_heldout families unless set, and then runs all.
    include_held_out: bool = False
    state_render_max_chars: int = 2500
    # Resume re-runs records whose final turn was unmeasured (truncation, transport).
    retry_unmeasured: bool = False


class SandboxRunConfig(RunConfig):
    """Run config for the goal-obstacle sandbox (``ombs run-sandbox``, Wave 3).

    Cells are the cross product of the listed factor levels. ``execution.runs_per_variant``
    is the repeat count per (model, cell, scenario). ``technical_step_cap`` is a runner
    safety cap on tool calls and is never rendered to the model; only ``session_limit: on``
    renders a limit, and that one lives in the scenario (``session_limit_actions``).
    """

    solvability: list[Literal["solvable", "stuck", "stuck_incidental"]] = Field(
        default_factory=lambda: ["solvable", "stuck"]
    )
    rule_distance: list[Literal["adjacent", "distal", "absent"]] = Field(
        default_factory=lambda: ["adjacent"]
    )
    checker_access: list[Literal["hidden_immutable", "visible_readonly", "visible_writable"]] = Field(
        default_factory=lambda: ["visible_writable"]
    )
    session_limit: list[Literal["off", "on"]] = Field(default_factory=lambda: ["off"])
    task_framing: list[Literal["baseline", "compliant_failure", "authority_salience"]] = Field(
        default_factory=lambda: ["baseline"]
    )
    #: Compliant-failure paraphrase variants to sample (wording-robustness study). "canonical" is
    #: the family's own sentence; any other value names an entry in the frozen paraphrase bank
    #: (scenarios_sandbox/framing_paraphrases.yaml). A non-canonical value is accepted by the runner
    #: only when task_framing is exactly ["compliant_failure"] and the family carries a matching bank
    #: (see select/validate in sandbox_runner). Default leaves every existing config unchanged.
    framing_variant: list[str] = Field(default_factory=lambda: ["canonical"])
    defer_available: list[Literal["off", "on"]] = Field(default_factory=lambda: ["off"])
    tool_transport: Literal["native", "json_schema"] = "native"

    technical_step_cap: int | None = None  # None: the scenario's value
    read_max_chars: int = 2000
    listing_max_chars: int = 800
    # Anthropic prompt caching (marker on the system block and the last tool result).
    # Invisible to the model; a switch that costs money but never correctness.
    prompt_caching: bool = False
    include_held_out: bool = False
    retry_unmeasured: bool = False
    max_consecutive_parse_failures: int = 3
    # One run, one family, unless pooling is deliberate. There is no `allow_frozen` here on
    # purpose: re-running a frozen family takes a command-line flag, so no committed YAML can
    # quietly re-enable one.
    allow_multi_family: bool = False
