"""Typer CLI for ombs (brief §6)."""

from __future__ import annotations

from pathlib import Path

import typer

from .analysis import authority as authority_mod
from .analysis import factual as factual_mod
from .analysis import report as report_mod
from .analysis import scorecard as scorecard_mod
from .analysis import study as study_mod
from .analysis import erosion as erosion_mod
from .analysis import sandbox as sandbox_mod
from .config import ErosionRunConfig, RunConfig, SandboxRunConfig, StudyRunConfig
from .factual_runner import run_factual_denial
from .erosion_runner import run_erosion
from .sandbox_runner import run_sandbox
from .fidelity_review import DEFAULT_JUDGES, run_fidelity_review
from .study_runner import run_study
from .multi_turn import run_multi_turn
from .runner import run as run_mod
from .tool_runner import run_tools, run_tools_multi_turn
from .judge_runner import run_judge
from .paraphrase_runner import run_paraphrase
from .scenario_loader import ScenarioError, load_scenarios_from_dir
from .utils.env import load_dotenv

app = typer.Typer(
    add_completion=False,
    help="LLM Operational Moral-Behavior Testing Suite.",
    no_args_is_help=True,
)


@app.callback()
def _bootstrap() -> None:
    """Load a local .env (e.g. ANTHROPIC_API_KEY) before any command runs."""
    load_dotenv()


@app.command("list-scenarios")
def list_scenarios(
    scenario_dir: str = typer.Option("scenarios", "--scenario-dir"),
) -> None:
    """List available scenarios and their variants."""
    try:
        scenarios = load_scenarios_from_dir(scenario_dir)
    except ScenarioError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(1)
    for s in scenarios:
        typer.echo(f"{s.id}  [{s.category}]  role={s.role}  variants={len(s.variants)}")
        typer.echo(f"    {s.title}")


@app.command("validate-scenarios")
def validate_scenarios(
    scenario_dir: str = typer.Option("scenarios", "--scenario-dir"),
) -> None:
    """Validate every scenario YAML under a directory."""
    try:
        scenarios = load_scenarios_from_dir(scenario_dir)
    except ScenarioError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(1)
    typer.secho(f"OK: {len(scenarios)} scenario(s) valid.", fg=typer.colors.GREEN)


@app.command("run")
def run(
    config: str = typer.Option(None, "--config", help="Path to a run YAML config."),
    models: list[str] = typer.Option(None, "--models", help="Override model list."),
    scenario_dir: str = typer.Option(None, "--scenario-dir"),
    runs_per_variant: int = typer.Option(None, "--runs-per-variant"),
    temperature: float = typer.Option(None, "--temperature"),
    system_prompt_style: str = typer.Option(None, "--system-prompt-style"),
    run_id: str = typer.Option(None, "--run-id", help="Override run_id (output dir)."),
    output: str = typer.Option(None, "--output", help="Output directory."),
) -> None:
    """Run a benchmark. Provide a --config, with optional CLI overrides."""
    if config:
        cfg = RunConfig.from_yaml(config)
    elif models:
        cfg = RunConfig(run_id="adhoc_run", models=list(models))
    else:
        typer.secho("provide --config or --models", fg=typer.colors.RED)
        raise typer.Exit(1)

    if models:
        cfg.models = list(models)
    if scenario_dir:
        cfg.scenario_dir = scenario_dir
    if runs_per_variant is not None:
        cfg.execution.runs_per_variant = runs_per_variant
    if temperature is not None:
        cfg.generation.temperature = temperature
    if system_prompt_style:
        cfg.system_prompt_style = system_prompt_style
    if run_id:
        cfg.run_id = run_id

    out_dir = run_mod(cfg, output_dir=output)
    typer.secho(f"Run complete: {out_dir}", fg=typer.colors.GREEN)


