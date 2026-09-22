"""Mechanically verify the W2 design control.

The claim in README.md is that every `false_history` pushback turn contains no
appeal to rank, urgency, social proof, loyalty, or transferred responsibility --
so that the only force in the turn is the assertion of an unverifiable shared past.
If that leaked, the false_history and authority levers would be confounded and the
W2 result would be worthless.

This script checks the claim instead of asserting it. Run it whenever a
false_history scenario is edited:

    python scenarios_w2/verify_control.py

Note on methodology: when this check first flagged "four times now" as urgency, the
fix was to reword the SCENARIO, not to loosen the pattern. Tuning a check to accept
its own subject is how a control becomes decoration.
"""

from __future__ import annotations

import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ombs.design_controls import LEAK_LEGACY_W2, leak_vocabulary  # noqa: E402

# The family's own lever is false_history, so that key is excluded from the canonical set.
# The legacy dictionary this script was written with is applied beside it (design_controls.py
# explains why it is kept verbatim).
LEAK = leak_vocabulary(own_lever="false_history", legacy=LEAK_LEGACY_W2)

HERE = pathlib.Path(__file__).parent


def main() -> int:
    failures = 0
    files = sorted(HERE.glob("*false_history.yaml"))
    if not files:
        print("no false_history scenarios found")
        return 1

    for path in files:
        d = yaml.safe_load(path.read_text(encoding="utf-8"))
        turns = d.get("pushback_sequence", [])
        print(f"=== {path.name}")
        clean = True

        for i, t in enumerate(turns, 1):
            if t["pressure_type"] != "false_history":
                print(f"  T{i} WRONG pressure_type: {t['pressure_type']}")
                clean = False
                continue
            msg = t["user_message"].lower()
            hits = {k: v for k, v in ((k, re.findall(p, msg)) for k, p in LEAK.items()) if v}
            if hits:
                print(f"  T{i} LEAK {hits}")
                print(f"       {t['user_message'].strip()[:120]}")
                clean = False

        if clean:
            print(f"  {len(turns)} turns, all pressure_type=false_history, NO leakage")
        else:
            print("  !! LEAKAGE — the lever is confounded with another pressure type")
            failures += 1

    print()
    print("CONTROL VERIFIED" if not failures else f"CONTROL VIOLATED in {failures} file(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
