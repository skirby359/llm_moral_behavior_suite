"""Goal-obstacle sandbox runner (Wave 3): models x cells x scenarios x repeats -> sandbox.jsonl.

One opening instruction; thereafter the environment supplies observations only (tool
results and a compact listing) and the model acts until it calls `done`, stops calling
tools, hits the silent technical cap, or (session_limit on) reaches the schedule. Two tool
transports share everything downstream:

- ``native``       provider tool calling (Anthropic tool_use / OpenAI tool_calls / Ollama tools);
                   several calls per assistant turn allowed, executed in order, results
                   returned together with the listing as a text block;
- ``json_schema``  the constrained-output mechanism used by Waves 1-2, one call per reply.

Every turn is persisted immediately (``sandbox_turns.jsonl``, with the run's attempt_id);
one completed record per run goes to ``sandbox.jsonl``; ``freeze.json`` records what ran
(cells, n, scenario hash, template version, transport, git commit, rule-text hash).

Stop rules: transport failure, truncation or a vendor refusal ends the run as
``stopped_early`` (unmeasured, retryable); ``max_consecutive_parse_failures`` parse
failures in a row end it too; a budget abort leaves the key open for resume. Parse or
execution errors otherwise consume a turn/action and are shown to the model.
"""

from __future__ import annotations

import itertools
import json
import uuid
from dataclasses import replace
from pathlib import Path

import yaml
from pydantic import ValidationError

from .config import SandboxRunConfig
from .erosion_runner import _append_jsonl, _format_for_tools, _is_provider_refusal, _is_truncated
from .prompt_builder import (
    SANDBOX_TEMPLATE_VERSION,
    build_sandbox_observation,
    build_sandbox_opening,
    build_sandbox_system,
    sandbox_extra_text,
    sandbox_prompt_hash,
    sandbox_tool_specs,
)
from .providers import get_provider
from .providers.base import (
    AssistantMsg,
    GenerationOptions,
    SystemMsg,
    ToolResult,
    ToolResultsMsg,
    ToolSpec,
    UserMsg,
)
from .runner import _resolve_format, _utc_now
from .sandbox_env import SandboxEnvironment
from .scenario_loader import load_sandbox_scenarios_from_dir
from .schemas import SandboxCell, SandboxRecord, SandboxScenario, SandboxToolCall, SandboxTurn
from .scorers.sandbox import classify_action, summarise_run
from .study_runner import _git_commit
from .utils.budget import BudgetExceeded, BudgetGuard, call_cost, usage_from_metadata, refuse_unpriced
from .utils.hardware import collect_hardware_report
from .utils.hashing import sha256_bytes, sha256_text
from .utils.json_extract import extract_json
from .utils.logging import get_logger

log = get_logger(__name__)

RECORDS_NAME = "sandbox.jsonl"
TURNS_NAME = "sandbox_turns.jsonl"


def cells_from_config(config: SandboxRunConfig) -> list[SandboxCell]:
    cells = []
    for s, r, c, lim, f, v, d in itertools.product(
        config.solvability, config.rule_distance, config.checker_access, config.session_limit,
        config.task_framing, config.framing_variant, config.defer_available,
    ):
        # A paraphrase variant names a compliant-failure sentence only; pairing a non-canonical
        # variant with any other framing is meaningless, so those combinations are not emitted.
        if v != "canonical" and f != "compliant_failure":
            continue
        cells.append(SandboxCell(solvability=s, rule_distance=r, checker_access=c, session_limit=lim,
                                 task_framing=f, framing_variant=v, defer_available=d,
                                 tool_transport=config.tool_transport))
    return cells


def frozen_families(scenario_dir: str | Path) -> dict[str, dict]:
    """Families whose first frontier outcome has been observed and which must never run again."""
    path = Path(scenario_dir) / "frozen_families.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("families", {})


FRAMING_BANK_NAME = "framing_paraphrases.yaml"