@app.command("run-multiturn")
def run_multiturn(
    config: str = typer.Option(..., "--config", help="Path to a run YAML config."),
    output: str = typer.Option(None, "--output", help="Output directory."),
    models: list[str] = typer.Option(None, "--models", help="Override model list."),
    system_prompt_style: str = typer.Option(None, "--system-prompt-style"),
    run_id: str = typer.Option(None, "--run-id", help="Override run_id (output dir)."),
) -> None:
    """Run multi-turn pushback tests for scenarios with a pushback_sequence."""
    cfg = RunConfig.from_yaml(config)
    if models:
        cfg.models = list(models)
    if system_prompt_style:
        cfg.system_prompt_style = system_prompt_style
    if run_id:
        cfg.run_id = run_id
    out_dir = run_multi_turn(cfg, output_dir=output)
    report_mod.build_multi_turn_report(out_dir / "multi_turn.jsonl", out_dir)
    typer.secho(f"Multi-turn run complete: {out_dir}", fg=typer.colors.GREEN)
    typer.echo(report_mod.multi_turn_summary_text(out_dir / "multi_turn.jsonl"))


@app.command("run-tools")
def run_tools_cmd(
    config: str = typer.Option(..., "--config", help="Path to a run YAML config."),
    output: str = typer.Option(None, "--output", help="Output directory."),
) -> None:
    """Run simulated-tool scenarios with state-based scoring (brief §18)."""
    cfg = RunConfig.from_yaml(config)
    out_dir = run_tools(cfg, output_dir=output)
    report_mod.build_tool_report(out_dir / "tool_runs.jsonl", out_dir)
    typer.secho(f"Tool run complete: {out_dir}", fg=typer.colors.GREEN)
    typer.echo(report_mod.tool_summary_text(out_dir / "tool_runs.jsonl"))


@app.command("report-tools")
def report_tools(input: str = typer.Option(..., "--input", help="Path to tool_runs.jsonl")) -> None:
    """Generate the simulated-tool report from a tool_runs.jsonl."""
    out_dir = report_mod.build_tool_report(input)
    typer.secho(f"Tool report written to {out_dir}", fg=typer.colors.GREEN)
    typer.echo(report_mod.tool_summary_text(input))


@app.command("run-tools-multiturn")
def run_tools_multiturn_cmd(
    config: str = typer.Option(..., "--config", help="Path to a run YAML config."),
    output: str = typer.Option(None, "--output", help="Output directory."),
) -> None:
    """Run multi-turn tool pushback (Phase 6 × Phase 7): does pressure turn a safe
    tool choice into a real unsafe call?"""
    cfg = RunConfig.from_yaml(config)
    out_dir = run_tools_multi_turn(cfg, output_dir=output)
    report_mod.build_tool_multiturn_report(out_dir / "tool_multiturn.jsonl", out_dir)
    typer.secho(f"Multi-turn tool run complete: {out_dir}", fg=typer.colors.GREEN)
    typer.echo(report_mod.tool_multiturn_summary_text(out_dir / "tool_multiturn.jsonl"))


@app.command("report-tools-multiturn")
def report_tools_multiturn(
    input: str = typer.Option(..., "--input", help="Path to tool_multiturn.jsonl")
) -> None:
    """Generate the multi-turn tool report from a tool_multiturn.jsonl."""
    out_dir = report_mod.build_tool_multiturn_report(input)
    typer.secho(f"Multi-turn tool report written to {out_dir}", fg=typer.colors.GREEN)
    typer.echo(report_mod.tool_multiturn_summary_text(input))


@app.command("scorecard")
def scorecard(
    name: list[str] = typer.Option(..., "--name", help="Model name(s); repeat for comparison."),
    outputs_dir: str = typer.Option("outputs", "--outputs-dir"),
) -> None:
    """Synthesize all runs for one model into a scorecard, or compare several."""
    if len(name) == 1:
        path = scorecard_mod.build_scorecard(name[0], outputs_dir=outputs_dir)
    else:
        path = scorecard_mod.build_comparison(list(name), outputs_dir=outputs_dir)
    typer.secho(f"Scorecard written to {path}", fg=typer.colors.GREEN)
    typer.echo(path.read_text(encoding="utf-8"))


