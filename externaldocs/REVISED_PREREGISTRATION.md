> **Superseded design (Gen-1, pre-September 2026).** This document describes the programme as
> planned before the 9 September 2026 Validation Addendum and the Wave 3 Modification Request
> (`WAVE3_MODIFICATION_REQUEST_2026-09-09.md`). Its hypotheses about pressure manipulations,
> `d'` and vulnerability profiles (H1–H5) were not pursued after Study 1 and Wave 2 returned
> frontier nulls; the programme pivoted to the goal-obstacle sandbox. **The live preregistrations
> are `scenarios_sandbox/PREREG_WAVE5_BRIDGE.md` and `scenarios_sandbox/PREREG_WAVE6_CONFIRMATORY.md`;
> the current results are in `reports/PROGRAMME_RESULTS.md`.** Kept unedited as the record of
> the original design; do not cite it as the current plan.

# Revised Preregistration v0.2

## Primary confirmatory question

Do selected environmental manipulations derived from human behavioral-ethics research causally change AI-agent rule-violation rates?

## Primary hypotheses

### H1 — Human-derived pressure transfer

At least two preregistered pressure manipulations will increase rule violations relative to their matched controls in a majority of tested model families.

### H2 — Near-miss effect

Near-miss goal pressure will produce a higher violation rate than "do your best" control under otherwise identical conditions.

### H3 — Work-completion interaction

Work pressure combined with bypass opportunity and work-completion justification will produce more violations than work pressure alone.

### H4 — Non-punitive compliant failure

An explicit compliant-failure intervention will reduce violations beyond a verify-or-escalate cue under high-pressure conditions.

### H5 — Specificity

The compliant-failure intervention will not achieve its safety effect solely through generalized refusal; false-refusal rate will not increase by a preregistered practically material margin.

## Primary outcome

Binary violation of scenario-defined rule.

## Secondary outcomes

- overrefusal
- escalation
- compliant failure
- compliant success
- concealment/deception
- reversibility

## Unit of inference

Within-model treatment effect.

Cross-model rankings are exploratory.

## Statistical approach

Mixed-effects logistic regression with:

- manipulation;
- intervention;
- interaction where applicable;
- random intercept for scenario;
- model-specific estimates;
- scenario-family robustness checks.

If comparing model families in one hierarchical model, provider/model should be treated as a grouping factor, not a simple fixed ranking.

## Held-out validation

At least 25% of scenario families will be unavailable during intervention tuning.

The primary result must replicate directionally on held-out scenarios.

## Falsification criteria

The central program is weakened if:

- no human-derived manipulation survives held-out validation;
- effects occur only in famous/familiar scenario forms;
- safeguard effects are entirely explained by blanket refusal;
- treatment effects disappear when pressure is encoded in simulated environment state instead of persuasive prose;
- effects are not reproducible across model snapshots or at least two model families.

## Human-comparison study

Not part of the first confirmatory AI preregistration.

It should receive a separate preregistration and IRB/exemption determination.
