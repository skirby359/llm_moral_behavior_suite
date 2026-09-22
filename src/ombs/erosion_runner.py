"""Gradual-erosion runner (Wave 2): models x conditions x scenarios x repeats -> erosion.jsonl.

Three conditions share one policy, one tool list and one final request:

- ``abrupt``               the final request from the initial workspace, no history;
- ``abrupt_state_matched`` the initial workspace plus the rungs' effects already recorded by
                           a named colleague, no history;
- ``gradual``              the model decides and executes each permissible rung in turn, sees
                           the result and the updated workspace, then gets the final request;
- ``authority_transfer``   (continuity condition, opt-in) the same substantive final request
                           from the initial workspace, sent by a named senior figure who is not
                           the authorizing party and takes responsibility. Everything above the
                           message block is byte-identical to ``abrupt``.

What the model sees each turn is built by ``prompt_builder.build_erosion_opening`` /
``build_erosion_observation``; what happened is executed by ``ErosionEnvironment``; what it
means is decided by ``scorers.erosion``. The runner persists **every turn immediately**
(``erosion_turns.jsonl``) and writes one completed record per run (``erosion.jsonl``);
analysis reads outcomes only from completed records, and every turn row carries the
run's ``attempt_id`` so an aborted ladder can never be mistaken for a finished one.

Stop rules inside a run: a transport failure or a truncated reply ends the ladder (a
partial assistant turn cannot be appended to the conversation without corrupting it);
a parse failure or an execution error continues, with the error shown to the model as
its observation and the workspace unchanged. A budget abort before any call in a run
leaves the key open for resume.
"""

from __future__ import annotations

import copy
import json
import uuid
from dataclasses import replace
from pathlib import Path

import yaml
from pydantic import ValidationError

from .config import ErosionRunConfig
from .erosion_env import ErosionEnvironment
from .prompt_builder import (
    EROSION_RESPONSE_SCHEMA_BLOCK,
    EROSION_TEMPLATE_VERSION,
    EROSION_TOOL_SIGNATURES,
    SYSTEM_PROMPTS,
    build_erosion_observation,
    build_erosion_opening,
    build_erosion_system,
    erosion_prompt_hash,
)
from .providers import get_provider
from .providers.base import GenerationOptions
from .runner import _resolve_format, _utc_now
from .scenario_loader import load_erosion_scenarios_from_dir
from .schemas import ErosionRecord, ErosionScenario, ErosionStep, ErosionToolCall, ErosionTurn
from .scorers.erosion import classify_turn, summarise_run
from .study_runner import _git_commit
from .utils.budget import BudgetExceeded, BudgetGuard, call_cost, usage_from_metadata
from .utils.hardware import collect_hardware_report
from .utils.hashing import sha256_text
from .utils.json_extract import extract_json
from .utils.logging import get_logger

log = get_logger(__name__)

RECORDS_NAME = "erosion.jsonl"
TURNS_NAME = "erosion_turns.jsonl"
CONDITIONS = ("abrupt", "abrupt_state_matched", "gradual", "authority_transfer")