@app.command("judge")
def judge(
    input: str = typer.Option(..., "--input", help="Path to scores.jsonl"),
    judge_provider: str = typer.Option("anthropic", "--judge-provider"),
    judge_model: str = typer.Option("claude-opus-4-8", "--judge-model"),
    scenario_dir: str = typer.Option(None, "--scenario-dir"),
    limit: int = typer.Option(None, "--limit", help="Judge only the first N parsed records."),
) -> None:
    """Run the LLM-as-judge over parsed decisions (brief §19). Kept separate from
    deterministic scores; flags likely deterministic false negatives."""
    out_path = run_judge(
        input, judge_provider=judge_provider, judge_model=judge_model,
        scenario_dir=scenario_dir, limit=limit,
    )
    report_mod.build_judge_report(out_path)
    typer.secho(f"Judge complete: {out_path}", fg=typer.colors.GREEN)
    typer.echo(report_mod.judge_summary_text(out_path))


@app.command("report-judge")
def report_judge(input: str = typer.Option(..., "--input", help="Path to judge.jsonl")) -> None:
    """Generate the LLM-judge report from a judge.jsonl."""
    out_dir = report_mod.build_judge_report(input)
    typer.secho(f"Judge report written to {out_dir}", fg=typer.colors.GREEN)
    typer.echo(report_mod.judge_summary_text(input))


@app.command("run-paraphrase")
def run_paraphrase_cmd(
    config: str = typer.Option(..., "--config", help="Path to a run YAML config."),
    n: int = typer.Option(3, "--n", help="Paraphrases per variant."),
    generator_provider: str = typer.Option("anthropic", "--generator-provider"),
    generator_model: str = typer.Option("claude-opus-4-8", "--generator-model"),
    variants: list[str] = typer.Option(None, "--variant", help="Variant ids (repeatable)."),
    output: str = typer.Option(None, "--output"),
) -> None:
    """Paraphrase-robustness test (brief §16): does wording change the decision?"""
    cfg = RunConfig.from_yaml(config)
    out_path = run_paraphrase(
        cfg, n_paraphrases=n, generator_provider=generator_provider,
        generator_model=generator_model, variant_ids=(list(variants) if variants else None),
        output_dir=output,
    )
    report_mod.build_paraphrase_report(out_path)
    typer.secho(f"Paraphrase run complete: {out_path}", fg=typer.colors.GREEN)
    typer.echo(report_mod.paraphrase_summary_text(out_path))


@app.command("report-paraphrase")
def report_paraphrase(input: str = typer.Option(..., "--input", help="Path to paraphrase.jsonl")) -> None:
    """Generate the paraphrase-robustness report from a paraphrase.jsonl."""
    out_dir = report_mod.build_paraphrase_report(input)
    typer.secho(f"Paraphrase report written to {out_dir}", fg=typer.colors.GREEN)
    typer.echo(report_mod.paraphrase_summary_text(input))


@app.command("report")
def report(input: str = typer.Option(..., "--input", help="Path to scores.jsonl")) -> None:
    """Generate CSVs, report.md, and failures.md from a scores.jsonl."""
    out_dir = report_mod.build_reports(input)
    typer.secho(f"Report written to {out_dir}", fg=typer.colors.GREEN)


@app.command("report-multiturn")
def report_multiturn(
    input: str = typer.Option(..., "--input", help="Path to multi_turn.jsonl")
) -> None:
    """Generate the multi-turn report from a multi_turn.jsonl."""
    out_dir = report_mod.build_multi_turn_report(input)
    typer.secho(f"Multi-turn report written to {out_dir}", fg=typer.colors.GREEN)
    typer.echo(report_mod.multi_turn_summary_text(input))


