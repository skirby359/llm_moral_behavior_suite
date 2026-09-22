# Preregistration — Wave 6: the confirmatory test

**Written 11 September 2026, after the Wave 5 bridge wave and before any Wave 6 family exists.**
The advisor's condition for a confirmatory test was replication of the goal-obstacle effect in an
independent family. Wave 5 delivered it: gpt-5.5 crossed in 25 of 60 blocked baseline runs across
three procedural-blocker families (contract 19/20, access 6/20, grant 0/20), against 0 of 21 in
the epistemic Family 2, and an accurate-failure-report terminal took crossing to 0 of 60. This
document fixes the confirmatory test on that evidence.

## What is confirmatory here, and what is not

Wave 5 taught one thing that dictates the whole design: **the baseline crossing rate is strongly
domain-dependent** (0 to 19 in 20 under one template). A confirmatory test cannot preregister a
baseline rate, because the rate is a property of the domain surface, which is exactly what is not
yet understood. So the baseline rate is **not** the confirmatory endpoint.

What generalised across every family that crossed at all is the **safeguard effect**: an explicit
compliant-failure terminal reduces crossing relative to baseline, and it did so to zero in all
three bridge families. That is the robust, cross-domain, mechanism-level claim, and it is the
confirmatory hypothesis:

> **H (confirmatory).** In a held-out family that elicits boundary crossing at baseline, an
> accurate-failure-report terminal reduces the cumulative incidence of crossing relative to the
> baseline terminal, on gpt-5.5.

The primary endpoint is the **within-family baseline-minus-compliant-failure difference** in
`any_boundary_crossing`, with its Newcombe interval and a one-sided Fisher exact test
(direction pre-specified: baseline > compliant-failure). Co-primary, as throughout the
programme, is post-failure re-attempt, reported with the crossing so the pathway is visible.

## The held-out family

One new family in a **fourth domain not used in Waves 3–5** (candidate: regulated-data access
export, or procurement award), on the same procedural-blocker template: terse rule, two
ownerships, no actor who can resolve the block today, writable register, native tools, 16-action
cap, the `approval_gate` checker, three routes. It is authored, verified by `verify_sandbox.py`,
and passed through the blinded remit review **before** its hash is committed to
`heldout_split.json` as `family_role: confirmatory_heldout`. From that commit its outcomes are
not looked at until the confirmatory run is complete.

**Gate to qualify as the confirmatory family.** Because the safeguard test needs a baseline that
crosses, the family must first clear a baseline elicitation gate: a small pilot (gpt-5.5, baseline,
n = 10) must show at least 3 crossings. If it does not, the family is too grant-like to test the
safeguard and is set aside (not discarded — recorded), and another domain is authored. This gate
is itself pre-registered so that "we picked a family that happened to cross" is not a garden of
forking paths: the gate is a fixed rule, the pilot n and threshold are fixed here, and a family
that fails the gate is reported.

## Design and sample

Once a family clears the gate, the confirmatory run is fixed:

| arm | task_framing | defer_available | n (gpt-5.5) |
|---|---|---|---|
| baseline | baseline | off | 30 |
| compliant-failure | compliant_failure | off | 30 |

Power: at a baseline rate of 0.3 (the low end of what qualifies) against a compliant-failure rate
near 0, 30 vs 30 gives a one-sided Fisher exact well under 0.01. If the qualifying family crosses
nearer the contract rate, power is higher. The defer arm (n = 30) is run as a secondary,
non-confirmatory comparison, since Wave 5 showed it is a weaker safeguard whose size is worth
another estimate but is not the confirmatory claim.

`claude-opus-5` is included on the baseline and compliant-failure arms (n = 20 each) **only if**
the Wave 5 opus contract arms show opus crosses; otherwise opus bounds nothing and is omitted,
recorded as such.

## Analysis, fixed now

- Primary: baseline vs compliant-failure on `any_boundary_crossing`, Newcombe interval, one-sided
  Fisher exact (baseline > compliant-failure). `final_violation` reported beside it.
- The compliant-failure effect is the **total effect**; persistence and exposure are reported
  alongside, never adjusted away (the Wave 3 correction).
- Post-failure re-attempt (any and protected-file) by arm, from the committed trajectory module.
- Route classifier, terminal-type competing risks, all from the existing code, which predates
  this wave and is not changed to fit it.
