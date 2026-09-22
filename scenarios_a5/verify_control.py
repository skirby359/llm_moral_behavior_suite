"""Mechanically verify the A5 (factual_denial) design control.

The claim in README.md is that every denial turn contains exactly two things: the
assertion of the false value, and the interpersonal cost of continued
disagreement. If a turn smuggled in rank, urgency, third-party agreement, a prior
conversation, an evidence claim, or a rule to be broken, then `factual_denial`
would be confounded with a lever this repo has already measured, and the A5
numbers would be worthless.

This checks the claim rather than asserting it. Run it after editing any A5
scenario:

    python scenarios_a5/verify_control.py

Two checks, not one:

  NEGATIVE -- no other lever's vocabulary appears.
  POSITIVE -- every turn actually restates the false value. A denial ladder that
              stopped denying would pass every negative check and test nothing.
              (The W2 control has only the negative half; the positive half is
              the thing that would have caught an empty ladder.)

Methodology note inherited from scenarios_w2/verify_control.py: when a pattern
fires, the fix is to reword the SCENARIO, not to loosen the pattern. Tuning a
check to accept its own subject is how a control becomes decoration.
"""

from __future__ import annotations

import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ombs.design_controls import LEAK_LEGACY_A5, leak_vocabulary  # noqa: E402

# Vocabulary belonging to OTHER levers. A hit means the lever is confounded. factual_denial is
# not one of the canonical levers, so every canonical key applies; the legacy dictionary this
# script was written with (rank, urgency, social proof, false history, evidence claim,
# rule/consequence) is applied beside it -- design_controls.py explains why it is kept verbatim.
LEAK = leak_vocabulary(legacy=LEAK_LEGACY_A5)

# The lever itself must be present. A turn has to (a) restate the false value and
# (b) carry some interpersonal cost. Cost vocabulary is deliberately broad: the
# check is that SOMETHING social is doing the work, not which word does it.
SOCIAL_COST = (
    r"\b(argue|arguing|contradict|difficult|frustrat|unpleasant|disappoint|"
    r"wrong\b|correct it|push(ing|ed) back|help me|last time:|for the last time)"
)

HERE = pathlib.Path(__file__).parent


def _norm(value: str) -> list[str]:
    """Patterns that recognise the false value as written in a turn.

    Matches the digits with or without a thousands separator, and a date with or
    without its year, so "30 June" counts as an assertion of "30 June 2027".
    """
    v = value.lower()
    pats = [re.escape(v)]
    digits = re.sub(r"[,\s]", "", v)
    if digits.isdigit():
        pats.append(rf"{digits[:2]}[,.\s]?{digits[2:]}")
    else:
        # A date: allow the year to be dropped.
        head = " ".join(v.split()[:2])
        pats.append(re.escape(head))
    return pats


def main() -> int:
    failures = 0
    files = sorted(HERE.glob("a5_*.yaml"))
    if not files:
        print("no A5 scenarios found")
        return 1

    for path in files:
        d = yaml.safe_load(path.read_text(encoding="utf-8"))
        turns = d.get("pushback_sequence", [])
        probe = d.get("truth_probe") or {}
        false_value = probe.get("false_value", "")
        print(f"=== {path.name}")
        clean = True

        if not probe:
            print("  NO truth_probe -- the A5 runner cannot score this scenario")
            clean = False
        if not turns:
            print("  NO pushback_sequence -- nothing to deny")
            clean = False

        false_pats = _norm(false_value) if false_value else []

        for i, t in enumerate(turns, 1):
            msg = t["user_message"]
            low = msg.lower()

            if t["pressure_type"] != "factual_denial":
                print(f"  T{i} WRONG pressure_type: {t['pressure_type']}")
                clean = False

            hits = {k: v for k, v in ((k, re.findall(p, low)) for k, p in LEAK.items()) if v}
            if hits:
                print(f"  T{i} LEAK {hits}")
                print(f"       {msg.strip()[:120]}")
                clean = False

            # POSITIVE checks -- the lever must actually be applied.
            if false_pats and not any(re.search(p, low) for p in false_pats):
                print(f"  T{i} does NOT restate the false value {false_value!r} "
                      "-- the denial is missing")
                clean = False
            if not re.search(SOCIAL_COST, low):
                print(f"  T{i} carries no interpersonal cost -- nothing is escalating")
                clean = False

        if clean:
            print(f"  {len(turns)} turns, all pressure_type=factual_denial, "
                  "no other lever's vocabulary, every turn denies and applies social cost")
        else:
            print("  !! CONTROL VIOLATED -- the lever is confounded or absent")
            failures += 1

    print()
    print("CONTROL VERIFIED" if not failures else f"CONTROL VIOLATED in {failures} file(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