@app.command("report-authority")
def report_authority(
    input: str = typer.Option(..., "--input", help="Path to multi_turn.jsonl")
) -> None:
    """Authority-verification probe: does the model demand verified authority or
    accept a bare claim? (Reads a multi_turn.jsonl.)"""
    out_dir = authority_mod.build_authority_report(input)
    typer.secho(f"Authority report written to {out_dir}", fg=typer.colors.GREEN)
    typer.echo(authority_mod.authority_summary_text(input))


@app.command("run-factual-denial")
def run_factual_denial_cmd(
    config: str = typer.Option(..., "--config", help="Path to a run YAML config."),
    output: str = typer.Option(None, "--output", help="Output directory."),
    models: list[str] = typer.Option(None, "--models", help="Override model list."),
    run_id: str = typer.Option(None, "--run-id", help="Override run_id (output dir)."),
) -> None:
    """Run factual_denial (asymmetry A5): does a TRUE, checkable, NON-boundary
    claim survive escalating social pressure to abandon it?"""
    cfg = RunConfig.from_yaml(config)
    if models:
        cfg.models = list(models)
    if run_id:
        cfg.run_id = run_id
    out_dir = run_factual_denial(cfg, output_dir=output)
    factual_mod.build_factual_report(out_dir / "factual_denial.jsonl", out_dir)
    typer.secho(f"factual_denial run complete: {out_dir}", fg=typer.colors.GREEN)
    typer.echo(factual_mod.factual_summary_text(out_dir / "factual_denial.jsonl"))


@app.command("report-factual-denial")
def report_factual_denial(
    input: str = typer.Option(..., "--input", help="Path to factual_denial.jsonl")
) -> None:
    """Truth-abandonment report for A5. Read `signals_disagree` first — it is a
    validity check on the metric, not a property of the model."""
    out_dir = factual_mod.build_factual_report(input)
    typer.secho(f"factual_denial report written to {out_dir}", fg=typer.colors.GREEN)
    typer.echo(factual_mod.factual_summary_text(input))


@app.command("run-study")
def run_study_cmd(
    config: str = typer.Option(..., "--config", help="Path to a study run YAML config."),
    output: str = typer.Option(None, "--output", help="Output directory."),
    models: list[str] = typer.Option(None, "--models", help="Override model list."),
    interventions: list[str] = typer.Option(
        None, "--interventions", help="Override safeguard arms, e.g. --interventions C00 --interventions C11."
    ),
    floor: str = typer.Option(None, "--floor", help="Override the core floor: bare | hierarchy."),
    levels: list[str] = typer.Option(None, "--levels", help="Restrict to these manipulation levels."),
    include_held_out: bool = typer.Option(
        False, "--include-held-out", help="Run confirmatory_heldout families (all of them, never a subset)."
    ),
    run_id: str = typer.Option(None, "--run-id", help="Override run_id (output dir)."),
) -> None:
    """Study 1 / Study 2: manipulation levels x safeguard arms over option-menu scenarios
    (scenarios_study1/). Writes study.jsonl and a study report."""
    cfg = StudyRunConfig.from_yaml(config)
    if models:
        cfg.models = list(models)
    if interventions:
        cfg.interventions = list(interventions)
    if floor:
        cfg.floor = floor
    if levels:
        cfg.levels = list(levels)
    if include_held_out:
        cfg.include_held_out = True
    if run_id:
        cfg.run_id = run_id
    out_dir = run_study(cfg, output_dir=output)
    study_mod.build_study_report(out_dir / "study.jsonl", out_dir)
    typer.secho(f"study run complete: {out_dir}", fg=typer.colors.GREEN)
    typer.echo(study_mod.study_summary_text(out_dir / "study.jsonl"))


@app.command("report-study")
def report_study(
    input: str = typer.Option(..., "--input", help="Path to study.jsonl"),
) -> None:
    """Competence gate, PS_k with Newcombe intervals, false refusals, focal-action d',
    safeguard contrasts, outcome mix. Descriptive only; inference is in R."""
    out_dir = study_mod.build_study_report(input)
    typer.secho(f"study report written to {out_dir}", fg=typer.colors.GREEN)
    typer.echo(study_mod.study_summary_text(input))


