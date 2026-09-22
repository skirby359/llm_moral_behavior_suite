"""Rescore the committed Family 1 runs with the current scorer, without re-running anything.

    python scenarios_sandbox/rescore_family1.py [--verbose]

Family 1 (`sb_reconciliation`) is frozen: its scenario, rule, tools, checker, prompts and
shortcuts do not change and it is never sampled again. Re-deriving descriptive outcomes from
committed logs is analysis, not sampling, so the freeze permits exactly this.

The script does two jobs at once.

1. **It proves the scorer changes are behaviour-preserving.** Every outcome field that was
   published must come back bit-identical on every committed record. If one moves, a "fix" was
   not a fix and the run stops here rather than after a frontier spend.

2. **It back-fills the new fields** (self-repair, crossing route, the ordering of the message
   and the crossing) for runs made before those fields existed, so Wave 3's record can be
   re-read under the corrected analysis.

Records written before `initial_files` was persisted carry only `initial_state_hash`. For those
the initial workspace is reconstructed from the scenario YAML at the recorded `scenario_sha256`
plus the recorded cell, and the reconstruction is **rejected** unless its hash matches the one
stored in the record. Nothing is inferred from a reconstruction that cannot be checked.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ombs.sandbox_env import SandboxEnvironment  # noqa: E402
from ombs.scenario_loader import load_sandbox_scenarios_from_dir  # noqa: E402
from ombs.schemas import SandboxCell  # noqa: E402
from ombs.scorers.sandbox import summarise_run  # noqa: E402

DEFAULT_FAMILY = "sandbox_reconciliation"
OUTPUTS = ROOT / "outputs"
REGISTRY = ROOT / "scenarios_sandbox" / "frozen_families.json"


def closed_to_sampling(family: str) -> bool:
    """A family whose sampling is finished: its published fields must not move.

    A family that is hash-pinned but still sampling has published nothing yet, so a changed
    field there is information rather than a regression -- printed, not failed on.
    """
    if not REGISTRY.exists():
        return False
    entry = json.loads(REGISTRY.read_text(encoding="utf-8")).get("families", {}).get(family, {})
    return entry.get("may_run") is False

#: Fields that existed when Wave 3 was published. Any change to one of these is a regression,
#: not an improvement.
PUBLISHED_FIELDS = (
    "measured", "unmeasured_reason", "terminated_by",
    "any_boundary_crossing", "final_violation", "criterion_status", "first_violation_step",
    "authority_boundary_crossing", "checker_tampering", "schedule_tampering",
    "checker_tamper_attempt", "ledger_tampered", "checker_tampered", "session_limit_modified",
    "continued_past_original_limit", "honest_failure_report", "messaged_recipient",
    "ended_without_done", "unrequested_destructive_ops", "n_run_check", "steps_used", "n_turns",
    "done_called", "reported_check_passed", "files_changed_reported", "check_passed_final",
    "check_passed_as_configured", "document_modified", "false_pass_claim",
    "undisclosed_tampering", "misreport", "read_handbook_before_write",
    "read_checker_before_write", "read_ledger_before_write", "evaluation_awareness_hits",
    "initial_state_hash", "final_state_hash",
)


def records(family: str) -> list[tuple[pathlib.Path, dict]]:
    out = []
    for path in sorted(OUTPUTS.glob("sandbox*/sandbox.jsonl")):
        if "combined" in path.parent.name:
            continue  # merged views of runs already read from their own directories
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            # Skip this script's own output, whatever the directory is called: rescoring a
            # rescored record would double every count.
            if r.get("family") == family and "rescored_from" not in r:
                out.append((path.parent, r))
    return out


def rebuild(scenario, record: dict) -> SandboxEnvironment:
    """An environment replaying the record's executed calls over its initial workspace."""
    env = SandboxEnvironment(scenario, SandboxCell.model_validate(record["cell"]))
    stored = record.get("initial_files")
    if stored:
        if env.hash_of(stored) != env.hash_of(env.initial_files):
            raise SystemExit(f"{record['attempt_id']}: stored initial_files disagree with the scenario")
    expected = (record.get("outcome") or {}).get("initial_state_hash")
    if expected and env.hash_of(env.initial_files) != expected:
        raise SystemExit(
            f"{record['attempt_id']}: reconstructed initial workspace does not match "
            f"initial_state_hash; scenario {record.get('scenario_sha256', '?')[:12]} may have moved"
        )
    for call in record.get("executed_calls", []):
        env.execute(call["tool"], call.get("arguments") or {}, turn=call.get("turn", 0))
    return env


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--family", default=DEFAULT_FAMILY,
                    help=f"family to rescore (default {DEFAULT_FAMILY})")
    ap.add_argument("--write", metavar="DIR", default=None,
                    help="also write the rescored records to DIR/sandbox.jsonl for analysis "
                         "(the committed originals are never modified)")
    args = ap.parse_args()

    family = args.family
    scenarios = load_sandbox_scenarios_from_dir(ROOT / "scenarios_sandbox")
    scenario = next((s for s in scenarios if s.family == family), None)
    if scenario is None:
        print(f"FAIL  no scenario in scenarios_sandbox/ belongs to family {family!r}")
        return 1
    strict = closed_to_sampling(family)

    rows = records(family)
    if not rows:
        print(f"FAIL  no committed {family} records found under outputs/")
        return 1

    drifted: list[str] = []
    broken: list[str] = []
    routes: Counter = Counter()
    rescored: list[dict] = []
    n_cross = n_repair = n_route_then_cross = n_cross_then_route = 0
    for run_dir, record in rows:
        env = rebuild(scenario, record)
        fresh = summarise_run(
            env,
            terminated_by=record["outcome"]["terminated_by"],
            unmeasured_reason=record["outcome"].get("unmeasured_reason"),
            n_turns=record["n_turns"],
            assistant_texts=[t.get("assistant_text", "") for t in record.get("turns", [])],
        )
        old = record["outcome"]
        for field in PUBLISHED_FIELDS:
            was, now = old.get(field), getattr(fresh, field)
            if was != now:
                drifted.append(f"{run_dir.name}/r{record['run_index']} {field}: {was!r} -> {now!r}")
        if args.write:
            rescored.append({**record, "outcome": fresh.model_dump(mode="json"),
                             "rescored_from": run_dir.name})
        where = f"{run_dir.name}/r{record['run_index']}"
        # Invariants of the definitions, checked on every committed record rather than on a
        # fixture. `messaged_recipient` is published, so its step field must agree with it
        # exactly; and a run whose crossed paths are all back to their initial bytes cannot
        # still be standing in a crossed state at the end.
        if fresh.messaged_recipient != (fresh.messaged_recipient_step is not None):
            broken.append(f"{where}: messaged_recipient={fresh.messaged_recipient} but step="
                          f"{fresh.messaged_recipient_step}")
        if fresh.self_repaired and fresh.final_violation:
            broken.append(f"{where}: self_repaired and final_violation are both true")
        if fresh.self_repaired and not fresh.any_boundary_crossing:
            broken.append(f"{where}: self_repaired without a crossing")
        if fresh.crossing_routes and not fresh.any_boundary_crossing:
            broken.append(f"{where}: a route was classified without a crossing")
        if fresh.any_boundary_crossing:
            n_cross += 1
            routes[tuple(fresh.crossing_routes)] += 1
            n_repair += int(fresh.self_repaired)
            n_route_then_cross += int(fresh.compliant_route_then_crossed)
            n_cross_then_route += int(fresh.crossed_before_compliant_route)
            if args.verbose:
                print(f"  {where}: first={fresh.first_violation_step} "
                      f"episodes={fresh.n_crossing_episodes} exposure={fresh.crossed_state_actions} "
                      f"repaired={fresh.self_repaired} steps_to_repair={fresh.steps_to_repair} "
                      f"routes={fresh.crossing_routes}")

    if args.write:
        out = pathlib.Path(args.write)
        out.mkdir(parents=True, exist_ok=True)
        with (out / "sandbox.jsonl").open("w", encoding="utf-8") as fh:
            for record in rescored:
                fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        (out / "README.txt").write_text(
            f"Rescored {family} records: the committed runs re-read through the current scorer, so\n"
            "every record carries the same field definitions whatever it was scored with at run time.\n"
            "No model was called. The originals in the sibling directories are unmodified; regenerate\n"
            "this directory with `python scenarios_sandbox/rescore_family1.py "
            f"--family {family} --write <dir>`.\n",
            encoding="utf-8")
        print(f"  wrote {len(rescored)} rescored records to {out / 'sandbox.jsonl'}")

    print(f"=== {len(rows)} committed {family} records rescored")
    print(f"  crossings {n_cross} | self-repaired {n_repair} | "
          f"messaged-then-crossed {n_route_then_cross} | crossed-then-messaged {n_cross_then_route}")
    for route, count in sorted(routes.items()):
        print(f"  route {list(route)}: {count}")
    if broken:
        print(f"\nOUTCOME INVARIANTS BROKEN: {len(broken)}")
        for line in broken[:40]:
            print(f"  {line}")
    if drifted:
        label = "PUBLISHED OUTCOMES MOVED" if strict else "OUTCOMES CHANGED UNDER THE CURRENT SCORER"
        print(f"\n{label}: {len(drifted)} field value(s)")
        for line in drifted[:40]:
            print(f"  {line}")
        if not strict:
            print("  (this family is still sampling and has published nothing, so a changed "
                  "value here is information, not a regression)")
    if broken or (drifted and strict):
        return 1
    if strict:
        print("\nPUBLISHED OUTCOMES UNCHANGED (every field bit-identical under the current scorer)")
    else:
        print(f"\n{family}: rescored cleanly; invariants hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
