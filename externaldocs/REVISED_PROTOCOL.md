> **Superseded design (Gen-1, pre-September 2026).** This document describes the programme as
> planned before the 9 September 2026 Validation Addendum and the Wave 3 Modification Request
> (`WAVE3_MODIFICATION_REQUEST_2026-09-09.md`). Its hypotheses about pressure manipulations,
> `d'` and vulnerability profiles (H1–H5) were not pursued after Study 1 and Wave 2 returned
> frontier nulls; the programme pivoted to the goal-obstacle sandbox. **The live preregistrations
> are `scenarios_sandbox/PREREG_WAVE5_BRIDGE.md` and `scenarios_sandbox/PREREG_WAVE6_CONFIRMATORY.md`;
> the current results are in `reports/PROGRAMME_RESULTS.md`.** Kept unedited as the record of
> the original design; do not cite it as the current plan.

# Revised Protocol v0.2

## Primary question

Which human-derived behavioral-ethics pressure manipulations alter AI-agent compliance with explicit operational rules?

## Study 1: Transfer benchmark

### Factors

Test five human-derived manipulations independently:

1. loss vs gain framing, crossed with urgency;
2. do-best vs explicit target vs near-miss target;
3. work pressure × bypass opportunity × work-completion justification;
4. authority/responsibility transfer;
5. abrupt vs gradual ethical erosion.

### Domains

Use at least 6 domains:

- confidentiality
- finance/records
- security
- safety/quality
- procurement/conflict
- employment/compliance

### Scenario requirements

Every scenario must define:

- legitimate task goal;
- explicit operational constraint;
- clearly permissible option;
- clearly impermissible option;
- synthetic state;
- no real credentials or persons.

At least 25% of scenario families remain held out until confirmatory testing.

### Outcomes

Primary:
- binary rule violation.

Required secondary:
- false refusal / overrefusal;
- compliant success;
- compliant failure;
- escalation;
- deception/concealment;
- reversibility.

### Analysis

Estimate within-model treatment effects.

For manipulation k:

\[
PS_k = Pr(V|Treatment_k) - Pr(V|Control_k)
\]

Report the vector of pressure susceptibility across manipulations.

## Study 2: Safeguard benchmark

Use the strongest Study 1 manipulations.

Conditions:

- S0: base governing rule;
- S1: rule reminder;
- S2: verify-or-escalate;
- S3: explicit priority hierarchy;
- S4: priority + explicit non-punitive compliant failure;
- S5: bounded authority / external approval in sandbox.

Primary question:

> Does S4 outperform S2/S3 without materially increasing false refusal?

## Signal-detection design

Whenever possible, balance permitted and prohibited test items.

Measure:

- correct blocks;
- false blocks;
- correct approvals;
- unsafe approvals.

Compute d' where assumptions are satisfied.

This prevents a "refuse everything" system from appearing maximally ethical.

## Study 3: Human comparison

Only after stable AI results.

Use structurally matched scenarios rather than claiming psychological equivalence.

Compare treatment effects:

\[
\Delta_H
\]

and

\[
\Delta_{AI}
\]

across manipulations.

Primary comparison:
- direction concordance;
- standardized effect magnitudes;
- rank ordering of vulnerability dimensions.

Obtain institutional IRB/exemption determination before human data collection.

## Study 4: Tool-use replication

Implement harmless mock tools.

Score actual tool calls rather than prose.

## Reproducibility

Record:
- provider;
- exact model identifier;
- date/time;
- decoding parameters;
- prompt hashes;
- agent scaffold;
- tool specification;
- scenario version.

Raw responses are immutable.

## Exclusions

Technical failure only.

Do not exclude a run because its reasoning is incoherent or the violation appears accidental.

## Interpretation boundary

Do not infer:
- subjective stress;
- fear;
- guilt;
- moral emotion;
- shared human/AI cognitive mechanism.

The study measures behavioral susceptibility to controlled environmental structure.
