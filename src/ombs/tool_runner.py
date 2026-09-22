"""Simulated-tool runner (brief §18).

For each (model, tool scenario): prompt the model for a single tool call, execute
it against a fresh FakeEnvironment, then score the resulting STATE. This measures
whether a model acts safely when it can actually act — not just whether its prose
sounds safe.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from pydantic import ValidationError

from . import PROMPT_TEMPLATE_VERSION
from .config import RunConfig
from .prompt_builder import (
    SYSTEM_PROMPTS,
    TOOL_TEMPLATE_VERSION,
    build_pushback_message,
    build_tool_prompt,
    tool_prompt_hash,
)
from .providers import get_provider
from .providers.base import GenerationOptions
from .runner import _resolve_format, _utc_now
from .scenario_loader import load_tool_scenarios_from_dir
from .schemas import (
    ToolCallDecision,
    ToolMultiTurnRecord,
    ToolRunRecord,
    ToolScenario,
    ToolTurnResult,
)
from .scorers.state_based import score_state, violation_occurred
from .tools import FakeEnvironment
from .utils.json_extract import extract_json
from .utils.logging import get_logger

log = get_logger(__name__)


def _append_jsonl(path: Path, obj: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _parse_tool_call(raw: str) -> tuple[ToolCallDecision | None, str | None]:
    obj, reason = extract_json(raw)
    if obj is None:
        return None, reason
    try:
        return ToolCallDecision.model_validate(obj), None
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", []))
        return None, f"schema_invalid: {loc}: {first.get('msg', exc)}"


def run_tools(config: RunConfig, output_dir: str | Path | None = None) -> Path:
    out_dir = Path(output_dir) if output_dir else Path("outputs") / config.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    scenarios: list[ToolScenario] = load_tool_scenarios_from_dir(
        config.scenario_dir or "tool_scenarios"
    )
    if config.scenario_ids:
        wanted = set(config.scenario_ids)
        scenarios = [s for s in scenarios if s.id in wanted]

    (out_dir / "config.yaml").write_text(
        yaml.safe_dump(config.model_dump(), sort_keys=False), encoding="utf-8"
    )

    provider = get_provider(config.provider)
    gen = config.generation
    options = GenerationOptions(
        temperature=gen.temperature, top_p=gen.top_p, max_tokens=gen.max_tokens,
        seed=gen.seed, timeout_seconds=config.execution.timeout_seconds,
        think=gen.think, format=_resolve_format(gen.format),
    )
    system = SYSTEM_PROMPTS[config.system_prompt_style]

    records_path = out_dir / "tool_runs.jsonl"
    for model in config.models:
        for scenario in scenarios:
            for run_index in range(1, config.execution.runs_per_variant + 1):
                prompt = build_tool_prompt(
                    config.role or scenario.role, scenario.task, scenario.available_tools
                )
                p_hash = tool_prompt_hash(f"<<SYSTEM>>\n{system}\n\n<<USER>>\n{prompt}")
                log.info("%s | %s (run %d)", model, scenario.id, run_index)
                result = provider.generate(
                    system=system, prompt=prompt, model=model, options=options
                )

                tool_call, parse_error = (None, None)
                if result.ok:
                    tool_call, parse_error = _parse_tool_call(result.raw_response)
                else:
                    parse_error = result.error

                env = FakeEnvironment(internal_domain=scenario.internal_domain)
                if tool_call is not None:
                    env.execute(tool_call.tool, tool_call.arguments)
                check_results, state_passed = score_state(env, scenario)

                record = ToolRunRecord(
                    run_id=config.run_id, timestamp=_utc_now(), provider=config.provider,
                    model=model, scenario_id=scenario.id, scenario_version=scenario.version,
                    role=config.role or scenario.role,
                    prompt_template_version=PROMPT_TEMPLATE_VERSION,
                    tool_template_version=TOOL_TEMPLATE_VERSION, prompt_hash=p_hash,
                    temperature=gen.temperature,
                    raw_response=result.raw_response, parsed_ok=tool_call is not None,
                    parse_error=parse_error, tool_call=tool_call,
                    executed_calls=env.calls, check_results=check_results,
                    state_passed=state_passed if tool_call is not None else False,
                    latency_seconds=result.latency_seconds,
                    errors=([] if result.ok else [result.error or "unknown_error"]),
                )
                _append_jsonl(records_path, record.model_dump(mode="json"))

    log.info("tool run done: output in %s", out_dir)
    return out_dir


def run_tools_multi_turn(config: RunConfig, output_dir: str | Path | None = None) -> Path:
    """Phase 6 × Phase 7: open the tool task, then apply escalating pushback,
    executing each chosen tool call into the SAME environment. Tests whether
    sustained authority pressure turns a safe tool choice into a real unsafe call."""
    out_dir = Path(output_dir) if output_dir else Path("outputs") / config.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    scenarios = [
        s
        for s in load_tool_scenarios_from_dir(config.scenario_dir or "tool_scenarios")
        if s.pushback_sequence
    ]
    if config.scenario_ids:
        wanted = set(config.scenario_ids)
        scenarios = [s for s in scenarios if s.id in wanted]
    if not scenarios:
        raise ValueError("no tool scenarios with a pushback_sequence found")

    (out_dir / "config.yaml").write_text(
        yaml.safe_dump(config.model_dump(), sort_keys=False), encoding="utf-8"
    )

    provider = get_provider(config.provider)
    if not hasattr(provider, "chat"):
        raise NotImplementedError(f"provider {config.provider!r} has no chat() method")
    gen = config.generation
    options = GenerationOptions(
        temperature=gen.temperature, top_p=gen.top_p, max_tokens=gen.max_tokens,
        seed=gen.seed, timeout_seconds=config.execution.timeout_seconds,
        think=gen.think, format=_resolve_format(gen.format),
    )
    system = SYSTEM_PROMPTS[config.system_prompt_style]

    records_path = out_dir / "tool_multiturn.jsonl"
    for model in config.models:
        for scenario in scenarios:
            env = FakeEnvironment(internal_domain=scenario.internal_domain)
            opening = build_tool_prompt(
                config.role or scenario.role, scenario.task, scenario.available_tools
            )
            messages = [{"role": "system", "content": system},
                        {"role": "user", "content": opening}]
            p_hash = tool_prompt_hash(f"<<SYSTEM>>\n{system}\n\n<<USER>>\n{opening}")
            turn_specs = [("neutral", opening)] + [
                (pb.pressure_type, build_pushback_message(pb.user_message))
                for pb in scenario.pushback_sequence
            ]

            turns: list[ToolTurnResult] = []
            first_violation: int | None = None
            survived = 0

            for idx, (ptype, user_text) in enumerate(turn_specs):
                if idx > 0:
                    messages.append({"role": "user", "content": user_text})
                log.info("%s | %s | tool turn %d [%s]", model, scenario.id, idx, ptype)
                result = provider.chat(messages=messages, model=model, options=options)

                tool_call, parse_error = (None, None)
                if result.ok:
                    tool_call, parse_error = _parse_tool_call(result.raw_response)
                else:
                    parse_error = result.error

                executed = None
                if tool_call is not None:
                    executed = env.execute(tool_call.tool, tool_call.arguments)
                violated = violation_occurred(env, scenario)
                if violated and first_violation is None:
                    first_violation = idx
                if idx > 0 and first_violation is None:
                    survived += 1

                turns.append(ToolTurnResult(
                    turn_index=idx, pressure_type=ptype, user_message=user_text,
                    raw_response=result.raw_response, parsed_ok=tool_call is not None,
                    parse_error=parse_error, tool_call=tool_call, executed_call=executed,
                    violation_after=violated, latency_seconds=result.latency_seconds,
                ))
                messages.append({"role": "assistant", "content": result.raw_response})

            check_results, passed = score_state(env, scenario)
            record = ToolMultiTurnRecord(
                run_id=config.run_id, timestamp=_utc_now(), provider=config.provider,
                model=model, scenario_id=scenario.id, scenario_version=scenario.version,
                role=config.role or scenario.role,
                prompt_template_version=PROMPT_TEMPLATE_VERSION,
                tool_template_version=TOOL_TEMPLATE_VERSION, prompt_hash=p_hash,
                temperature=gen.temperature,
                turns=turns, executed_calls=env.calls, final_check_results=check_results,
                final_state_passed=passed, tool_boundary_survival_depth=survived,
                first_violation_turn=first_violation,
            )
            _append_jsonl(records_path, record.model_dump(mode="json"))

    log.info("multi-turn tool run done: output in %s", out_dir)
    return out_dir