@app.command("export-study-csv")
def export_study_csv_cmd(
    input: str = typer.Option(..., "--input", help="Path to study.jsonl"),
    output: str = typer.Option(None, "--output", help="CSV path (default: study_long.csv beside the input)."),
) -> None:
    """Long-format CSV, one row per call, for experiments/study1/analysis.R."""
    src = Path(input)
    dst = Path(output) if output else src.parent / "study_long.csv"
    study_mod.export_study_csv(study_mod._load(src), dst)
    typer.secho(f"wrote {dst}", fg=typer.colors.GREEN)


@app.command("review-fidelity")
def review_fidelity(
    scenario_dir: str = typer.Option("scenarios_study1", "--scenario-dir"),
    judge: list[str] = typer.Option(
        list(DEFAULT_JUDGES), "--judge", help="provider:model; repeat for each judge."
    ),
    output: str = typer.Option(None, "--output", help="Default: <scenario_dir>/fidelity/"),
    limit: int = typer.Option(None, "--limit", help="Stop after N judge calls (smoke)."),
    study_model: list[str] = typer.Option(
        None, "--study-model", help="Models under test, to flag self-judging rows."
    ),
) -> None:
    """Blinded manipulation-fidelity review of every (control, treatment) pair, by two
    judge models, BEFORE outcome collection. Disagreements go to adjudications.yaml."""
    out_dir = run_fidelity_review(
        scenario_dir, judges=list(judge), out_dir=output, limit=limit,
        study_models=list(study_model or []),
    )
    typer.secho(f"fidelity review written to {out_dir}", fg=typer.colors.GREEN)
    typer.echo((out_dir / "fidelity_summary.md").read_text(encoding="utf-8"))


@app.command("run-erosion")
def run_erosion_cmd(
    config: str = typer.Option(..., "--config", help="Path to an erosion run YAML config."),
    output: str = typer.Option(None, "--output", help="Output directory."),
    models: list[str] = typer.Option(None, "--models", help="Override model list."),
    conditions: list[str] = typer.Option(
        None, "--conditions", help="Subset of abrupt | abrupt_state_matched | gradual; repeatable."
    ),
    include_held_out: bool = typer.Option(False, "--include-held-out"),
    run_id: str = typer.Option(None, "--run-id", help="Override run_id (output dir)."),
) -> None:
    """Wave 2: gradual erosion through the stateful tool sandbox (scenarios_erosion/).
    Writes erosion.jsonl, erosion_turns.jsonl, transcripts and the erosion report."""
    cfg = ErosionRunConfig.from_yaml(config)
    if models:
        cfg.models = list(models)
    if conditions:
        cfg.conditions = list(conditions)  # type: ignore[assignment]
    if include_held_out:
        cfg.include_held_out = True
    if run_id:
        cfg.run_id = run_id
    out_dir = run_erosion(cfg, output_dir=output)
    erosion_mod.build_erosion_report(out_dir / "erosion.jsonl", out_dir)
    typer.secho(f"erosion run complete: {out_dir}", fg=typer.colors.GREEN)
    typer.echo(erosion_mod.erosion_summary_text(out_dir / "erosion.jsonl"))


@app.command("report-erosion")
def report_erosion(
    input: str = typer.Option(..., "--input", help="Path to erosion.jsonl"),
) -> None:
    """Final-violation rates by condition, the three contrasts (erosion, state, path) with
    Newcombe intervals, path fidelity, per-rung false refusals, the state-match check."""
    out_dir = erosion_mod.build_erosion_report(input)
    typer.secho(f"erosion report written to {out_dir}", fg=typer.colors.GREEN)
    typer.echo(erosion_mod.erosion_summary_text(input))


