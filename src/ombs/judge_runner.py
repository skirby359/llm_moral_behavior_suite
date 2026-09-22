"""Run the LLM-as-judge over a scores.jsonl and write judge.jsonl (brief §19).

Reads parsed model decisions, asks a judge model to evaluate each, and records
the verdict alongside the deterministic boundary score (for comparison only — the
two are never merged). Judge runs are append-only and resumable.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .providers import get_provider
from .providers.base import GenerationOptions
from .scenario_loader import select_scenarios
from .schemas import ModelDecision
from .scorers.llm_judge import judge_one
from .utils.logging import get_logger

log = get_logger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def run_judge(
    scores_path: str | Path,
    *,
    judge_provider: str = "anthropic",
    judge_model: str = "claude-opus-4-8",
    scenario_dir: str | None = None,
    limit: int | None = None,
    out_path: str | Path | None = None,
) -> Path:
    scores_path = Path(scores_path)
    out_path = Path(out_path) if out_path else scores_path.with_name("judge.jsonl")

    records = [r for r in _load_jsonl(scores_path) if r.get("parsed_ok")]
    if limit:
        records = records[:limit]

    scenario_ids = sorted({r["scenario_id"] for r in records})
    scenarios = {
        s.id: s
        for s in select_scenarios(scenario_dir=scenario_dir, scenario_ids=scenario_ids)
    }

    provider = get_provider(judge_provider)
    options = GenerationOptions(max_tokens=600, timeout_seconds=120)

    # Resume: skip (model, scenario, variant, run_index) already judged.
    done = set()
    if out_path.exists():
        for r in _load_jsonl(out_path):
            done.add((r["model"], r["scenario_id"], r["variant_id"], r["run_index"]))

    n = 0
    for r in records:
        key = (r["model"], r["scenario_id"], r["variant_id"], r["run_index"])
        if key in done:
            continue
        scenario = scenarios.get(r["scenario_id"])
        if scenario is None:
            continue
        decision = ModelDecision.model_validate(r["parsed_response"])
        verdict, parse_error, raw = judge_one(
            provider, judge_model=judge_model, scenario=scenario,
            decision=decision, options=options,
        )
        det_boundary = r["scores"]["boundary_preserved"] if r.get("scores") else None
        row = {
            "judged_at": _utc_now(),
            "judge_provider": judge_provider,
            "judge_model": judge_model,
            "self_judge": judge_model == r["model"],
            "model": r["model"],
            "scenario_id": r["scenario_id"],
            "variant_id": r["variant_id"],
            "pressure_type": r.get("pressure_type"),
            "run_index": r["run_index"],
            "deterministic_boundary_preserved": det_boundary,
            "judge_ok": verdict is not None,
            "judge_parse_error": parse_error,
            "verdict": verdict.model_dump() if verdict else None,
            "judge_raw": None if verdict else (raw or "")[:600],
        }
        with out_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        n += 1
        log.info("judged %s | %s/%s (%d)", r["model"], r["scenario_id"], r["variant_id"], n)

    log.info("judge done: %d new verdicts -> %s", n, out_path)
    return out_path
