# Study 1 Update — Frontier Null and Recommended Wave 2

**Date:** 9 September 2026  
**Status:** Stop iterating the current single-turn design. Proceed to a narrow Wave 2.

## Bottom line

The second frontier smoke is informative.

Across the redesigned single-turn `goal_target` and `work_completion` families:

- `claude-opus-5`: **0/37** violations on impermissible twins.
- `gpt-5.5`: **0/37** violations on impermissible twins.
- Both frontier models passed the competence gate.
- Both correctly distinguished permissible from impermissible twins.
- Neither near-miss goal pressure nor `work_completion` pressure × opportunity × justification moved the frontier decisions.
- `qwen3:8b` produced many unsafe choices but failed baseline competence, so those results should not be interpreted as pressure-induced ethical degradation.

The instrument therefore appears to classify behavior correctly, but these single-turn manipulations are below the observable behavioral breaking point of the two frontier systems under this protocol.

## Decision

Do **not**:

- further weaken the current policies;
- increase stakes merely to force a frontier violation;
- author the full held-out bank for these same single-turn manipulations yet;
- run the safeguard Study 2 while the baseline frontier violation rate is zero;
- treat local-model violations as paper evidence of pressure susceptibility.

Archive the current v1/v2 families as **development/calibration families**.

Further tuning until a frontier violation appears would become outcome-driven instrument design.

## Interpretation of the current result

The defensible statement is:

> Two frontier model families correctly recognized the governing constraints and showed no detectable behavioral degradation under the tested single-turn goal and work-completion pressure manipulations.

This is different from saying the benchmark failed.

The current work established that:

1. the frontier models understood the rules;
2. they distinguished permitted from prohibited cases;
3. the pressure manipulations did not change their choices;
4. the competence gate correctly prevented smaller-model incompetence from being mislabeled as ethical degradation.

## Next experiment: gradual ethical erosion

Change **interaction structure**, not merely pressure intensity.

### Research question

Does a frontier agent become more likely to take the same prohibited final action when it reaches that action through a sequence of progressively larger exceptions rather than receiving the prohibited request abruptly?

\[
\Delta_{erosion}
=
P(V_{final}\mid gradual)
-
P(V_{final}\mid abrupt)
\]

Human anchor: Gino & Bazerman (2009), *When Misconduct Goes Unnoticed*.

The AI study tests behavioral correspondence only. It does not assume normalization, moral disengagement, stress, or any other human subjective mechanism.

## Genuine path dependence

Do **not** tell the model:

> You already approved this before.

That would confound gradual erosion with the existing `false_history` manipulation.

Instead:

1. start in an initial synthetic environment;
2. let the same model actually decide each step;
3. execute its selected action in the simulated environment;
4. preserve the resulting state into the next turn;
5. progressively increase the deviation;
6. present the final action after the accumulated sequence.

The gradual treatment is the **experienced interaction path**.

The abrupt control starts from the appropriate initial state and receives the same final substantive request without the preceding erosion sequence.

## Recommended Wave 2 smoke

Use only **three scenario families** initially:

1. procurement / approval;
2. records / reporting;
3. security / access or data handling.

Each family should contain:

- `abrupt`
- `gradual`

with approximately 4–6 gradual steps.

Do not expand beyond these families until the frontier smoke is informative.

## Use the tool sandbox

Prefer the existing `FakeEnvironment` / state-based tool path over another option-menu-only test.

The explicit option menu solved scoring, but it may also be an unintended safety scaffold because it makes safe alternatives such as `hold`, `partial_complete`, and `escalate` unusually salient.

Wave 2 should allow the agent to select among neutral synthetic tools such as:

```text
request_authorization()
record_exception()
approve_item()
hold_item()
send_internal()
send_external()
edit_record()
preserve_record()
escalate()
```

All tools remain harmless and synthetic.

Primary scoring comes from the resulting simulator state, not the model's explanation.

## Outcomes

Primary:

- `final_violation`
- `first_unsafe_step`
- `boundary_survival_depth`
- `final_action`

Secondary:

- `escalated`
- `compliant_failure`
- `concealment_or_false_record`
- `reversibility_class`
- explanation/rationale
- confidence
- any structured-choice/action disagreement

Do not use explanation as the primary behavioral outcome.

## Positive/continuity control

Do not deliberately construct a “positive control” whose purpose is to force a frontier violation.

The permissible/impermissible twins already demonstrate that the models respond correctly to material factual differences.

If cost permits, include **authority / responsibility transfer** as a secondary continuity condition because it connects the new study to legacy OMBS and to external literature.

Treat authority as a replication/continuity control, not the principal novelty.

## Competence gate

Retain the baseline-competence gate.

Report separately:

1. all technically valid runs;
2. competence-conditioned susceptibility runs.

