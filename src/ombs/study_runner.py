"""Study 1 / Study 2 runner (externaldocs/REVISED_PROTOCOL.md; Validation Addendum, 9 Sep 2026).

    models x safeguard arms x study scenarios x manipulation levels x repeats -> study.jsonl

Structurally a sibling of ``factual_runner.py``: same budget guard, same resume
semantics, same manifest. What differs is the measurement -- the model picks from
an explicit option menu and the outcome is read from the scenario's authored
option table (``scorers/discrimination.py``).

What this runner refuses to do, by design:

- run a ``confirmatory_heldout`` family unless ``include_held_out`` is set, and then
  it runs **all** of them. There is no per-family outcome filter anywhere in this
  module; selecting confirmatory items by result is the bias the addendum forbids.
- render the option menu in a hidden order: every record carries the permutation
  and the seed that produced it.
- reuse one pinned seed across repeats: when ``generation.seed`` is set, repeat
  ``k`` is sent ``seed + k - 1`` and the record stores the seed actually used. A
  pinned seed produced a meaningless +/- 0.00 once already (W2, ``qwen2.5:3b``).
- score a truncated response: ``truncated`` from the provider forces the outcome
  to unmeasured, whatever the partial JSON says.

Wave 1 is single-turn. The erosion ladder (multi-turn) is wave 2.
"""

from __future__ import annotations

import copy
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import yaml
from pydantic import ValidationError

from .config import StudyRunConfig
from .interventions import (
    INTERVENTIONS_VERSION,
    TOOL_ONLY_IDS,
    arm_factors,
    intervention_text,
    render_all,
)
from .prompt_builder import (
    STUDY_TEMPLATE,
    STUDY_TEMPLATE_VERSION,
    SYSTEM_PROMPTS,
    build_study_full_prompt,
    split_system_user,
    study_option_order,
    study_prompt_hash,
)
from .providers import get_provider
from .providers.base import GenerationOptions
from .runner import _resolve_format, _utc_now
from .scenario_loader import select_scenarios
from .schemas import Scenario, StudyDecision, StudyOutcome, StudyRecord, StudyTurn, Variant
from .scorers.discrimination import classify_outcome
from .utils.budget import BudgetExceeded, BudgetGuard, call_cost, usage_from_metadata
from .utils.hardware import collect_hardware_report
from .utils.hashing import sha256_text
from .utils.json_extract import extract_json
from .utils.logging import get_logger

log = get_logger(__name__)

RECORDS_NAME = "study.jsonl"


def _append_jsonl(path: Path, obj: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _completed_keys(path: Path) -> set[tuple]:
    """(model, floor, intervention, scenario_id, variant_id, run_index) already written."""
    done: set[tuple] = set()
    if not path.exists():
        return done
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            done.add((r["model"], r["floor"], r["intervention"], r["scenario_id"],
                      r["variant_id"], r["run_index"]))
        except (json.JSONDecodeError, KeyError):
            continue
    return done


def _parse_study_decision(raw: str) -> tuple[StudyDecision | None, str | None]:
    obj, reason = extract_json(raw)
    if obj is None:
        return None, reason
    try:
        return StudyDecision.model_validate(obj), None
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", []))
        return None, f"schema_invalid: {loc}: {first.get('msg', exc)}"


def select_study_scenarios(config: StudyRunConfig) -> list[Scenario]:
    """Study scenarios for this run, with the held-out guard applied.

    The guard is all-or-nothing on purpose: either every selected held-out family
    runs, or the run refuses to start. Filtering by factor / permissibility is
    allowed because those are design axes, not outcomes.
    """
    scenarios = [
        s for s in select_scenarios(
            scenario_dir=config.scenario_dir, scenario_ids=config.scenario_ids
        )
        if s.study is not None
    ]
    if config.factors:
        scenarios = [s for s in scenarios if s.study.manipulation.factor in config.factors]
    if config.permissibility:
        scenarios = [s for s in scenarios if s.study.permissibility in config.permissibility]
    if not scenarios:
        raise ValueError(
            "no study scenarios selected (need a `study` block; see scenarios_study1/)"
        )
    held = [s.id for s in scenarios if s.study.family_role == "confirmatory_heldout"]
    if held and not config.include_held_out:
        raise ValueError(
            f"{len(held)} confirmatory_heldout scenario(s) selected but include_held_out is "
            "false. Held-out families run all-or-nothing after the split is committed "
            "(scenarios_study1/README.md, Gate 4); set include_held_out: true to run them, "
            "or point scenario_dir at the development set."
        )
    return scenarios


def _variants_for(scenario: Scenario, config: StudyRunConfig) -> list[Variant]:
    vs = list(scenario.variants)
    if config.levels:
        vs = [v for v in vs if v.level in config.levels]
    if config.variants:
        vs = [v for v in vs if v.id in config.variants]
    return vs


def _repeats_for(variant: Variant, scenario: Scenario, config: StudyRunConfig) -> int:
    if variant.id == scenario.study.control_variant_id:
        return config.control_runs_per_variant
    return config.execution.runs_per_variant


def _format_for_call(base_format: str | dict | None, order: list[str]) -> str | dict | None:
    """Constrain `chosen_option` to the ids actually rendered, when a schema is in use."""
    if not isinstance(base_format, dict):
        return base_format
    fmt = copy.deepcopy(base_format)
    props = fmt.get("properties", {})
    if "chosen_option" in props:
        props["chosen_option"] = {"type": "string", "enum": list(order)}
    return fmt


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10, check=False
        )
        return out.stdout.strip() or "<unavailable>"
    except Exception:  # noqa: BLE001 - metadata must never fail the run
        return "<unavailable>"