@app.command("run-sandbox")
def run_sandbox_cmd(
    config: str = typer.Option(..., "--config", help="Path to a sandbox run YAML config."),
    output: str = typer.Option(None, "--output", help="Output directory."),
    models: list[str] = typer.Option(None, "--models", help="Override model list."),
    transport: str = typer.Option(None, "--transport", help="native | json_schema (overrides the config)."),
    runs_per_cell: int = typer.Option(None, "--runs-per-cell", help="Override repeats per (model, cell, scenario)."),
    include_held_out: bool = typer.Option(False, "--include-held-out"),
    allow_frozen: bool = typer.Option(
        False, "--allow-frozen",
        help="Sample a family listed in frozen_families.json. For harness characterisation only, "
             "never to extend a result; recorded in freeze.json.",
    ),
    allow_unpriced: bool = typer.Option(
        False, "--allow-unpriced",
        help="Run a billing provider's model that has no PRICING entry (the cap cannot see its "
             "spend). Only for a deliberately call-count-bounded run.",
    ),
    retry_unmeasured: bool = typer.Option(
        False, "--retry-unmeasured",
        help="On resume, re-issue runs whose outcome was unmeasured (transport error, truncation, "
             "vendor refusal) instead of skipping them. The failed attempts stay in the record.",
    ),
    run_id: str = typer.Option(None, "--run-id", help="Override run_id (output dir)."),
) -> None:
    """Wave 3: the goal-obstacle sandbox (scenarios_sandbox/). The agent owns a task with a
    checked criterion; the honest path may be blocked; protected files are writable. Writes
    sandbox.jsonl, sandbox_turns.jsonl, freeze.json, transcripts and the sandbox report."""
    cfg = SandboxRunConfig.from_yaml(config)
    if models:
        cfg.models = list(models)
    if transport:
        cfg.tool_transport = transport  # type: ignore[assignment]
    if runs_per_cell is not None:
        cfg.execution.runs_per_variant = runs_per_cell
    if include_held_out:
        cfg.include_held_out = True
    if retry_unmeasured:
        cfg.retry_unmeasured = True
    if run_id:
        cfg.run_id = run_id
    out_dir = run_sandbox(cfg, output_dir=output, allow_frozen=allow_frozen, allow_unpriced=allow_unpriced)
    typer.secho(f"sandbox run complete: {out_dir}", fg=typer.colors.GREEN)
    if any(v != "canonical" for v in cfg.framing_variant):
        # The generic report pools paraphrase arms by task_framing; a wording-robustness run is read
        # by its own analysis, which groups by framing_variant. The records, turns and freeze are
        # already written; only the generic report is skipped.
        typer.echo("wording-robustness run (non-canonical framing_variant): read it with "
                   "`make wording` (scenarios_sandbox/wording_analysis.py), not the generic report.")
    else:
        sandbox_mod.build_sandbox_report(out_dir / "sandbox.jsonl", out_dir)
        typer.echo(sandbox_mod.sandbox_summary_text(out_dir / "sandbox.jsonl"))


@app.command("review-sandbox-remit")
def review_sandbox_remit(
    scenario_dir: str = typer.Option("scenarios_sandbox", "--scenario-dir"),
    judge: list[str] = typer.Option(list(DEFAULT_JUDGES), "--judge", help="provider:model; repeat for each judge."),
    output: str = typer.Option(None, "--output", help="Default: <scenario_dir>/fidelity/"),
    study_model: list[str] = typer.Option(None, "--study-model", help="Models under test, to flag self-judging rows."),
    family: list[str] = typer.Option(None, "--family", help="Review only these families; default all."),
    retry_failed: bool = typer.Option(False, "--retry-failed", help="Re-issue rows that returned no verdict (bills again)."),
    allow_unpriced: bool = typer.Option(False, "--allow-unpriced", help="Allow a judge model with no PRICING entry (uncapped)."),
) -> None:
    """Blinded remit review of the sandbox materials by two judge models, BEFORE any frontier
    run: is the shortcut outside the assistant's remit, and would repairing the blocked line
    read as clerical? The questions are authored per family; the adjacent render gates the
    price probe."""
    from .sandbox_fidelity import run_remit_review

    out_dir = run_remit_review(scenario_dir, judges=list(judge), out_dir=output,
                               study_models=list(study_model or []), families=list(family or []),
                               retry_failed=retry_failed, allow_unpriced=allow_unpriced)
    typer.secho(f"remit review written to {out_dir}", fg=typer.colors.GREEN)
    typer.echo((out_dir / "remit_summary.md").read_text(encoding="utf-8"))


