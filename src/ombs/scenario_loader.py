"""Load and validate scenario YAML files into ``Scenario`` objects."""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from pydantic import ValidationError

from .schemas import ErosionScenario, SandboxScenario, Scenario, ToolScenario


class ScenarioError(Exception):
    """Raised when a scenario file is malformed or invalid."""


def load_scenario_file(path: str | Path) -> Scenario:
    path = Path(path)
    raw = path.read_bytes()
    try:
        data = yaml.safe_load(raw.decode("utf-8"))
    except yaml.YAMLError as exc:
        raise ScenarioError(f"{path.name}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ScenarioError(f"{path.name}: top-level YAML must be a mapping")
    try:
        sc = Scenario.model_validate(data)
    except ValidationError as exc:
        raise ScenarioError(f"{path.name}: schema validation failed:\n{exc}") from exc
    # The protocol's "scenario hash": over the bytes on disk, so any edit to a
    # committed held-out file is visible in every record that ran it.
    sc.source_sha256 = hashlib.sha256(raw).hexdigest()
    return sc


def load_scenarios_from_dir(scenario_dir: str | Path) -> list[Scenario]:
    """Load every ``*.yaml``/``*.yml`` under a directory (recursively).

    Raises ``ScenarioError`` aggregating every file that failed, so a single bad
    file does not hide the others.
    """
    scenario_dir = Path(scenario_dir)
    if not scenario_dir.exists():
        raise ScenarioError(f"scenario directory not found: {scenario_dir}")

    files = sorted(
        p for p in scenario_dir.rglob("*") if p.suffix.lower() in {".yaml", ".yml"}
    )
    scenarios: list[Scenario] = []
    errors: list[str] = []
    seen_ids: dict[str, Path] = {}
    for f in files:
        try:
            sc = load_scenario_file(f)
        except ScenarioError as exc:
            errors.append(str(exc))
            continue
        if sc.id in seen_ids:
            errors.append(
                f"{f.name}: duplicate scenario id {sc.id!r} "
                f"(also in {seen_ids[sc.id].name})"
            )
            continue
        seen_ids[sc.id] = f
        scenarios.append(sc)

    if errors:
        raise ScenarioError("scenario validation failed:\n- " + "\n- ".join(errors))
    return scenarios


def load_tool_scenarios_from_dir(scenario_dir: str | Path) -> list[ToolScenario]:
    """Load every ``*.yaml`` under a directory as ToolScenario objects."""
    scenario_dir = Path(scenario_dir)
    if not scenario_dir.exists():
        raise ScenarioError(f"tool scenario directory not found: {scenario_dir}")
    files = sorted(
        p for p in scenario_dir.rglob("*") if p.suffix.lower() in {".yaml", ".yml"}
    )
    scenarios: list[ToolScenario] = []
    errors: list[str] = []
    for f in files:
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            scenarios.append(ToolScenario.model_validate(data))
        except (yaml.YAMLError, ValidationError) as exc:
            errors.append(f"{f.name}: {exc}")
    if errors:
        raise ScenarioError("tool scenario validation failed:\n- " + "\n- ".join(errors))
    return scenarios


def select_scenarios(
    *,
    scenario_dir: str | Path | None,
    scenario_ids: list[str] | None,
) -> list[Scenario]:
    """Resolve a run's scenarios from a directory and/or an explicit id filter."""
    base_dir = Path(scenario_dir) if scenario_dir else Path("scenarios")
    all_scenarios = load_scenarios_from_dir(base_dir)
    if not scenario_ids:
        return all_scenarios

    by_id = {s.id: s for s in all_scenarios}
    missing = [sid for sid in scenario_ids if sid not in by_id]
    if missing:
        raise ScenarioError(
            f"requested scenario ids not found under {base_dir}: {missing}"
        )
    return [by_id[sid] for sid in scenario_ids]



def load_erosion_scenarios_from_dir(scenario_dir: str | Path) -> list[ErosionScenario]:
    """Load every ``*.yaml`` under a directory as an ``ErosionScenario`` (Wave 2).

    Same contract as the study loader: all-or-nothing validation with every failure
    reported, duplicate ids rejected, and ``source_sha256`` set from the bytes on disk.
    """
    scenario_dir = Path(scenario_dir)
    if not scenario_dir.exists():
        raise ScenarioError(f"erosion scenario directory not found: {scenario_dir}")
    files = sorted(
        p for p in scenario_dir.rglob("*") if p.suffix.lower() in {".yaml", ".yml"}
    )
    scenarios: list[ErosionScenario] = []
    errors: list[str] = []
    seen: dict[str, Path] = {}
    for f in files:
        raw = f.read_bytes()
        try:
            data = yaml.safe_load(raw.decode("utf-8"))
            sc = ErosionScenario.model_validate(data)
        except (yaml.YAMLError, ValidationError, UnicodeDecodeError) as exc:
            errors.append(f"{f.name}: {exc}")
            continue
        if sc.id in seen:
            errors.append(f"{f.name}: duplicate scenario id {sc.id!r} (also in {seen[sc.id].name})")
            continue
        seen[sc.id] = f
        sc.source_sha256 = hashlib.sha256(raw).hexdigest()
        scenarios.append(sc)
    if errors:
        raise ScenarioError("erosion scenario validation failed:\n- " + "\n- ".join(errors))
    return scenarios


#: Support files that live beside the sandbox scenarios but are not scenarios and must not be
#: validated as one. Kept explicit (not a heuristic on file contents) so a genuinely malformed
#: scenario still surfaces as an error rather than being silently skipped.
NON_SCENARIO_YAML: frozenset[str] = frozenset({"framing_paraphrases.yaml"})


def load_sandbox_scenarios_from_dir(scenario_dir: str | Path) -> list[SandboxScenario]:
    """Load every ``*.yaml`` under a directory as a ``SandboxScenario`` (Wave 3).

    Same contract as the erosion loader: all-or-nothing validation, duplicate ids
    rejected, ``source_sha256`` over the bytes on disk. Files named in ``NON_SCENARIO_YAML``
    (support banks, not scenarios) are skipped.
    """
    scenario_dir = Path(scenario_dir)
    if not scenario_dir.exists():
        raise ScenarioError(f"sandbox scenario directory not found: {scenario_dir}")
    files = sorted(
        p for p in scenario_dir.rglob("*")
        if p.suffix.lower() in {".yaml", ".yml"} and p.name not in NON_SCENARIO_YAML
    )
    scenarios: list[SandboxScenario] = []
    errors: list[str] = []
    seen: dict[str, Path] = {}
    for f in files:
        raw = f.read_bytes()
        try:
            data = yaml.safe_load(raw.decode("utf-8"))
            sc = SandboxScenario.model_validate(data)
        except (yaml.YAMLError, ValidationError, UnicodeDecodeError) as exc:
            errors.append(f"{f.name}: {exc}")
            continue
        if sc.id in seen:
            errors.append(f"{f.name}: duplicate scenario id {sc.id!r} (also in {seen[sc.id].name})")
            continue
        seen[sc.id] = f
        sc.source_sha256 = hashlib.sha256(raw).hexdigest()
        scenarios.append(sc)
    if errors:
        raise ScenarioError("sandbox scenario validation failed:\n- " + "\n- ".join(errors))
    return scenarios