def resolve_framing_bank(config: SandboxRunConfig, scenarios: list[SandboxScenario],
                         scenario_dir: str | Path) -> dict | None:
    """Validate and load the compliant-failure paraphrase bank for a wording-robustness run.

    Returns ``None`` when only the canonical sentence is requested (every existing config), so
    nothing changes for runs that do not use the bank. Otherwise returns a dict with the bank
    path, its SHA-256, and the rendered sentence (and its SHA-256) for each requested variant --
    the provenance recorded in freeze.json. Raises on any misuse so a paraphrase run cannot start
    unless the bank is present, pinned to the family, and the canonical entry is byte-identical to
    the family's committed addendum.
    """
    non_canonical = [v for v in config.framing_variant if v != "canonical"]
    if not non_canonical:
        return None
    if config.task_framing != ["compliant_failure"]:
        raise ValueError(
            "framing_variant beyond 'canonical' is only valid with task_framing == "
            f"['compliant_failure']; got {config.task_framing}. The bank names compliant-failure "
            "sentences only, so no other framing may carry a paraphrase."
        )
    path = Path(scenario_dir) / FRAMING_BANK_NAME
    if not path.exists():
        raise ValueError(f"framing_variant {non_canonical} requested but no bank at {path}")
    raw = path.read_bytes()
    bank = yaml.safe_load(raw.decode("utf-8")) or {}
    cf = bank.get("compliant_failure") or {}
    applies = set(bank.get("applies_to") or [])
    rendered: dict[str, str] = {}
    for scenario in scenarios:
        if scenario.id not in applies:
            raise ValueError(
                f"paraphrase bank does not apply to {scenario.id!r} (applies_to={sorted(applies)})"
            )
        if cf.get("canonical") != scenario.task_compliant_failure_addendum:
            raise ValueError(
                f"bank canonical sentence does not match {scenario.id}'s committed "
                "task_compliant_failure_addendum; the bank is not pinned to this frozen family"
            )
    for v in non_canonical:
        sentence = cf.get(v)
        if not sentence:
            raise ValueError(f"framing_variant {v!r} not found in {path}")
        rendered[v] = sentence
    return {
        "path": str(path.relative_to(Path.cwd())) if path.is_absolute() else str(path),
        "sha256": sha256_bytes(raw),
        "version": bank.get("version"),
        "canonical_sha256": sha256_text(cf["canonical"]),
        "rendered": {v: {"text": s, "sha256": sha256_text(s)} for v, s in rendered.items()},
    }


def framing_addendum_for(cell: SandboxCell, scenario: SandboxScenario,
                         bank: dict | None) -> str | None:
    """The framing sentence a cell renders: the family's own addendum, or a bank paraphrase when
    the cell is a non-canonical compliant-failure variant."""
    if cell.task_framing == "compliant_failure" and cell.framing_variant != "canonical":
        return (bank or {}).get("rendered", {}).get(cell.framing_variant, {}).get("text")
    return {
        "compliant_failure": scenario.task_compliant_failure_addendum,
        "authority_salience": scenario.task_authority_salience_addendum,
    }.get(cell.task_framing)


def select_sandbox_scenarios(config: SandboxRunConfig, *, allow_frozen: bool = False) -> list[SandboxScenario]:
    scenario_dir = config.scenario_dir or "scenarios_sandbox"
    # A directory holds every family, and the loader walks it recursively, so selecting by
    # directory alone silently widens a run the moment a second family lands -- including
    # re-running a frozen one. Pinning is mandatory rather than conventional.
    if not config.scenario_ids:
        raise ValueError(
            "sandbox runs must pin scenario_ids: scenario_dir alone selects every family in "
            f"{scenario_dir}/ and would re-run frozen ones (see scenarios_sandbox/frozen_families.json)"
        )
    scenarios = load_sandbox_scenarios_from_dir(scenario_dir)
    by_id = {s.id: s for s in scenarios}
    missing = [i for i in config.scenario_ids if i not in by_id]
    if missing:
        raise ValueError(f"sandbox scenario ids not found: {missing}")
    scenarios = [by_id[i] for i in config.scenario_ids]
    if not scenarios:
        raise ValueError("no sandbox scenarios selected (see scenarios_sandbox/)")

    families = {s.family for s in scenarios}
    if len(families) > 1 and not config.allow_multi_family:
        raise ValueError(
            f"one run, one family: {sorted(families)}. Set allow_multi_family to pool deliberately."
        )
    frozen = frozen_families(scenario_dir)
    blocked = sorted(f for f in families if not frozen.get(f, {}).get("may_run", True))
    if blocked and not allow_frozen:
        raise ValueError(
            f"{blocked} is frozen and may not be sampled again; re-derive outcomes from the "
            "committed logs instead (scenarios_sandbox/rescore_family1.py). Pass --allow-frozen "
            "only to characterise the harness, never to extend a result."
        )
    held = [s.id for s in scenarios if s.family_role == "confirmatory_heldout"]
    if held and not config.include_held_out:
        raise ValueError(
            f"{len(held)} confirmatory_heldout scenario(s) selected but include_held_out is false. "
            "Held-out families run all-or-nothing after the split is committed."
        )
    return scenarios


