"""Multi-turn pushback runner (brief §17).

Opens each scenario with a clean request, then applies the scenario's ordered
pushback turns, scoring whether the boundary survives each turn. The full
conversation transcript is saved so erosion can be inspected by hand.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from . import PROMPT_TEMPLATE_VERSION
from .config import RunConfig
from .prompt_builder import (
    SYSTEM_PROMPTS,
    build_full_prompt,
    build_pushback_message,
    split_system_user,
)
from .providers import get_provider
from .providers.base import GenerationOptions
from .scenario_loader import select_scenarios
from .schemas import MultiTurnRecord, MultiTurnTurnResult, Scenario
from .scorers.multi_turn import boundary_survival_depth
from .scorers.rule_based import score_boundary_preserved
from .runner import _parse_decision, _resolve_format, _utc_now
from .utils.budget import BudgetExceeded, BudgetGuard, call_cost, usage_from_metadata
from .utils.hardware import collect_hardware_report
from .utils.logging import get_logger

log = get_logger(__name__)


def _append_jsonl(path: Path, obj: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _completed_keys(path: Path) -> set[tuple]:
    done: set[tuple] = set()
    if not path.exists():
        return done
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                r = json.loads(line)
                done.add((r["model"], r["scenario_id"]))
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def _write_transcript(out_dir: Path, model: str, scenario: Scenario, turns) -> None:
    safe_model = model.replace(":", "_").replace("/", "_")
    path = out_dir / "transcripts" / f"{safe_model}__{scenario.id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {model} — {scenario.id}", ""]
    for t in turns:
        lines += [
            f"## Turn {t.turn_index} [{t.pressure_type}]",
            f"**User:** {t.user_message}",
            "",
            f"**Assistant (parsed_ok={t.parsed_ok}, boundary_preserved={t.boundary_preserved}):**",
            "```json",
            (t.raw_response or "")[:1200],
            "```",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_multi_turn(config: RunConfig, output_dir: str | Path | None = None) -> Path:
    out_dir = Path(output_dir) if output_dir else Path("outputs") / config.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    scenarios = [
        s
        for s in select_scenarios(
            scenario_dir=config.scenario_dir, scenario_ids=config.scenario_ids
        )
        if s.pushback_sequence
    ]
    if not scenarios:
        raise ValueError(
            "no scenarios with a pushback_sequence found; multi-turn needs them"
        )

    (out_dir / "config.yaml").write_text(
        yaml.safe_dump(config.model_dump(), sort_keys=False), encoding="utf-8"
    )
    try:
        (out_dir / "hardware.txt").write_text(collect_hardware_report(), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        (out_dir / "hardware.txt").write_text(f"<hardware capture failed: {exc}>", "utf-8")

    provider = get_provider(config.provider)
    if not hasattr(provider, "chat"):
        raise NotImplementedError(f"provider {config.provider!r} has no chat() method")

    gen = config.generation
    options = GenerationOptions(
        temperature=gen.temperature, top_p=gen.top_p, max_tokens=gen.max_tokens,
        seed=gen.seed, timeout_seconds=config.execution.timeout_seconds,
        think=gen.think, format=_resolve_format(gen.format),
    )

    records_path = out_dir / "multi_turn.jsonl"
    done = _completed_keys(records_path)

    # Enforced cumulative spend cap (utils/budget.py). Local Ollama models are
    # unpriced and therefore uncovered, which is fine -- they are free -- but the
    # guard reports how many such calls it saw so "capped" is never overclaimed.
    budget = BudgetGuard(run_id=config.run_id)
    log.info(
        "budget: cap $%.2f, $%.4f already on the ledger, $%.4f remaining",
        budget.cap_usd, budget.spent_before, budget.remaining(),
    )
    aborted: str | None = None

    for model in config.models:
        if aborted:
            break
        for scenario in scenarios:
            if aborted:
                break
            if (model, scenario.id) in done:
                continue

            system = SYSTEM_PROMPTS[config.system_prompt_style]
            _, opening_user = split_system_user(
                build_full_prompt(
                    scenario, scenario.variants[0],
                    system_prompt_style=config.system_prompt_style, role=config.role,
                )
            )
            # Replace the variant message in the rendered opening with the
            # designated opening message (neutral request).
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": opening_user},
            ]

            turn_specs = [("neutral", scenario.opening_message())] + [
                (pb.pressure_type, build_pushback_message(pb.user_message))
                for pb in scenario.pushback_sequence
            ]

            turns: list[MultiTurnTurnResult] = []
            pushback_flags: list[bool] = []
            first_failure: int | None = None

            for idx, (ptype, _user_text) in enumerate(turn_specs):
                if idx == 0:
                    user_content = opening_user
                else:
                    user_content = turn_specs[idx][1]
                    messages.append({"role": "user", "content": user_content})

                log.info("%s | %s | turn %d [%s]", model, scenario.id, idx, ptype)
                try:
                    budget.check_before_call(model)
                except BudgetExceeded as exc:
                    # Stop cleanly: the conversation so far is still written, so a
                    # partial run is inspectable rather than lost.
                    log.error("%s", exc)
                    aborted = str(exc)
                    break
                result = provider.chat(messages=messages, model=model, options=options)

                decision, parse_error = (None, None)
                if result.ok:
                    decision, parse_error = _parse_decision(result.raw_response)
                else:
                    parse_error = result.error

                meta = result.provider_metadata or {}
                # Derived before charging so the record is complete even on the
                # call that trips the cap -- the ledger records that call's usage,
                # and a record showing None beside it would misrepresent what was
                # actually spent.
                usage = usage_from_metadata(meta)
                cost = call_cost(model, usage)
                try:
                    budget.charge(model, meta)
                except BudgetExceeded as exc:
                    log.error("%s", exc)
                    aborted = str(exc)

                boundary = score_boundary_preserved(decision) if decision else None
                turns.append(
                    MultiTurnTurnResult(
                        turn_index=idx, pressure_type=ptype, user_message=user_content,
                        raw_response=result.raw_response, parsed_ok=decision is not None,
                        parse_error=parse_error, parsed_response=decision,
                        boundary_preserved=boundary,
                        latency_seconds=result.latency_seconds,
                        errors=([] if result.ok else [result.error or "unknown_error"]),
                        usage=usage, cost_usd=cost,
                        finish_reason=meta.get("finish_reason") or meta.get("stop_reason"),
                        truncated=bool(meta.get("truncated")),
                    )
                )
                # Keep the conversation going with the model's own reply.
                messages.append({"role": "assistant", "content": result.raw_response})

                if idx > 0:
                    pushback_flags.append(bool(boundary))
                if boundary is False and first_failure is None:
                    first_failure = idx
                if aborted:
                    break

            turn_costs = [t.cost_usd for t in turns if t.cost_usd is not None]
            record = MultiTurnRecord(
                run_id=config.run_id, timestamp=_utc_now(), provider=config.provider,
                model=model, scenario_id=scenario.id, scenario_version=scenario.version,
                role=config.role or scenario.role,
                system_prompt_style=config.system_prompt_style,
                prompt_template_version=PROMPT_TEMPLATE_VERSION,
                temperature=gen.temperature, top_p=gen.top_p, seed=gen.seed,
                turns=turns,
                boundary_survival_depth=boundary_survival_depth(pushback_flags),
                first_failure_turn=first_failure,
                cost_usd=round(sum(turn_costs), 6) if turn_costs else None,
            )
            _append_jsonl(records_path, record.model_dump(mode="json"))
            _write_transcript(out_dir, model, scenario, turns)

    log.info("budget: %s", budget.summary())
    (out_dir / "spend.txt").write_text(
        budget.summary() + ("\nABORTED: " + aborted if aborted else "") + "\n",
        encoding="utf-8",
    )
    if aborted:
        # Loud, and not a success. A silently truncated run would be read as a
        # complete one.
        raise BudgetExceeded(aborted)
    log.info("multi-turn done: output in %s", out_dir)
    return out_dir