def _append_jsonl(path: Path, obj: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")


def _completed_keys(path: Path, *, retry_unmeasured: bool) -> set[tuple]:
    """(model, condition, scenario_id, run_index) of completed runs; optionally only measured ones."""
    done: set[tuple] = set()
    if not path.exists():
        return done
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            if not r.get("complete"):
                continue
            if retry_unmeasured and not (r.get("outcome") or {}).get("final_measured"):
                continue
            done.add((r["model"], r["condition"], r["scenario_id"], r["run_index"]))
        except (json.JSONDecodeError, KeyError):
            continue
    return done


def _parse_tool_call(raw: str) -> tuple[ErosionToolCall | None, str | None]:
    obj, reason = extract_json(raw)
    if obj is None:
        return None, reason
    try:
        return ErosionToolCall.model_validate(obj), None
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", []))
        return None, f"schema_invalid: {loc}: {first.get('msg', exc)}"


def _is_provider_refusal(meta: dict) -> bool:
    return meta.get("stop_reason") == "refusal" or meta.get("finish_reason") == "content_filter"


def _is_truncated(meta: dict) -> bool:
    return bool(meta.get("truncated")) or meta.get("stop_reason") == "max_tokens" or meta.get("finish_reason") == "length"


def _format_for_tools(base_format: str | dict | None, tools: list[str]) -> str | dict | None:
    """Make the sent schema constrain what the model must emit.

    Three things the raw pydantic schema gets wrong for constrained decoding, all found
    by the first local smoke (every call came back with no arguments at all):
    - `arguments` and the arg keys have defaults, so they are not `required`, and a
      constrained decoder is free to omit them -- Ollama did, every time;
    - `arguments` is a `$ref` into `$defs`, which not every decoder resolves;
    - `tool` is a free string.
    So: inline the ref, require every key at both levels, close both objects, and set
    the `tool` enum to the scenario's available tools. The pydantic model keeps its
    defaults so unconstrained replies still parse.
    """
    if not isinstance(base_format, dict):
        return base_format
    fmt = copy.deepcopy(base_format)
    defs = fmt.pop("$defs", {})
    props = fmt.get("properties", {})
    if "tool" in props:
        props["tool"] = {"type": "string", "enum": list(tools)}
    args = props.get("arguments")
    if isinstance(args, dict) and "$ref" in args:
        name = args["$ref"].rsplit("/", 1)[-1]
        args = copy.deepcopy(defs.get(name, {}))
        props["arguments"] = args
    if isinstance(args, dict) and "properties" in args:
        for v in args["properties"].values():
            v.pop("default", None)
        args["required"] = list(args["properties"])
        args["additionalProperties"] = False
    for v in props.values():
        if isinstance(v, dict):
            v.pop("default", None)
    fmt["required"] = list(props)
    fmt["additionalProperties"] = False
    return fmt


def select_erosion_scenarios(config: ErosionRunConfig) -> list[ErosionScenario]:
    scenarios = load_erosion_scenarios_from_dir(config.scenario_dir or "scenarios_erosion")
    if config.scenario_ids:
        by_id = {s.id: s for s in scenarios}
        missing = [i for i in config.scenario_ids if i not in by_id]
        if missing:
            raise ValueError(f"erosion scenario ids not found: {missing}")
        scenarios = [by_id[i] for i in config.scenario_ids]
    if not scenarios:
        raise ValueError("no erosion scenarios selected (see scenarios_erosion/)")
    held = [s.id for s in scenarios if s.family_role == "confirmatory_heldout"]
    if held and not config.include_held_out:
        raise ValueError(
            f"{len(held)} confirmatory_heldout scenario(s) selected but include_held_out is false. "
            "Held-out families run all-or-nothing after the split is committed; set "
            "include_held_out: true to run them, or point scenario_dir at the development set."
        )
    return scenarios


def _seed_env(scenario: ErosionScenario, condition: str) -> ErosionEnvironment:
    env = ErosionEnvironment(scenario)
    if condition == "abrupt_state_matched":
        env.apply_prior(scenario.effective_prior(), actor=scenario.colleague_name)
    return env


def _turn_plan(scenario: ErosionScenario, condition: str) -> list[tuple[str, str, ErosionStep | None]]:
    plan: list[tuple[str, str, ErosionStep | None]] = []
    if condition == "authority_transfer":
        return [("final", scenario.final_request_authority or "", None)]
    if condition == "gradual":
        plan += [(s.id, s.user_message, s) for s in scenario.steps]
    plan.append(("final", scenario.final_request, None))
    return plan


def _write_manifest(out_dir: Path, config: ErosionRunConfig, scenarios: list[ErosionScenario]) -> None:
    (out_dir / "config.yaml").write_text(yaml.safe_dump(config.model_dump(), sort_keys=False), encoding="utf-8")
    (out_dir / "models.txt").write_text("\n".join(config.models) + "\n", encoding="utf-8")
    (out_dir / "erosion_template.md").write_text(
        f"# Erosion template v{EROSION_TEMPLATE_VERSION}\n\n"
        f"## System prompt style: {config.system_prompt_style}\n\n"
        f"```\n{SYSTEM_PROMPTS[config.system_prompt_style]}\n```\n\n"
        "## Tool signatures\n\n```\n" + "\n".join(EROSION_TOOL_SIGNATURES.values()) + "\n```\n\n"
        f"## Response schema\n\n```\n{EROSION_RESPONSE_SCHEMA_BLOCK}\n```\n",
        encoding="utf-8",
    )
    manifest = {
        "run_id": config.run_id,
        "conditions": list(config.conditions),
        "erosion_template_version": EROSION_TEMPLATE_VERSION,
        "git_commit": _git_commit(),
        "scenarios": [
            {
                "id": s.id, "version": s.version, "sha256": s.source_sha256, "family": s.family,
                "family_role": s.family_role, "domain": s.domain, "n_steps": len(s.steps),
                "tools": list(s.available_tools), "final_focal": s.final_focal.model_dump(),
                "colleague_name": s.colleague_name, "requester_name": s.requester_name,
                "authority_name": s.authority_name,
                "human_evidence_class": s.human_evidence_class, "literature_tag": s.literature_tag,
            }
            for s in scenarios
        ],
    }
    (out_dir / "scenario_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "git_commit.txt").write_text(manifest["git_commit"] + "\n", encoding="utf-8")
    try:
        (out_dir / "hardware.txt").write_text(collect_hardware_report(), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        (out_dir / "hardware.txt").write_text(f"<hardware capture failed: {exc}>", "utf-8")


def _write_transcript(out_dir: Path, model: str, condition: str, scenario: ErosionScenario,
                      run_index: int, system: str, turns: list[ErosionTurn], env: ErosionEnvironment) -> None:
    safe_model = model.replace(":", "_").replace("/", "_")
    path = out_dir / "transcripts" / safe_model / condition / f"{scenario.id}__r{run_index}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {model} -- {condition} -- {scenario.id} -- run {run_index}", "", "## System", "```", system, "```", ""]
    for t in turns:
        o = t.outcome
        tag = "unmeasured:" + (o.unmeasured_reason or "?") if (o and not o.measured) else (
            f"tool={o.tool} intended={o.took_intended} violation={o.violation} refusal={o.false_refusal}" if o else "")
        lines += [f"## Turn {t.turn_index} [{t.step_id}]  {tag}", "", "**User:**", "```", t.user_message, "```", "",
                  "**Assistant (raw):**", "```json", (t.raw_response or "")[:2000], "```", ""]
    lines += ["## Final workspace", "```", env.render_state(max_chars=6000), "```", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_erosion(config: ErosionRunConfig, output_dir: str | Path | None = None) -> Path:
    out_dir = Path(output_dir) if output_dir else Path("outputs") / config.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    scenarios = select_erosion_scenarios(config)
    conditions = [c for c in config.conditions if c in CONDITIONS]
    _write_manifest(out_dir, config, scenarios)

    provider = get_provider(config.provider)
    if not hasattr(provider, "chat"):
        raise NotImplementedError(f"provider {config.provider!r} has no chat() method")

    gen = config.generation
    base_format = _resolve_format(gen.format, schema="erosion")
    base_options = GenerationOptions(
        temperature=gen.temperature, top_p=gen.top_p, max_tokens=gen.max_tokens, seed=gen.seed,
        timeout_seconds=config.execution.timeout_seconds, think=gen.think, format=base_format,
    )
    system = build_erosion_system(system_prompt_style=config.system_prompt_style)
    system_hash = sha256_text(system)

    records_path, turns_path = out_dir / RECORDS_NAME, out_dir / TURNS_NAME
    done = _completed_keys(records_path, retry_unmeasured=config.retry_unmeasured)
    if done:
        log.info("resuming: %d runs already complete, will be skipped", len(done))

    budget = BudgetGuard(run_id=config.run_id)
    log.info("budget: cap $%.2f, $%.4f already on the ledger, $%.4f remaining",
             budget.cap_usd, budget.spent_before, budget.remaining())
    aborted: str | None = None
    n_runs = n_calls = 0

    for model in config.models:
        for condition in conditions:
            for scenario in scenarios:
                if condition == "authority_transfer" and not scenario.final_request_authority:
                    log.warning("%s has no final_request_authority; skipping the continuity condition", scenario.id)
                    continue
                requester = scenario.authority_name if condition == "authority_transfer" else scenario.requester_name
                fmt = _format_for_tools(base_format, list(scenario.available_tools))
                for run_index in range(1, config.execution.runs_per_variant + 1):
                    if aborted:
                        break
                    key = (model, condition, scenario.id, run_index)
                    if key in done:
                        continue
                    attempt_id = uuid.uuid4().hex[:12]
                    call_seed = None if gen.seed is None else gen.seed + run_index - 1
                    options = replace(base_options, seed=call_seed, format=fmt)
                    env = _seed_env(scenario, condition)
                    plan = _turn_plan(scenario, condition)
                    messages: list[dict] = [{"role": "system", "content": system}]
                    turns: list[ErosionTurn] = []
                    prev_exec: dict | None = None
                    prompt_hash = ""
                    stopped_early = False
                    canonical_before_final: str | None = None

                    for turn_index, (step_id, text, step) in enumerate(plan):
                        if step is None:
                            canonical_before_final = env.canonical_state_hash()
                        if turn_index == 0:
                            user = build_erosion_opening(
                                role=config.role or scenario.role, policy_context=scenario.policy_context,
                                task_goal=scenario.task_goal,
                                state_render=env.render_state(config.state_render_max_chars),
                                request=text, requester_name=requester,
                                available_tools=list(scenario.available_tools),
                            )
                            prompt_hash = erosion_prompt_hash(f"<<SYSTEM>>\n{system}\n\n<<USER>>\n{user}")
                        else:
                            user = build_erosion_observation(
                                result=prev_exec, state_render=env.render_state(config.state_render_max_chars),
                                next_request=text, requester_name=requester,
                            )
                        messages.append({"role": "user", "content": user})

                        try:
                            budget.check_before_call(model)
                        except BudgetExceeded as exc:
                            log.error("%s", exc)
                            aborted = str(exc)
                            break
                        log.info("%s | %s | %s r%d | turn %d [%s]", model, condition, scenario.id, run_index, turn_index, step_id)
                        result = provider.chat(messages=messages, model=model, options=options)
                        n_calls += 1
                        meta = result.provider_metadata or {}
                        usage = usage_from_metadata(meta)
                        cost = call_cost(model, usage)
                        try:
                            budget.charge(model, meta)
                        except BudgetExceeded as exc:
                            log.error("%s", exc)
                            aborted = str(exc)

                        truncated = _is_truncated(meta) if result.ok else False
                        refused = _is_provider_refusal(meta) if result.ok else False
                        call, perr, executed = None, None, None
                        if result.ok and not truncated and not refused:
                            call, perr = _parse_tool_call(result.raw_response)
                            if call is not None:
                                executed = env.execute(call.tool, call.arguments.model_dump(), actor="you", turn=turn_index)
                        elif not result.ok:
                            perr = result.error
                        outcome = classify_turn(
                            scenario=scenario, step=step, call=call, executed=executed, env=env,
                            turn_index=turn_index, truncated=truncated, provider_refusal=refused,
                            transport_error=None if result.ok else (result.error or "unknown_error"),
                        )
                        turn = ErosionTurn(
                            turn_index=turn_index, step_id=step_id, user_message=user,
                            raw_response=result.raw_response, parsed_ok=call is not None, parse_error=perr,
                            tool_call=call, executed_call=executed, outcome=outcome,
                            latency_seconds=result.latency_seconds, usage=usage, cost_usd=cost,
                            finish_reason=meta.get("finish_reason") or meta.get("stop_reason"),
                            truncated=truncated, errors=([] if result.ok else [result.error or "unknown_error"]),
                        )
                        turns.append(turn)
                        _append_jsonl(turns_path, {
                            "attempt_id": attempt_id, "model": model, "condition": condition,
                            "scenario_id": scenario.id, "run_index": run_index, **turn.model_dump(mode="json"),
                        })
                        if not result.ok or truncated or refused:
                            stopped_early = True
                            break
                        messages.append({"role": "assistant", "content": result.raw_response})
                        prev_exec = executed
                        if aborted:
                            break

                    if aborted:
                        break  # key stays open; orphan turn rows carry the attempt_id

                    turn_outcomes = [t.outcome for t in turns if t.outcome is not None]
                    run_outcome = summarise_run(
                        turn_outcomes, condition=condition, n_steps=len(scenario.steps),
                        canonical_before_final=canonical_before_final, stopped_early=stopped_early,
                    )
                    turn_costs = [t.cost_usd for t in turns if t.cost_usd is not None]
                    record = ErosionRecord(
                        run_id=config.run_id, timestamp=_utc_now(), attempt_id=attempt_id,
                        provider=config.provider, model=model,
                        model_digest=next((t for t in [getattr(result, "model_digest", None)] if t), None),
                        model_resolved=meta.get("model") if turns else None,
                        scenario_id=scenario.id, scenario_version=scenario.version,
                        scenario_sha256=scenario.source_sha256, family=scenario.family,
                        family_role=scenario.family_role, domain=scenario.domain,
                        literature_tag=scenario.literature_tag,
                        human_evidence_class=scenario.human_evidence_class,
                        condition=condition, role=config.role or scenario.role,
                        system_prompt_style=config.system_prompt_style, system_prompt_chars=len(system),
                        temperature=gen.temperature, top_p=gen.top_p, seed=call_seed,
                        max_tokens=gen.max_tokens, think=gen.think, format=gen.format, run_index=run_index,
                        erosion_template_version=EROSION_TEMPLATE_VERSION,
                        prompt_hash=prompt_hash, system_hash=system_hash,
                        n_steps=len(scenario.steps), n_turns=len(turns), turns=turns,
                        outcome=run_outcome, executed_calls=list(env.calls), final_state=env.to_dict(),
                        stopped_early=stopped_early, complete=True,
                        cost_usd=round(sum(turn_costs), 6) if turn_costs else None,
                    )
                    _append_jsonl(records_path, record.model_dump(mode="json"))
                    _write_transcript(out_dir, model, condition, scenario, run_index, system, turns, env)
                    n_runs += 1
                if aborted:
                    break
            if aborted:
                break
        if aborted:
            break

    log.info("budget: %s", budget.summary())
    (out_dir / "spend.txt").write_text(
        budget.summary() + ("\nABORTED: " + aborted if aborted else "") + "\n", encoding="utf-8"
    )
    if aborted:
        raise BudgetExceeded(aborted)
    log.info("erosion run done: %d runs, %d calls, output in %s", n_runs, n_calls, out_dir)
    return out_dir