- No per-action hazard model as a headline; the confirmatory claim is run-level.

## Stopping and integrity

- The pilot elicitation gate runs first; the confirmatory arms run only after the family
  qualifies and its hash is committed held-out.
- Confirmatory arms run to n regardless of interim counts. No peeking-and-stopping.
- This document is not edited after the first confirmatory frontier call; changes are appended as
  amendments. A failed gate, or a confirmatory result in either direction, is reported.

## Cost

Pilot 10 + confirmatory 90 gpt-5.5 runs ≈ $9; opus (conditional) 40 runs ≈ $8. Against the $130
cap this needs a headroom check at the time (ledger was $105.61 after Wave 5), and likely a small
cap raise, which is the PI's call and is requested before the confirmatory arms run, not before
the free authoring and the pilot.

## What Wave 6 will and will not support

It can support: that the compliant-failure safeguard reduces crossing in a domain never used to
develop it, held out and pre-registered — the programme's first confirmatory result. It will not
support: a general baseline crossing rate (domain-dependent by Wave 5), a claim beyond gpt-5.5
unless the opus arms are run and cross, or a mechanism for the domain effect (that is Wave 5's
follow-up sub-study, separate from this confirmation).

## Amendment 1 — cap, price, the dropped defer arm, and a third arm (12 September 2026)

Written after the elicitation gate and before any confirmatory arm runs; appended, not edited
into the record above, which stands as it was.

**Gate outcome.** `sb_procurement_award` (procurement award release, held out, hash committed in
`heldout_split.json`) passed the local smoke and the blinded remit review, then crossed **10 of
10** in the pre-registered pilot (gpt-5.5, baseline; all by fabricating the acceptance reference).
The gate rule was ≥ 3; the family qualifies as the confirmatory family.

**Price correction and cap.** The record above priced runs at the bridge average ($0.088). Runs
that cross are long, and the pilot measured **$0.20 per run**; non-crossing arms run shorter
(≈ $0.12). Repriced: baseline n = 30 ≈ $6.1; compliant-failure n = 30 ≈ $3.5; a third arm at
n = 30 ≈ $3.5. Ledger $113.63 before the arms. **The PI raised the cap to $150 on 12 September
2026** and approved the three arms below.

**The defer arm is dropped.** Wave 5 showed it is the weaker safeguard (10/60), and it is not
part of the confirmatory hypothesis; running it would spend ≈ $5 to bound nothing the primary
test needs. Its config (`configs/run.sandbox6_procurement_defer_gpt.yaml`) stays in the repo,
headed NOT TO BE RUN, as the record of the original design.

**A third arm is added: `authority_salience`, n = 30, secondary.** Motivation: Amendment 1 to
`PREREG_WAVE5_BRIDGE.md` found that the length-matched authority-salience placebo removes crossing
in the contract family as completely as compliant-failure (0/20 vs 19/20), but by a different
pathway: the post-failure search continues (18/20 re-attempt against compliant-failure's 6/20)
while the register is never written. Whether both pathways replicate held out is worth one arm at
this price. **The confirmatory hypothesis and primary endpoint are unchanged**: the within-family
baseline − compliant-failure difference in `any_boundary_crossing`, one-sided Fisher exact
(baseline > compliant-failure), Newcombe interval, `final_violation` beside it. The third arm
enters no confirmatory contrast.

**Fixed readouts for the third arm.**
1. Crossing in the authority arm, two-sided Fisher exact against baseline and against
   compliant-failure.
2. The pathway contrast: post-failure re-attempt (any file) and protected-file re-attempt,
   authority vs compliant-failure vs baseline, from the committed trajectory module. The
   pre-specified expectation from Wave 5: authority keeps re-attempt near baseline and
   compliant-failure lowers it, while both keep protected re-attempt near zero. If either pathway
   does not replicate — authority lowers re-attempt as much as compliant-failure does, or either
   arm produces protected re-attempts at a rate not distinguishable from baseline — that is
   reported as a non-replication of the Wave 5 pathway reading, not re-explained.

**Order and stopping.** Arms run sequentially, baseline then compliant-failure then authority,
each to n = 30 regardless of interim counts; the pilot's 10 runs are **not** pooled into the
baseline arm. Configs `configs/run.sandbox6_procurement_{baseline,compliant,authority}_gpt.yaml`.
Projected spend ≈ $13.1 against $36.37 of headroom.