def _completed_keys(path: Path, *, retry_unmeasured: bool) -> set[tuple]:
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
            if retry_unmeasured and not (r.get("outcome") or {}).get("measured"):
                continue
            done.add((r["model"], SandboxCell.model_validate(r["cell"]).label(), r["scenario_id"], r["run_index"]))
        except (json.JSONDecodeError, KeyError, ValidationError):
            continue
    return done


def _parse_json_call(raw: str) -> tuple[SandboxToolCall | None, str | None]:
    obj, reason = extract_json(raw)
    if obj is None:
        return None, reason
    try:
        return SandboxToolCall.model_validate(obj), None
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", []))
        return None, f"schema_invalid: {loc}: {first.get('msg', exc)}"


def tool_specs(scenario: SandboxScenario, tools: list[str] | None = None) -> list[ToolSpec]:
    return [
        ToolSpec(name=s["name"], description=s["description"], parameters=s["parameters"])
        for s in sandbox_tool_specs(tools if tools is not None else list(scenario.available_tools),
                                    recipient_name=scenario.recipient_name,
                                    check_description=scenario.check_description)
    ]


def _write_manifest(out_dir: Path, config: SandboxRunConfig, scenarios: list[SandboxScenario],
                    cells: list[SandboxCell], system_hashes: dict[str, str],
                    framing_bank: dict | None = None) -> None:
    (out_dir / "config.yaml").write_text(yaml.safe_dump(config.model_dump(), sort_keys=False), encoding="utf-8")
    (out_dir / "models.txt").write_text("\n".join(config.models) + "\n", encoding="utf-8")
    commit = _git_commit()
    freeze = {
        "run_id": config.run_id,
        "sandbox_template_version": SANDBOX_TEMPLATE_VERSION,
        "tool_transport": config.tool_transport,
        "cells": [c.label() for c in cells],
        "runs_per_cell": config.execution.runs_per_variant,
        "models": list(config.models),
        "git_commit": commit,
        # Provenance for a wording-robustness run: the paraphrase bank's path, hash, and the exact
        # sentence (with its hash) rendered for each non-canonical variant. Absent for every run
        # that uses only the family's canonical sentence.
        **({"framing_bank": framing_bank} if framing_bank else {}),
        "scenarios": [
            {
                "id": s.id, "version": s.version, "sha256": s.source_sha256, "family": s.family,
                "family_role": s.family_role, "domain": s.domain, "tools": list(s.available_tools),
                "technical_step_cap": config.technical_step_cap or s.technical_step_cap,
                "session_limit_actions": s.session_limit_actions,
                "rule_text_sha256": sha256_text(s.rule_text), "task_sha256": sha256_text(s.task),
                "system_hash": system_hashes.get(s.id),
                "literature_tag": s.literature_tag, "human_evidence_class": s.human_evidence_class,
            }
            for s in scenarios
        ],
    }
    (out_dir / "freeze.json").write_text(json.dumps(freeze, indent=2), encoding="utf-8")
    (out_dir / "git_commit.txt").write_text(commit + "\n", encoding="utf-8")
    try:
        (out_dir / "hardware.txt").write_text(collect_hardware_report(), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        (out_dir / "hardware.txt").write_text(f"<hardware capture failed: {exc}>", "utf-8")


def _write_transcript(out_dir: Path, model: str, cell: SandboxCell, scenario: SandboxScenario, run_index: int,
                      system: str, turns: list[SandboxTurn], env: SandboxEnvironment, outcome) -> None:
    safe_model = model.replace(":", "_").replace("/", "_")
    path = out_dir / "transcripts" / safe_model / cell.label() / f"{scenario.id}__r{run_index}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {model} -- {cell.label()} -- {scenario.id} -- run {run_index}", "",
             f"terminated_by={outcome.terminated_by} any_boundary_crossing={outcome.any_boundary_crossing} "
             f"criterion={outcome.criterion_status} done={outcome.reported_check_passed}", "",
             "## System", "```", system, "```", ""]
    for t in turns:
        lines += [f"## Turn {t.turn_index} (actions before: {t.actions_before})", "", "**Shown to the model:**", "```",
                  t.observation, "```", ""]
        if t.assistant_text:
            lines += ["**Assistant text:**", "```", t.assistant_text[:2000], "```", ""]
        lines += ["**Tool calls:**", "```json", json.dumps(t.tool_calls, ensure_ascii=False)[:3000], "```", ""]
        for o in t.action_outcomes:
            lines.append(f"- action {o.action_index}: {o.tool} path={o.path} executed={o.executed} changed={o.changed} "
                         f"crossing={o.crossing_type} error={o.error}")
        lines.append("")
    lines += ["## Final workspace", "```", env.listing(), "```", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_sandbox(config: SandboxRunConfig, output_dir: str | Path | None = None, *,
                allow_frozen: bool = False, allow_unpriced: bool = False) -> Path:
    out_dir = Path(output_dir) if output_dir else Path("outputs") / config.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # First, before anything else: a billing provider may not run a model the cap cannot price.
    refuse_unpriced(config.models, config.provider, allow_unpriced=allow_unpriced)

    scenarios = select_sandbox_scenarios(config, allow_frozen=allow_frozen)
    cells = cells_from_config(config)
    framing_bank = resolve_framing_bank(config, scenarios, config.scenario_dir or "scenarios_sandbox")
    transport = config.tool_transport

    provider = get_provider(config.provider)
    if transport == "native" and not getattr(provider, "supports_tools", False):
        raise NotImplementedError(f"provider {config.provider!r} has no native tool calling; use tool_transport: json_schema")
    if transport == "json_schema" and not hasattr(provider, "chat"):
        raise NotImplementedError(f"provider {config.provider!r} has no chat() method")

    gen = config.generation
    base_format = _resolve_format("schema", schema="sandbox") if transport == "json_schema" else None
    base_options = GenerationOptions(
        temperature=gen.temperature, top_p=gen.top_p, max_tokens=gen.max_tokens, seed=gen.seed,
        timeout_seconds=config.execution.timeout_seconds, think=gen.think, format=None,
        prompt_caching=config.prompt_caching,
    )
    systems = {s.id: build_sandbox_system(role_line=s.role_line, transport=transport) for s in scenarios}
    _write_manifest(out_dir, config, scenarios, cells, {k: sha256_text(v) for k, v in systems.items()},
                    framing_bank=framing_bank)

    records_path, turns_path = out_dir / RECORDS_NAME, out_dir / TURNS_NAME
    done_keys = _completed_keys(records_path, retry_unmeasured=config.retry_unmeasured)
    if done_keys:
        log.info("resuming: %d runs already complete, will be skipped", len(done_keys))

    budget = BudgetGuard(run_id=config.run_id)
    log.info("budget: cap $%.2f, $%.4f already on the ledger, $%.4f remaining",
             budget.cap_usd, budget.spent_before, budget.remaining())
    aborted: str | None = None
    n_runs = n_calls = 0

    for model in config.models:
        for cell in cells:
            for scenario in scenarios:
                system = systems[scenario.id]
                system_hash = sha256_text(system)
                cap = config.technical_step_cap or scenario.technical_step_cap
                cell_tools = cell.tools(list(scenario.available_tools))
                specs = tool_specs(scenario, cell_tools)
                fmt = _format_for_tools(base_format, cell_tools) if base_format else None
                for run_index in range(1, config.execution.runs_per_variant + 1):
                    if aborted:
                        break
                    key = (model, cell.label(), scenario.id, run_index)
                    if key in done_keys:
                        continue
                    attempt_id = uuid.uuid4().hex[:12]
                    call_seed = None if gen.seed is None else gen.seed + run_index - 1
                    options = replace(base_options, seed=call_seed, format=fmt)
                    env = SandboxEnvironment(scenario, cell, read_max_chars=config.read_max_chars,
                                             listing_max_chars=config.listing_max_chars)
                    addendum = framing_addendum_for(cell, scenario, framing_bank)
                    opening = build_sandbox_opening(
                        task=scenario.task,
                        rule_text=scenario.rule_text if cell.rule_distance == "adjacent" else None,
                        framing_addendum=addendum, listing=env.listing(),
                        available_tools=cell_tools, recipient_name=scenario.recipient_name,
                        transport=transport, check_description=scenario.check_description,
                    )
                    prompt_hash = sandbox_prompt_hash(f"<<SYSTEM>>\n{system}\n\n<<USER>>\n{opening}")
                    if transport == "native":
                        messages: list = [SystemMsg(system), UserMsg(opening)]
                    else:
                        messages = [{"role": "system", "content": system}, {"role": "user", "content": opening}]

                    turns: list[SandboxTurn] = []
                    assistant_texts: list[str] = []
                    shown = opening
                    terminated_by: str | None = None
                    unmeasured_reason: str | None = None
                    consecutive_parse_failures = 0
                    turn_index = 0
                    last_result = None

                    while terminated_by is None:
                        turn_index += 1
                        try:
                            budget.check_before_call(model)
                        except BudgetExceeded as exc:
                            log.error("%s", exc)
                            aborted = str(exc)
                            break
                        log.info("%s | %s | %s r%d | turn %d (actions %d)", model, cell.label(), scenario.id,
                                 run_index, turn_index, env.actions)
                        if transport == "native":
                            result = provider.chat_tools(messages=messages, tools=specs, model=model, options=options)
                        else:
                            result = provider.chat(messages=messages, model=model, options=options)
                        last_result = result
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
                        turn = SandboxTurn(
                            turn_index=turn_index, actions_before=env.actions, observation=shown,
                            raw_response=result.raw_response or "", parsed_ok=False,
                            latency_seconds=result.latency_seconds, usage=usage, cost_usd=cost,
                            finish_reason=meta.get("finish_reason") or meta.get("stop_reason"), truncated=truncated,
                            errors=([] if result.ok else [result.error or "unknown_error"]),
                        )
                        if not result.ok:
                            err = result.error or "unknown_error"
                            terminated_by = "stopped_early"
                            unmeasured_reason = "tools_unsupported" if err.startswith("tools_unsupported") else f"transport_error:{err[:60]}"
                            turn.parse_error = err
                        elif truncated:
                            terminated_by, unmeasured_reason = "stopped_early", "truncated"
                        elif refused:
                            terminated_by, unmeasured_reason = "stopped_early", "provider_refusal"
                        else:
                            calls: list[tuple[str, dict, str | None, str | None]] = []  # (name, args, call_id, arg_error)
                            if transport == "native":
                                turn.assistant_text = result.text or ""
                                if turn.assistant_text:
                                    assistant_texts.append(turn.assistant_text)
                                for tc in result.tool_calls:
                                    calls.append((tc.name, tc.arguments, tc.id, tc.arguments_error))
                                turn.parsed_ok = True
                                if not calls:
                                    terminated_by = "ended_without_done"
                            else:
                                call, perr = _parse_json_call(result.raw_response)
                                if call is None:
                                    turn.parse_error = perr
                                    consecutive_parse_failures += 1
                                    if consecutive_parse_failures >= config.max_consecutive_parse_failures:
                                        terminated_by, unmeasured_reason = "stopped_early", f"no_parsed_call_x{consecutive_parse_failures}"
                                else:
                                    consecutive_parse_failures = 0
                                    turn.parsed_ok = True
                                    calls.append((call.tool, call.arguments.model_dump(), None, None))

                            results: list[ToolResult] = []
                            obs_results: list[tuple[str, str]] = []
                            for name, args, call_id, arg_error in calls:
                                turn.tool_calls.append({"tool": name, "arguments": args, "id": call_id})
                                if arg_error:
                                    entry = env.execute(name, {}, turn=turn_index)
                                    entry["error"] = f"arguments_unreadable: {arg_error[:80]}"
                                    entry["executed"] = False
                                    entry["result"] = f"Error: {entry['error']}."
                                else:
                                    entry = env.execute(name, args, turn=turn_index)
                                turn.executed.append(entry)
                                turn.action_outcomes.append(classify_action(env, entry))
                                text = str(entry.get("result") or "")
                                results.append(ToolResult(call_id=call_id or f"c{env.actions}", name=name,
                                                          content=text, is_error=not entry.get("executed")))
                                obs_results.append((name, text))

                            if terminated_by is None:
                                if env.done_call is not None:
                                    terminated_by = "done"
                                elif env.defer_call is not None:
                                    terminated_by = "deferred"
                                elif env.session_limit_reached():
                                    terminated_by = "schedule"
                                elif env.actions >= cap or turn_index >= cap:
                                    terminated_by = "technical_cap"

                            if terminated_by is None:
                                notice = env.notice()
                                remaining = env.actions_remaining()
                                if transport == "native":
                                    messages.append(AssistantMsg(text=result.text or "", tool_calls=list(result.tool_calls),
                                                                 replay=result.replay))
                                    extra = sandbox_extra_text(listing=env.listing(), notice=notice, actions_remaining=remaining)
                                    messages.append(ToolResultsMsg(results=results, extra_text=extra))
                                    shown = "\n\n".join([f"Result of {n}:\n{t}" for n, t in obs_results] + [extra])
                                else:
                                    messages.append({"role": "assistant", "content": result.raw_response})
                                    if not obs_results:
                                        obs_results = [("(no tool call)", f"Your last reply could not be read as a tool call: {turn.parse_error}. No change was made.")]
                                    shown = build_sandbox_observation(results=obs_results, listing=env.listing(),
                                                                      notice=notice, actions_remaining=remaining)
                                    messages.append({"role": "user", "content": shown})

                        turns.append(turn)
                        _append_jsonl(turns_path, {
                            "attempt_id": attempt_id, "model": model, "cell": cell.model_dump(),
                            "scenario_id": scenario.id, "run_index": run_index, **turn.model_dump(mode="json"),
                        })
                        if aborted and terminated_by is None:
                            break

                    if aborted:
                        break  # key stays open; orphan turn rows carry the attempt_id

                    outcome = summarise_run(env, terminated_by=terminated_by or "stopped_early",
                                            unmeasured_reason=unmeasured_reason, n_turns=len(turns),
                                            assistant_texts=assistant_texts)
                    turn_costs = [t.cost_usd for t in turns if t.cost_usd is not None]
                    meta = (last_result.provider_metadata if last_result else {}) or {}
                    record = SandboxRecord(
                        run_id=config.run_id, timestamp=_utc_now(), attempt_id=attempt_id,
                        provider=config.provider, model=model,
                        model_digest=getattr(last_result, "model_digest", None) if last_result else None,
                        model_resolved=meta.get("model"),
                        scenario_id=scenario.id, scenario_version=scenario.version,
                        scenario_sha256=scenario.source_sha256, family=scenario.family,
                        family_role=scenario.family_role, domain=scenario.domain,
                        literature_tag=scenario.literature_tag, human_evidence_class=scenario.human_evidence_class,
                        cell=cell, run_index=run_index, role_line=scenario.role_line,
                        system_hash=system_hash, prompt_hash=prompt_hash,
                        sandbox_template_version=SANDBOX_TEMPLATE_VERSION, technical_step_cap=cap,
                        session_limit_actions=scenario.session_limit_actions if cell.session_limit == "on" else None,
                        temperature=gen.temperature, top_p=gen.top_p, seed=call_seed, max_tokens=gen.max_tokens,
                        think=gen.think, format=("schema" if transport == "json_schema" else None),
                        n_turns=len(turns), turns=turns, outcome=outcome, executed_calls=list(env.calls),
                        initial_files=dict(env.initial_files), final_files=dict(env.files),
                        stopped_early=(terminated_by == "stopped_early"),
                        complete=True, cost_usd=round(sum(turn_costs), 6) if turn_costs else None,
                    )
                    _append_jsonl(records_path, record.model_dump(mode="json"))
                    _write_transcript(out_dir, model, cell, scenario, run_index, system, turns, env, outcome)
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
    log.info("sandbox run done: %d runs, %d calls, output in %s", n_runs, n_calls, out_dir)
    return out_dir
