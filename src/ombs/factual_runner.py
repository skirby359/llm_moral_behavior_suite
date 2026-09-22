"""factual_denial runner — asymmetry A5 (notes/PHASE-20-RELATIONAL.md).

Structurally parallel to ``multi_turn.py`` on purpose: same opening-then-escalate
shape, same per-turn scoring, same transcript output. What differs is the
construct. ``multi_turn.py`` asks "does the boundary hold under pressure";
this asks "does a **true, checkable, non-boundary** claim hold under denial".

The parallel structure is what makes A5's central prediction testable — that a
model can score perfectly on boundary preservation and badly on truth
persistence. Two metrics of the same shape over the same models, differing only
in what is being defended.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from pydantic import ValidationError

from . import PROMPT_TEMPLATE_VERSION
from .config import RunConfig
from .prompt_builder import (
    FACTUAL_TEMPLATE_VERSION,
    SYSTEM_PROMPTS,
    build_factual_prompt,
    build_factual_pushback_message,
    factual_prompt_hash,
)
from .providers import get_provider
from .providers.base import GenerationOptions
from .runner import _resolve_format, _utc_now
from .scenario_loader import select_scenarios
from .schemas import FactualPosition, FactualRecord, FactualTurnResult, Scenario
from .scorers.factual import correction_persistence, opening_was_correct, score_turn
from .utils.budget import BudgetExceeded, BudgetGuard, call_cost, usage_from_metadata
from .utils.hardware import collect_hardware_report
from .utils.json_extract import extract_json
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


def _parse_position(raw: str) -> tuple[FactualPosition | None, str | None]:
    obj, reason = extract_json(raw)
    if obj is None:
        return None, reason
    try:
        return FactualPosition.model_validate(obj), None
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", []))
        return None, f"schema_invalid: {loc}: {first.get('msg', exc)}"


def _write_transcript(out_dir: Path, model: str, scenario: Scenario, turns) -> None:
    safe_model = model.replace(":", "_").replace("/", "_")
    path = out_dir / "transcripts" / f"{safe_model}__{scenario.id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    probe = scenario.truth_probe
    lines = [
        f"# {model} — {scenario.id}",
        "",
        f"**Question:** {probe.question}" if probe else "",
        f"**True value:** {probe.true_value}  ·  **Value the user insists on:** "
        f"{probe.false_value}" if probe else "",
        f"**Derivation:** {probe.derivation}" if probe else "",
        "",
    ]
    for t in turns:
        p = t.parsed_response
        asserted = p.asserted_value if p else "<unparsed>"
        stance = p.stance if p else "?"
        lines += [
            f"## Turn {t.turn_index} [{t.pressure_type}]",
            f"**User:** {t.user_message}",
            "",
            f"**Asserted:** `{asserted}`  ·  stance=`{stance}`  ·  "
            f"held=`{t.held}`  ·  signals_disagree=`{t.signals_disagree}`",
            "",
            "```json",
            (t.raw_response or "")[:1200],
            "```",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_factual_denial(config: RunConfig, output_dir: str | Path | None = None) -> Path:
    out_dir = Path(output_dir) if output_dir else Path("outputs") / config.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    scenarios = [
        s
        for s in select_scenarios(
            scenario_dir=config.scenario_dir, scenario_ids=config.scenario_ids
        )
        if s.truth_probe and s.pushback_sequence
    ]
    if not scenarios:
        raise ValueError(
            "no scenarios with both a truth_probe and a pushback_sequence found; "
            "factual_denial needs both (see scenarios_a5/)"
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
        think=gen.think, format=_resolve_format(gen.format, schema="factual"),
    )

    records_path = out_dir / "factual_denial.jsonl"
    done = _completed_keys(records_path)

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

            probe = scenario.truth_probe
            system = SYSTEM_PROMPTS[config.system_prompt_style]
            opening_user = build_factual_prompt(
                scenario, scenario.opening_message(), role=config.role
            )
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": opening_user},
            ]
            p_hash = factual_prompt_hash(f"<<SYSTEM>>\n{system}\n\n<<USER>>\n{opening_user}")

            turn_specs = [("neutral", opening_user)] + [
                (pb.pressure_type, build_factual_pushback_message(pb.user_message))
                for pb in scenario.pushback_sequence
            ]

            turns: list[FactualTurnResult] = []
            held_flags: list[bool] = []
            first_abandonment: int | None = None

            for idx, (ptype, user_content) in enumerate(turn_specs):
                if idx > 0:
                    messages.append({"role": "user", "content": user_content})

                log.info("%s | %s | turn %d [%s]", model, scenario.id, idx, ptype)
                try:
                    budget.check_before_call(model)
                except BudgetExceeded as exc:
                    log.error("%s", exc)
                    aborted = str(exc)
                    break

                result = provider.chat(messages=messages, model=model, options=options)

                position, parse_error = (None, None)
                if result.ok:
                    position, parse_error = _parse_position(result.raw_response)
                else:
                    parse_error = result.error

                meta = result.provider_metadata or {}
                # Derived before charging so the record is complete even on the call
                # that trips the cap (see the same note in multi_turn.py).
                usage = usage_from_metadata(meta)
                cost = call_cost(model, usage)
                try:
                    budget.charge(model, meta)
                except BudgetExceeded as exc:
                    log.error("%s", exc)
                    aborted = str(exc)

                signals = score_turn(probe, position) if position else {}
                turns.append(
                    FactualTurnResult(
                        turn_index=idx, pressure_type=ptype, user_message=user_content,
                        raw_response=result.raw_response, parsed_ok=position is not None,
                        parse_error=parse_error, parsed_response=position,
                        self_reported_abandonment=signals.get("self_reported_abandonment"),
                        value_abandonment=signals.get("value_abandonment"),
                        drifted_elsewhere=signals.get("drifted_elsewhere"),
                        signals_disagree=bool(signals.get("signals_disagree")),
                        held=signals.get("held"),
                        latency_seconds=result.latency_seconds,
                        usage=usage, cost_usd=cost,
                        finish_reason=meta.get("finish_reason") or meta.get("stop_reason"),
                        truncated=bool(meta.get("truncated")),
                        errors=([] if result.ok else [result.error or "unknown_error"]),
                    )
                )
                messages.append({"role": "assistant", "content": result.raw_response})

                if idx > 0:
                    held_flags.append(bool(signals.get("held")))
                if signals.get("held") is False and first_abandonment is None:
                    first_abandonment = idx
                if aborted:
                    break

            turn_costs = [t.cost_usd for t in turns if t.cost_usd is not None]
            record = FactualRecord(
                run_id=config.run_id, timestamp=_utc_now(), provider=config.provider,
                model=model, scenario_id=scenario.id, scenario_version=scenario.version,
                role=config.role or scenario.role,
                system_prompt_style=config.system_prompt_style,
                prompt_template_version=PROMPT_TEMPLATE_VERSION,
                factual_template_version=FACTUAL_TEMPLATE_VERSION, prompt_hash=p_hash,
                temperature=gen.temperature, top_p=gen.top_p, seed=gen.seed,
                question=probe.question, true_value=probe.true_value,
                false_value=probe.false_value,
                turns=turns,
                correction_persistence=correction_persistence(held_flags),
                first_abandonment_turn=first_abandonment,
                opening_correct=opening_was_correct(
                    probe, turns[0].parsed_response if turns else None
                ),
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
        raise BudgetExceeded(aborted)
    log.info("factual-denial done: output in %s", out_dir)
    return out_dir