def _write_manifest(out_dir: Path, config: StudyRunConfig, scenarios: list[Scenario]) -> None:
    (out_dir / "config.yaml").write_text(
        yaml.safe_dump(config.model_dump(), sort_keys=False), encoding="utf-8"
    )
    (out_dir / "models.txt").write_text("\n".join(config.models) + "\n", encoding="utf-8")
    (out_dir / "study_template.md").write_text(
        f"# Study template v{STUDY_TEMPLATE_VERSION}\n\n"
        f"## System prompt style: {config.system_prompt_style}\n\n"
        f"```\n{SYSTEM_PROMPTS[config.system_prompt_style]}\n```\n\n"
        f"## Template\n\n```\n{STUDY_TEMPLATE}\n```\n",
        encoding="utf-8",
    )
    (out_dir / "interventions.md").write_text(render_all(config.floor), encoding="utf-8")
    manifest = {
        "run_id": config.run_id,
        "floor": config.floor,
        "interventions": list(config.interventions),
        "interventions_version": INTERVENTIONS_VERSION,
        "study_template_version": STUDY_TEMPLATE_VERSION,
        "git_commit": _git_commit(),
        "scenarios": [
            {
                "id": s.id,
                "version": s.version,
                "sha256": s.source_sha256,
                "family": s.study.family,
                "family_role": s.study.family_role,
                "domain": s.study.domain,
                "permissibility": s.study.permissibility,
                "factor": s.study.manipulation.factor,
                "human_evidence_class": s.study.manipulation.human_evidence_class,
                "control_variant_id": s.study.control_variant_id,
                "focal_action_id": s.study.focal_action_id,
                "levels": [v.level for v in s.variants],
                "options": [o.id for o in s.study.options],
            }
            for s in scenarios
        ],
    }
    (out_dir / "scenario_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    (out_dir / "git_commit.txt").write_text(manifest["git_commit"] + "\n", encoding="utf-8")
    try:
        (out_dir / "hardware.txt").write_text(collect_hardware_report(), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        (out_dir / "hardware.txt").write_text(f"<hardware capture failed: {exc}>", "utf-8")


def run_study(config: StudyRunConfig, output_dir: str | Path | None = None) -> Path:
    out_dir = Path(output_dir) if output_dir else Path("outputs") / config.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    scenarios = select_study_scenarios(config)
    _write_manifest(out_dir, config, scenarios)

    provider = get_provider(config.provider)
    gen = config.generation
    base_format = _resolve_format(gen.format, schema="study")
    base_options = GenerationOptions(
        temperature=gen.temperature, top_p=gen.top_p, max_tokens=gen.max_tokens,
        seed=gen.seed, timeout_seconds=config.execution.timeout_seconds,
        think=gen.think, format=base_format,
    )

    records_path = out_dir / RECORDS_NAME
    prompts_path = out_dir / "prompts.jsonl"
    done = _completed_keys(records_path)
    if done:
        log.info("resuming: %d calls already complete, will be skipped", len(done))

    arms = [a for a in config.interventions if a not in TOOL_ONLY_IDS]
    for skipped in set(config.interventions) - set(arms):
        log.warning("%s is a tool-path arm and is skipped by the chat runner", skipped)

    budget = BudgetGuard(run_id=config.run_id)
    log.info(
        "budget: cap $%.2f, $%.4f already on the ledger, $%.4f remaining",
        budget.cap_usd, budget.spent_before, budget.remaining(),
    )
    aborted: str | None = None
    total = unmeasured = 0

    for model in config.models:
        for arm in arms:
            for scenario in scenarios:
                st = scenario.study
                itext = intervention_text(arm, floor=config.floor, rule=scenario.expected_boundary)
                for variant in _variants_for(scenario, config):
                    for run_index in range(1, _repeats_for(variant, scenario, config) + 1):
                        if aborted:
                            break
                        key = (model, config.floor, arm, scenario.id, variant.id, run_index)
                        if key in done:
                            continue

                        order, order_seed = study_option_order(
                            scenario_id=scenario.id, variant_id=variant.id, intervention=arm,
                            floor=config.floor, run_index=run_index,
                            option_ids=[o.id for o in st.options],
                            randomize=config.randomize_option_order,
                        )
                        full = build_study_full_prompt(
                            scenario, variant, system_prompt_style=config.system_prompt_style,
                            intervention_text=itext, role=config.role, order=order,
                        )
                        p_hash = study_prompt_hash(full)
                        system, user = split_system_user(full)
                        s_hash = sha256_text(system)
                        call_seed = None if gen.seed is None else gen.seed + run_index - 1
                        options = replace(
                            base_options, seed=call_seed, format=_format_for_call(base_format, order)
                        )

                        try:
                            budget.check_before_call(model)
                        except BudgetExceeded as exc:
                            log.error("%s", exc)
                            aborted = str(exc)
                            break

                        log.info("%s | %s | %s/%s run %d", model, arm, scenario.id, variant.id, run_index)
                        result = provider.generate(
                            system=system, prompt=user, model=model, options=options
                        )

                        decision, parse_error = (None, None)
                        if result.ok:
                            decision, parse_error = _parse_study_decision(result.raw_response)
                        else:
                            parse_error = result.error

                        meta = result.provider_metadata or {}
                        usage = usage_from_metadata(meta)
                        cost = call_cost(model, usage)
                        try:
                            budget.charge(model, meta)
                        except BudgetExceeded as exc:
                            log.error("%s", exc)
                            aborted = str(exc)

                        truncated = bool(meta.get("truncated"))
                        if truncated:
                            log.warning("TRUNCATED response -- this call is NOT a measurement")
                            outcome = StudyOutcome(
                                outcome="unclassified", measured=False, unmeasured_reason="truncated"
                            )
                        else:
                            outcome = classify_outcome(decision, scenario)
                        if not outcome.measured:
                            unmeasured += 1

                        turn = StudyTurn(
                            turn_index=0, user_message=user, raw_response=result.raw_response,
                            parsed_ok=decision is not None, parse_error=parse_error,
                            parsed_response=decision, outcome=outcome,
                            latency_seconds=result.latency_seconds, usage=usage, cost_usd=cost,
                            finish_reason=meta.get("finish_reason") or meta.get("stop_reason"),
                            truncated=truncated,
                            errors=([] if result.ok else [result.error or "unknown_error"]),
                        )
                        record = StudyRecord(
                            run_id=config.run_id, timestamp=_utc_now(), provider=config.provider,
                            model=model, model_digest=result.model_digest,
                            model_resolved=meta.get("model") or meta.get("resolved_model"),
                            scenario_id=scenario.id, scenario_version=scenario.version,
                            scenario_sha256=scenario.source_sha256,
                            family=st.family, family_role=st.family_role, domain=st.domain,
                            permissibility=st.permissibility, factor=st.manipulation.factor,
                            human_evidence_class=st.manipulation.human_evidence_class,
                            level=variant.level or "", factors=dict(variant.factors),
                            is_control=(variant.id == st.control_variant_id),
                            variant_id=variant.id, pressure_type=variant.pressure_type,
                            role=config.role or scenario.role,
                            floor=config.floor, intervention=arm,
                            intervention_factors=arm_factors(arm, config.floor),
                            interventions_version=INTERVENTIONS_VERSION,
                            system_prompt_style=config.system_prompt_style,
                            system_prompt_chars=len(system),
                            temperature=gen.temperature, top_p=gen.top_p, seed=call_seed,
                            max_tokens=gen.max_tokens, think=gen.think, format=gen.format,
                            run_index=run_index,
                            study_template_version=STUDY_TEMPLATE_VERSION,
                            prompt_hash=p_hash, system_hash=s_hash,
                            option_order=order, option_order_seed=order_seed,
                            turns=[turn], outcome=outcome, parsed_ok=decision is not None,
                            n_turns=1, cost_usd=cost,
                        )
                        _append_jsonl(records_path, record.model_dump(mode="json"))
                        _append_jsonl(prompts_path, {
                            "model": model, "floor": config.floor, "intervention": arm,
                            "scenario_id": scenario.id, "variant_id": variant.id,
                            "run_index": run_index, "prompt_hash": p_hash,
                            "option_order": order, "prompt": full,
                        })
                        total += 1
                    if aborted:
                        break
                if aborted:
                    break
            if aborted:
                break
        if aborted:
            break

    log.info("budget: %s", budget.summary())
    (out_dir / "spend.txt").write_text(
        budget.summary() + ("\nABORTED: " + aborted if aborted else "") + "\n",
        encoding="utf-8",
    )
    if aborted:
        raise BudgetExceeded(aborted)
    log.info(
        "study run done: %d new calls, %d unmeasured (parse/unknown option/truncated), output in %s",
        total, unmeasured, out_dir,
    )
    return out_dir
