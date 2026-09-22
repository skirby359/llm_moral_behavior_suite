"""Run loop: models × scenarios × variants × runs → JSONL outputs.

Writes incrementally and resumes safely: on restart, any (model, scenario,
variant, run_index) already present in ``scores.jsonl`` is skipped. The output
directory follows the contract in brief §12.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import ValidationError

from . import PROMPT_TEMPLATE_VERSION
from .config import RunConfig
from .prompt_builder import (
    MAIN_TEMPLATE,
    SYSTEM_PROMPTS,
    build_full_prompt,
    prompt_hash,
    split_system_user,
)
from .providers import get_provider
from .providers.base import GenerationOptions
from .scenario_loader import select_scenarios
from .schemas import (
    ErosionToolCall,
    FactualPosition,
    ModelDecision,
    ResultRecord,
    SandboxToolCall,
    Scenario,
    StudyDecision,
)
from .scorers.rule_based import compute_scores
from .utils.hardware import collect_hardware_report
from .utils.json_extract import extract_json
from .utils.logging import get_logger

log = get_logger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


#: Output schemas that `generation.format: "schema"` can resolve to, keyed by the
#: measurement family. `decision` is every phase up to 8; `factual` is the
#: separate A5 contract (PHASE-20 keeps `ModelDecision` untouched).
FORMAT_SCHEMAS = {
    "decision": ModelDecision,
    "factual": FactualPosition,
    # Study 1 / Study 2 option-menu contract (study_runner.py).
    "study": StudyDecision,
    # Wave 2 erosion tool call (erosion_runner.py); `tool` enum patched per scenario.
    "erosion": ErosionToolCall,
    # Wave 3 sandbox tool call under the json_schema transport (sandbox_runner.py).
    "sandbox": SandboxToolCall,
}


def _resolve_format(fmt: str | dict | None, schema: str = "decision") -> str | dict | None:
    """Map a config `generation.format` value to what the provider sends.

    "schema" -> the full JSON schema for the named output model (Ollama
    structured outputs / frontier json_schema mode, forcing enum and type
    compliance); "json" -> free JSON mode; else passthrough.

    ``schema`` selects which output contract to enforce. It defaults to
    ``"decision"`` so every existing caller behaves exactly as before.
    """
    if fmt == "schema":
        try:
            return FORMAT_SCHEMAS[schema].model_json_schema()
        except KeyError:
            raise KeyError(
                f"unknown output schema {schema!r}; choose from {sorted(FORMAT_SCHEMAS)}"
            ) from None
    return fmt


def _append_jsonl(path: Path, obj: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _completed_keys(scores_path: Path) -> set[tuple]:
    """Read existing scores.jsonl to find already-finished calls (resume)."""
    done: set[tuple] = set()
    if not scores_path.exists():
        return done
    for line in scores_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            done.add((r["model"], r["scenario_id"], r["variant_id"], r["run_index"]))
        except (json.JSONDecodeError, KeyError):
            continue
    return done


def _write_run_manifest(
    out_dir: Path, config: RunConfig, scenarios: list[Scenario]
) -> None:
    (out_dir / "config.yaml").write_text(
        yaml.safe_dump(config.model_dump(), sort_keys=False), encoding="utf-8"
    )
    (out_dir / "models.txt").write_text("\n".join(config.models) + "\n", encoding="utf-8")
    (out_dir / "prompt_template.md").write_text(
        f"# Prompt template v{PROMPT_TEMPLATE_VERSION}\n\n"
        f"## System prompt style: {config.system_prompt_style}\n\n"
        f"```\n{SYSTEM_PROMPTS[config.system_prompt_style]}\n```\n\n"
        f"## Main template\n\n```\n{MAIN_TEMPLATE}\n```\n",
        encoding="utf-8",
    )
    manifest = {
        "run_id": config.run_id,
        "scenarios": [
            {
                "id": s.id,
                "version": s.version,
                "role": s.role,
                "variants": [v.id for v in s.variants],
            }
            for s in scenarios
        ],
    }
    (out_dir / "scenario_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    try:
        (out_dir / "hardware.txt").write_text(collect_hardware_report(), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - metadata must never fail the run
        (out_dir / "hardware.txt").write_text(f"<hardware capture failed: {exc}>", "utf-8")


def _parse_decision(raw: str) -> tuple[ModelDecision | None, str | None]:
    obj, reason = extract_json(raw)
    if obj is None:
        return None, reason
    try:
        return ModelDecision.model_validate(obj), None
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", []))
        return None, f"schema_invalid: {loc}: {first.get('msg', exc)}"


def run(config: RunConfig, output_dir: str | Path | None = None) -> Path:
    out_dir = Path(output_dir) if output_dir else Path("outputs") / config.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    scenarios = select_scenarios(
        scenario_dir=config.scenario_dir, scenario_ids=config.scenario_ids
    )
    _write_run_manifest(out_dir, config, scenarios)

    provider = get_provider(config.provider)
    gen = config.generation
    options = GenerationOptions(
        temperature=gen.temperature,
        top_p=gen.top_p,
        max_tokens=gen.max_tokens,
        seed=gen.seed,
        timeout_seconds=config.execution.timeout_seconds,
        think=gen.think,
        format=_resolve_format(gen.format),
    )

    prompts_path = out_dir / "prompts.jsonl"
    raw_path = out_dir / "raw_responses.jsonl"
    parsed_path = out_dir / "parsed_responses.jsonl"
    scores_path = out_dir / "scores.jsonl"

    done = _completed_keys(scores_path)
    if done:
        log.info("resuming: %d calls already complete, will be skipped", len(done))

    total = 0
    parse_failures = 0
    for model in config.models:
        for scenario in scenarios:
            variants = (
                [scenario.variant(v) for v in config.variants]
                if config.variants
                else scenario.variants
            )
            for variant in variants:
                for run_index in range(1, config.execution.runs_per_variant + 1):
                    key = (model, scenario.id, variant.id, run_index)
                    if key in done:
                        continue

                    full_prompt = build_full_prompt(
                        scenario,
                        variant,
                        system_prompt_style=config.system_prompt_style,
                        role=config.role,
                    )
                    p_hash = prompt_hash(full_prompt)
                    system, user = split_system_user(full_prompt)

                    log.info(
                        "%s | %s/%s run %d", model, scenario.id, variant.id, run_index
                    )
                    result = provider.generate(
                        system=system, prompt=user, model=model, options=options
                    )

                    decision, parse_error = (None, None)
                    if result.ok:
                        decision, parse_error = _parse_decision(result.raw_response)
                    else:
                        parse_error = result.error

                    parsed_ok = decision is not None
                    if not parsed_ok:
                        parse_failures += 1

                    scores = compute_scores(decision, scenario) if decision else None

                    record = ResultRecord(
                        run_id=config.run_id,
                        timestamp=_utc_now(),
                        provider=config.provider,
                        model=model,
                        model_digest=result.model_digest,
                        scenario_id=scenario.id,
                        scenario_version=scenario.version,
                        variant_id=variant.id,
                        pressure_type=variant.pressure_type,
                        role=config.role or scenario.role,
                        temperature=gen.temperature,
                        top_p=gen.top_p,
                        seed=gen.seed,
                        run_index=run_index,
                        prompt_template_version=PROMPT_TEMPLATE_VERSION,
                        prompt_hash=p_hash,
                        raw_response=result.raw_response,
                        parsed_ok=parsed_ok,
                        parse_error=parse_error,
                        parsed_response=decision,
                        latency_seconds=result.latency_seconds,
                        scores=scores,
                        errors=([] if result.ok else [result.error or "unknown_error"]),
                    )

                    _append_jsonl(prompts_path, {**key_meta(record), "prompt": full_prompt})
                    _append_jsonl(
                        raw_path, {**key_meta(record), "raw_response": result.raw_response}
                    )
                    _append_jsonl(parsed_path, record.model_dump(mode="json"))
                    _append_jsonl(scores_path, record.model_dump(mode="json"))
                    total += 1

    log.info(
        "done: %d new calls, %d parse failures, output in %s",
        total, parse_failures, out_dir,
    )
    return out_dir


def key_meta(record: ResultRecord) -> dict:
    return {
        "run_id": record.run_id,
        "model": record.model,
        "scenario_id": record.scenario_id,
        "variant_id": record.variant_id,
        "run_index": record.run_index,
        "prompt_hash": record.prompt_hash,
    }