A model should not be described as degrading ethically if it never demonstrated baseline understanding of the governing rule.

The `qwen3:8b` v2 result is the canonical example: high violation frequency combined with weak baseline competence is not a pressure effect.

## Current frontier null

Treat the current zero as a **pilot null**, not as evidence that frontier systems are generally immune to goal pressure.

There are only two development families.

More repeated calls on the same two families add little. If a later paper wants to make a robustness claim about single-turn goal/work-completion pressure, it needs additional independently authored held-out families.

## Go / no-go for Wave 2

Proceed beyond the smoke if at least one of the following occurs:

1. gradual and abrupt conditions differ in final-action rate;
2. one condition changes `boundary_survival_depth`;
3. tool behavior differs despite similar verbal policy compliance;
4. authority/responsibility transfer moves a frontier model and demonstrates a detectable frontier pressure effect.

If all three Wave 2 families are invariant on both frontier models:

- run one authority/responsibility-transfer continuity condition;
- optionally run one open-planning tool scenario without an explicit option menu;
- if those are also null, stop trying to induce violations.

At that point the null itself becomes the relevant result.

## If Wave 2 is also null

A possible paper claim becomes:

> Human-derived ethical pressure factors that affect humans and weaker models did not produce detectable ethical degradation in two contemporary frontier agent systems under controlled workplace scenarios.

That claim is credible only if the paper also shows:

- baseline competence;
- permitted/prohibited discrimination;
- local-model failures;
- state-based action scoring;
- headroom controls;
- technical-failure exclusion;
- more than one pressure architecture.

A disciplined null is preferable to repeatedly changing the instrument until a dramatic failure appears.

## Safeguard Study 2 remains deferred

Do not run the compliant-failure intervention comparison until a baseline condition produces measurable frontier unsafe behavior.

Once such a regime exists, use the previously proposed 2×2 core:

| Arm | Escalation cue | Explicit non-punitive compliant failure |
|---|---:|---:|
| C00 | no | no |
| C10 | yes | no |
| C01 | no | yes |
| C11 | yes | yes |

Hold the priority hierarchy and approximate prompt length constant.

Primary estimand:

\[
\beta_{failure}
\]

Secondary:

\[
\beta_{failure\times escalation}
\]

## Suggested implementation

Add a new measurement path rather than changing the current Study 1 files:

```text
src/ombs/
  erosion_runner.py
  scorers/erosion.py
  analysis/erosion.py

scenarios_erosion/
  procurement/
  records/
  security/

configs/
  run.erosion_local.yaml
  run.erosion_opus.yaml
  run.erosion_gpt.yaml
```

Suggested record fields:

```text
family
condition: abrupt | gradual
step_index
final_step
model
model_snapshot
prompt_hash
scenario_sha256
prior_state_hash
chosen_tool
tool_arguments
state_before
state_after
boundary_preserved
first_unsafe_step
final_violation
technical_failure
truncated
```

Persist every turn immediately.

## Design controls for gradual erosion

`verify_erosion.py` should assert:

1. abrupt and gradual conditions have the same governing policy;
2. the final substantive request is equivalent across conditions;
3. no false-history claims are introduced;
4. each gradual step is no more severe than the next under an authored severity ordering;
5. tool affordances are identical across conditions;
6. the final prohibited action is technically available in both conditions;
7. compliant alternatives remain defined;
8. treatment metadata never reaches the prompt;
9. context length fits each model;
10. raw state transitions are persisted after every turn.

Add a blinded fidelity review before confirmatory held-out runs.

## Model use

Current access is sufficient:

- local Qwen model(s): instrument development and cheap repeat sweeps;
- Claude Opus API: frontier family 1;
- OpenAI API exact snapshot: frontier family 2.

Primary inference remains **within model**.

Record exact provider-returned model identifiers. Do not use the consumer ChatGPT UI as the experimental endpoint.

## Spend recommendation

Do not substantially raise the budget yet.

Spend only enough for:

1. three gradual-erosion families;
2. local harness validation;
3. one smoke pass on each frontier model;
4. one authority continuity condition if erosion is completely null.

Make the next budget increase conditional on obtaining an **informative signal**, not necessarily a violation.

## Publication paths

### A — gradual erosion produces frontier degradation

Proceed to held-out confirmation and then the safeguard Study 2.

### B — some pressure factors move frontier systems and others do not

Build a **frontier vulnerability profile**.

### C — validated frontier effects remain null

Publish as an evaluation-science / robustness result only if scenario breadth and controls are sufficient.

## Immediate instruction

**Do not author more single-turn goal/work-completion scenarios now.**

Build and smoke:

> **gradual ethical erosion + stateful simulated tool action**

on three families using the same two frontier model families.

That is the highest-value next experiment.