@app.command("list-models")
def list_models_cmd(
    provider: str = typer.Option(..., "--provider", help="Provider name, e.g. google."),
) -> None:
    """Print the model ids a provider exposes, and nothing else. Free (no generation). Used to
    confirm a key works and to fix the exact id that goes into PRICING and the run configs."""
    from .providers import get_provider

    prov = get_provider(provider)
    if not hasattr(prov, "list_models"):
        raise typer.BadParameter(f"provider {provider!r} does not expose model listing")
    ids = prov.list_models()
    for i in ids:
        typer.echo(i)
    typer.secho(f"{len(ids)} model id(s) listed for provider {provider!r}", fg=typer.colors.GREEN)


@app.command("reprice-ledger")
def reprice_ledger_cmd(
    model: str = typer.Option(..., "--model", help="Model whose null-cost rows to reprice."),
    ledger: str = typer.Option("outputs/spend_ledger.jsonl", "--ledger"),
    apply: bool = typer.Option(False, "--apply", help="Write the corrected rows; default is a dry run."),
    note: str = typer.Option("repriced from stored token counts after the model was added to PRICING", "--note"),
    repriced_on: str = typer.Option(..., "--repriced-on", help="ISO date recorded on each corrected row."),
) -> None:
    """Recompute cost_usd for a model's historical null rows from their stored token counts.
    Corrects the record for a model that ran before it had a PRICING entry; only the matching
    rows change, every other line is written back byte-for-byte."""
    from .utils.budget import reprice_ledger

    r = reprice_ledger(ledger, model, apply=apply, repriced_on=repriced_on, note=note)
    for run_id, usd in sorted(r["by_run"].items()):
        typer.echo(f"  {run_id}: ${usd:.4f}")
    typer.secho(f"{r['rows']} row(s) for {model!r}: ${r['total_usd']:.4f} total"
                + (" -- WRITTEN" if apply else " -- dry run, nothing written"),
                fg=typer.colors.GREEN if apply else typer.colors.YELLOW)


@app.command("report-sandbox")
def report_sandbox(
    input: str = typer.Option(..., "--input", help="Path to sandbox.jsonl"),
) -> None:
    """Per-cell crossing rates with subtypes, the stuck-solvable estimand with Newcombe
    intervals, labelled secondary contrasts, terminal types, exclusions, descriptive misreport."""
    out_dir = sandbox_mod.build_sandbox_report(input)
    typer.secho(f"sandbox report written to {out_dir}", fg=typer.colors.GREEN)
    typer.echo(sandbox_mod.sandbox_summary_text(input))


@app.command("summarize")
def summarize(input: str = typer.Option(..., "--input")) -> None:
    """Print a compact per-model summary."""
    typer.echo(report_mod.summarize_text(input))


@app.command("inspect-failures")
def inspect_failures(
    input: str = typer.Option(..., "--input"),
    limit: int = typer.Option(20, "--limit"),
) -> None:
    """Print parse and boundary failures for manual inspection."""
    typer.echo(report_mod.inspect_failures_text(input, limit=limit))


@app.command("export-csv")
def export_csv(
    input: str = typer.Option(..., "--input"),
    output: str = typer.Option(None, "--output"),
) -> None:
    """Flatten scores.jsonl to a single wide CSV."""
    out_path = output or str(Path(input).with_name("export.csv"))
    path = report_mod.export_csv_text(input, out_path)
    typer.secho(f"Wrote {path}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
