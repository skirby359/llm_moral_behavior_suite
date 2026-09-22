"""Recompute the W2 result table from the raw records.

WHY THIS EXISTS. The W2 numbers had been transcribed by hand into three
documents, and one of the transcriptions went stale in a way that mattered:
`notes/OVERNIGHT-2026-08-04.md` said "W2 is n=1 per cell" and asked whether repeats
were worth buying, while `outputs/` already held eleven runs per local cell.
A hand-maintained table cannot be trusted to track the artifacts. This reads the
artifacts.

It also enforces the repo's own rule about error bars: a +/- is meaningless
unless you say how it was obtained, so every cell is labelled with its variance
provenance --

    seed-varied      : Ollama, >1 distinct seed. A real robustness statement.
    PINNED SEED      : Ollama, one seed. Repeats are replays of one
                       deterministic path; sd 0.00 here means nothing. This bit
                       once already (qwen2.5:3b false_history read 2.00 +/- 0.00
                       pinned, 0.40 +/- 0.55 seed-varied -- the pinned run
                       understated the effect).
    no seed param    : Anthropic/OpenAI. Neither API exposes a seed, so repeats
                       are independently sampled and sd 0.00 IS a robustness
                       claim. Identical notation, opposite epistemic content.

Usage:
    python scenarios_w2/summarize_w2.py
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"

LEVERS = ("authority", "false_history")


def facts_and_lever(scenario_id: str) -> tuple[str, str]:
    """`w2_layoff_false_history` -> ("layoff", "false_history")."""
    body = scenario_id.removeprefix("w2_")
    for lever in LEVERS:
        if body.endswith(lever):
            return body[: -len(lever)].rstrip("_"), lever
    return body, "other"


def run_dirs() -> list[Path]:
    return sorted(d for d in OUTPUTS.glob("w2_*") if (d / "multi_turn.jsonl").exists())


def load_run(d: Path) -> tuple[dict, list[dict]]:
    cfg = {}
    cfg_path = d / "config.yaml"
    if cfg_path.exists():
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    records = [
        json.loads(line)
        for line in (d / "multi_turn.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return cfg, records


def variance_provenance(provider: str, seeds: set) -> str:
    if provider in {"anthropic", "openai"}:
        return "no seed param"
    if len({s for s in seeds if s is not None}) > 1:
        return "seed-varied"
    return "PINNED SEED"


def fmt_cell(depths: list[int]) -> str:
    if not depths:
        return "--"
    sd = statistics.stdev(depths) if len(depths) > 1 else 0.0
    return f"{statistics.mean(depths):.2f} +/- {sd:.2f} (n={len(depths)})"


def main() -> None:
    # (model, output_constraint) -> (facts, lever) -> depths
    cells: dict[tuple[str, str], dict[tuple[str, str], list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    seeds: dict[tuple[str, str], set] = defaultdict(set)
    providers: dict[tuple[str, str], str] = {}
    runs_seen: dict[tuple[str, str], set[str]] = defaultdict(set)

    # Format / truncation / cost bookkeeping, kept strictly separate from the
    # behavioral numbers -- a format failure is not a boundary failure.
    per_run: list[dict] = []

    for d in run_dirs():
        cfg, records = load_run(d)
        constraint = (cfg.get("generation") or {}).get("format") or "unconstrained"
        turns = parsed = truncated = 0
        cost = 0.0
        costed = False
        for r in records:
            model, provider = r["model"], r["provider"]
            key = (model, constraint)
            providers[key] = provider
            seeds[key].add(r.get("seed"))
            runs_seen[key].add(d.name)
            facts, lever = facts_and_lever(r["scenario_id"])
            cells[key][(facts, lever)].append(r["boundary_survival_depth"])
            for t in r["turns"]:
                turns += 1
                parsed += bool(t["parsed_ok"])
                truncated += bool(t.get("truncated"))
            if r.get("cost_usd") is not None:
                cost += r["cost_usd"]
                costed = True
        per_run.append(
            {
                "run": d.name,
                "model": records[0]["model"] if records else "?",
                "provider": records[0]["provider"] if records else "?",
                "constraint": constraint,
                "turns": turns,
                "parse_rate": parsed / turns if turns else 0.0,
                "truncated": truncated,
                "cost": cost if costed else None,
            }
        )

    print("=" * 96)
    print("W2 -- boundary_survival_depth out of 5, recomputed from outputs/w2_*/multi_turn.jsonl")
    print("=" * 96)

    all_facts = sorted({f for c in cells.values() for f, _ in c})
    for key in sorted(cells, key=lambda k: (k[0], k[1])):
        model, constraint = key
        prov = variance_provenance(providers[key], seeds[key])
        n_runs = len(runs_seen[key])
        print(f"\n{model}   [output: {constraint}]   provider={providers[key]}   "
              f"{n_runs} run(s)   variance: {prov}")
        seed_list = sorted(s for s in seeds[key] if s is not None)
        if providers[key] == "ollama":
            print(f"  seeds: {seed_list}")
        print(f"  {'facts':<14} {'authority':>22} {'false_history':>22} {'delta':>10}")
        for facts in all_facts:
            a = cells[key].get((facts, "authority"), [])
            f = cells[key].get((facts, "false_history"), [])
            if not a and not f:
                continue
            delta = (
                f"{statistics.mean(f) - statistics.mean(a):+.2f}" if a and f else "--"
            )
            print(f"  {facts:<14} {fmt_cell(a):>22} {fmt_cell(f):>22} {delta:>10}")

    print("\n" + "=" * 96)
    print("OUTPUT-FORMAT COMPLIANCE (reported separately from behavior, per README)")
    print("=" * 96)
    print(f"  {'run':<24} {'model':<15} {'constraint':<12} {'turns':>6} {'parse_ok':>9} "
          f"{'trunc':>6} {'cost $':>9}")
    for r in sorted(per_run, key=lambda x: (x["model"], x["constraint"], x["run"])):
        cost = "--" if r["cost"] is None else f"{r['cost']:.4f}"
        print(f"  {r['run']:<24} {r['model']:<15} {r['constraint']:<12} {r['turns']:>6} "
              f"{r['parse_rate']:>8.0%} {r['truncated']:>6} {cost:>9}")

    total = sum(r["cost"] for r in per_run if r["cost"] is not None)
    uncosted = [r["run"] for r in per_run if r["cost"] is None and r["provider"] != "ollama"]
    print(f"\n  recorded frontier spend across W2 runs: ${total:.4f}")
    if uncosted:
        print("  NOT costed (predate per-call usage recording, added 2026-08-04): "
              + ", ".join(sorted(uncosted)))


if __name__ == "__main__":
    main()
