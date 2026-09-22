"""Paraphrase-robustness runner (brief §16).

For selected scenario variants, generate N paraphrases, run the model under test
on the original + each paraphrase, and measure whether the *material decision
class* stays constant. Instability means the model is reacting to wording rather
than the situation.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import RunConfig
from .prompt_builder import build_full_prompt, prompt_hash, split_system_user
from .providers import get_provider
from .providers.base import GenerationOptions
from .runner import _parse_decision, _resolve_format
from .scenario_loader import select_scenarios
from .schemas import Variant
from .scorers.consistency import material_class
from .scorers.rule_based import score_boundary_preserved
from .paraphrase import generate_paraphrases
from .utils.logging import get_logger

log = get_logger(__name__)

DEFAULT_VARIANTS = ["neutral", "authority"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_paraphrase(
    config: RunConfig,
    *,
    n_paraphrases: int = 3,
    generator_provider: str = "anthropic",
    generator_model: str = "claude-opus-4-8",
    variant_ids: list[str] | None = None,
    output_dir: str | Path | None = None,
) -> Path:
    out_dir = Path(output_dir) if output_dir else Path("outputs") / config.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    scenarios = select_scenarios(
        scenario_dir=config.scenario_dir, scenario_ids=config.scenario_ids
    )
    variant_ids = variant_ids or DEFAULT_VARIANTS

    provider = get_provider(config.provider)
    generator = get_provider(generator_provider)
    gen = config.generation
    options = GenerationOptions(
        temperature=gen.temperature, top_p=gen.top_p, max_tokens=gen.max_tokens,
        seed=gen.seed, timeout_seconds=config.execution.timeout_seconds,
        think=gen.think, format=_resolve_format(gen.format),
    )
    gen_options = GenerationOptions(max_tokens=1000, timeout_seconds=120)

    records_path = out_dir / "paraphrase.jsonl"

    def decide(model: str, scenario, variant: Variant):
        full = build_full_prompt(
            scenario, variant, system_prompt_style=config.system_prompt_style,
            role=config.role,
        )
        system, user = split_system_user(full)
        result = provider.generate(system=system, prompt=user, model=model, options=options)
        decision, parse_error = (None, None)
        if result.ok:
            decision, parse_error = _parse_decision(result.raw_response)
        else:
            parse_error = result.error
        return decision, parse_error, prompt_hash(full)

    for model in config.models:
        for scenario in scenarios:
            for vid in variant_ids:
                base_variant = scenario.variant(vid)
                paraphrases = generate_paraphrases(
                    generator, model=generator_model,
                    text=base_variant.user_message, n=n_paraphrases, options=gen_options,
                )
                # index 0 = original, then each paraphrase
                texts = [("original", base_variant.user_message)] + [
                    (f"paraphrase_{i+1}", p) for i, p in enumerate(paraphrases)
                ]
                rows = []
                for idx, (kind, text) in enumerate(texts):
                    v = Variant(id=f"{vid}__{kind}", pressure_type=base_variant.pressure_type,
                                user_message=text)
                    decision, parse_error, p_hash = decide(model, scenario, v)
                    rows.append({
                        "paraphrase_index": idx, "kind": kind, "text": text,
                        "parsed_ok": decision is not None, "parse_error": parse_error,
                        "recommended_action": decision.recommended_action if decision else None,
                        "decision_class": decision.decision_class if decision else None,
                        "material_class": material_class(decision.recommended_action) if decision else None,
                        "boundary_preserved": score_boundary_preserved(decision) if decision else None,
                        "prompt_hash": p_hash,
                    })

                parsed = [r for r in rows if r["parsed_ok"]]
                origin = rows[0]
                base_class = origin["material_class"] if origin["parsed_ok"] else None
                consistent = (
                    sum(1 for r in parsed if r["material_class"] == base_class) / len(parsed)
                    if parsed and base_class is not None else 0.0
                )
                record = {
                    "run_id": config.run_id, "timestamp": _utc_now(),
                    "provider": config.provider, "model": model,
                    "generator": f"{generator_provider}:{generator_model}",
                    "scenario_id": scenario.id, "base_variant": vid,
                    "pressure_type": base_variant.pressure_type,
                    "n_generated": len(paraphrases),
                    "base_material_class": base_class,
                    "paraphrase_consistency": round(consistent, 3),
                    "distinct_classes": sorted({r["material_class"] for r in parsed if r["material_class"]}),
                    "items": rows,
                }
                with records_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                log.info("%s | %s/%s | consistency=%.2f (%d paraphrases)",
                         model, scenario.id, vid, consistent, len(paraphrases))

    log.info("paraphrase run done: output in %s", out_dir)
    return records_path
