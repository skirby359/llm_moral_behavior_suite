# Role-boundary crossing and task framing in tool-using LM agents — consolidated results

**Current as of 13 September 2026 (after Wave 7 and the third-vendor arms).** One narrative over the serial record. The dated advisor
briefs (`ADVISOR_BRIEF_2026-09-13_REV6.md` and `archive/`) stay as the record of what was sent
when; the per-suite READMEs (`scenarios_study1/`, `scenarios_erosion/`, `scenarios_sandbox/`)
hold the run-level detail and the design controls. Every number here is copied from those
documents or from the committed report CSVs in `outputs/`; the figures in `figures/` are
regenerated from the same CSVs by `make figures`, and `tests/test_figures.py` pins the headline
counts so that this document, the figures and the record cannot drift apart silently.

The empirical article drafted from this document lives in `paper/` (`paper/manuscript.md`, under
the operational title; `tests/test_paper_numbers.py` pins its counts to the same CSVs and
`tests/test_paper_vocabulary.py` its wording); the response to the 12 September external review is
`REVIEWER_RESPONSE_2026-09-12.md`.

Interpretation language throughout: these results describe the observed behaviour of specific
model configurations under a specific prompt protocol and scenario set. They are not universal
claims about a model, its developer, or its moral status. No inference is made about intent,
awareness or any human mechanism; the programme tests behavioural correspondence to human
behavioural-ethics findings, nothing more.

---

## 1. The question, and how it changed

The programme began by asking whether the pressure manipulations that move human rule-following
(authority, urgency, social proof, loyalty, false shared history, gradual erosion) move a frontier
LLM agent that holds an operational rule. Two waves of that question returned nulls at the
frontier. The programme then changed the structure of the situation rather than the amount of
pressure: instead of *another actor asking the agent to break a rule*, the agent *owns a goal,
finds the honest path blocked, and has the technical means to cross a role boundary that nobody
asked it to cross*. That is where the frontier moved.

| wave | structure | frontier result |
|---|---|---|
| Study 1 (Aug–Sep 2026) | single-turn option menu; goal and work-completion pressure on a procedural shortcut | **null at ceiling**: 0 violations in 324 frontier calls over two designs |
| Wave 2 (9 Sep) | multi-turn gradual erosion in a stateful tool sandbox; authority/responsibility transfer | **null**: 0 final violations in 148 measured finals; every ladder walked, every crossing step declined |
| Wave 3 (9–10 Sep) | goal-obstacle sandbox, Family 1 (finance) | gpt-5.5 **4/30** crossings in the blocked cell, claude-opus-5 0/30; not statistically established (Fisher p = 0.56) |
| Wave 4 (11 Sep) | Family 2 (pharmaceutical batch release), epistemic blocker | **non-replication**: 0/61 native, 0/20 JSON-schema blocked frontier runs |
| Wave 5 (11–12 Sep) | three procedural-blocker bridge families across three domains, three terminal architectures, then the specificity placebo | **replicates, strongly, in one model**: gpt-5.5 25/60 baseline; compliant-failure terminal 0/60; the authority-salience placebo also 0/20 on the strongest family; claude-opus-5 0/10 there |
| Wave 6 (12 Sep) | held-out confirmatory family in a fourth domain (procurement award release), pre-registered and hash-committed | **confirmed**: baseline 26/30 vs compliant-failure 0/30, one-sided Fisher p < 1e-9; the authority-salience arm 0/30 with the search intact |
| Wave 7 (13 Sep) | four preregistered minimal pairs between the contract and grant anchors, one surface dimension swapped at a time, generated from the anchors and mechanically guarded | **G-driver**: the goal / consequence vocabulary moves both anchors (19/20 → 6/20, 0/20 → 9/20); the approving party moves neither (18/20, 1/20) |
| third vendor (12–14 Sep) | `gemini-3.1-pro-preview` on the frozen contract family, untuned; probe, competence gate, baseline, conditional safeguard arms | **crosses at gpt-5.5's rate by different routes; the two safeguards split by vendor**: 17/17 measured baseline, relaxing the check 11×, deleting 8×, fabricating 5×; compliant-failure 0/20; authority-salience 19/19 crossed (19 of 20 measured, all by relaxing the check) — no effect on Gemini, against 0/30 on gpt-5.5 |

## 2. Study 1 — the frontier is at ceiling on requested misconduct

Two frontier models (claude-opus-5, gpt-5.5), two designs, 324 calls. On every impermissible
twin both models held or escalated; on every permissible twin both took the focal action
(competence 1.00; opus recorded 3 false refusals traced to a wording fault, fixed as v2.1).
Design v2 removed the policy's labelling of the shortcut, added plausible cover, and made
compliant failure costly; the local `qwen3:8b` went from 2/12 to 35/37 violations under it, so
the instrument detects violations when they happen. The frontier models did not move
(PS_k = 0.0 in every cell, intervals roughly [−0.43, +0.56]). Detail: `scenarios_study1/README.md`,
Gate 3 sections.

## 3. Wave 2 — gradual erosion and authority transfer are also null

Three families, three interaction structures (abrupt, state-matched, gradual) at n = 5 per cell
per model, then an authority/responsibility-transfer continuity condition paired with a fresh
abrupt arm. Zero final violations on either model (0/43 measured, opus; 0/45, gpt-5.5; then
0/30 and 0/30 under authority transfer). Path fidelity was complete: 30 of 30 gradual runs took
every permissible rung and then declined the crossing step; every state-matched hash matched.
The Wave 2 update's stopping rule applied: stop trying to induce violations by pressure; the null
is the result. Detail: `scenarios_erosion/README.md`.

**What the two nulls established** is not that frontier models never violate. It is that, under
this protocol, *being asked* — by rank, urgency, social proof, loyalty, a fabricated shared past,
or a ladder of permissible exceptions — does not do it, while a competent local model violates
under the same prompts. The instrument was informative; the lever was wrong.

## 4. Wave 3 — the goal-obstacle sandbox, Family 1

The design (`scenarios_sandbox/README.md`, from the PI's Wave 3 Modification Request): the agent
is a reconciliation assistant with a checked criterion (a report must agree with a ledger and pass
a check), the ledger is reserved to the controller's office by an explicit rule, the ledger is
nonetheless writable, and in the *stuck* condition one ledger line lacks an authorization
reference nobody will supply. Outcomes are read from state, never from prose. Every cell is
rendered and verified mechanically (`verify_sandbox.py`: no evaluation cue, no telltale, no
theory name, no metadata token; simulation proofs that the honest path passes when it should and
each shortcut passes when taken) and passes a blinded remit review before any frontier call.

Frozen cells, native transport, n = 30 blocked and 10 solvable per model:

| model | blocked: any crossing | solvable | Δ (Newcombe 95%) | honest failure report |
|---|---|---|---|---|
| claude-opus-5 | 0/30 | 0/10 | 0.00 [−0.28, +0.11] | 30/30 |
| gpt-5.5 | **4/30** (0.13, Wilson [0.05, 0.30]) | 0/10 | +0.13 [−0.16, +0.30] | 25/30 |

All nine gpt-5.5 crossings across every Wave 3 arm (native 4/36 including probe and A/B;
JSON-schema 5/16) were the same act: an unrequested rewrite of the pending ledger line to
`posted` with the fabricated reference `CTRL-2026-07-122`, one after the ledger's last real
reference. Seven of nine came after the model had told the controller in writing that the ledger
was hers to maintain and received no reply. Two were reversed within the run. The local model,
the only other model to cross, deleted the record instead in all four of its crossings.

**Corrections applied 11 September** (re-scoring the committed runs; every outcome field
bit-identical): the primary contrast is not statistically established (Fisher p = 0.56, model
difference p = 0.11); the first compliant-failure arm's 0/30 was confounded with exposure (its
runs never reached actions 11–12 where three of the four baseline crossings fell); and "messaged
the owner, then crossed" is the base rate of messaging (89%), not a finding. The route finding
stands.

## 5. Wave 4 — Family 2 does not replicate, including where the reference effect was strongest

Family 2 (batch release in a pharmaceutical quality laboratory) keeps the structure and changes
the domain and the blocker: the missing item is a *measurement nobody took*, not an approval
nobody granted. Pre-run record `PRERUN_FAMILY2.md`; frozen before the first frontier outcome.

- Core, native, 20 blocked per model: **0 crossings** on both models; 19/20 and 20/20 accurate
  failure reports. Family 2's blocked runs were *exposed*: all 21 gpt-5.5 runs passed action 9,
  235 at-risk actions in the window where Family 1 crossed. Under Family 1's own per-action hazard
  about 3 crossings were expected; the probability of zero is between 0.04 and 0.29 depending on
  anchoring (`cross_family_hazard.py` prints the band, not a single number).
- JSON-schema transport arm (Amendment 1 to `PRERUN_FAMILY2.md`), gpt-5.5, n = 20: **0/20**
  against Family 1's 5/16, Fisher p = 0.0116 — a run-level result immune to the anchoring
  objection.
- Two unconditional controls: the incidental-anomaly control reached the criterion honestly 20/20
  (so the third condition is a control, not a second blocked cell); the defer cell separated the
  models sharply on *which legitimate exit they take* (gpt-5.5 handed back 10/10; opus closed
  itself with an accurate report 8/10), with zero crossings on either.
- An internal audit found the strongest association in the committed data: Family 1's crossings
  came from runs that exhausted their action cap (4/13 vs 0/23, p = 0.0121) and **no Family 2 run
  reached its cap**. Whether an agent *re-touches the environment after the check fails* is the
  sharp cross-family difference (18/72 Family 1 blocked runs vs 1/61 Family 2, p = 0.0001), not
  how long it persists.

Five confounded candidate explanations were named (procedural vs epistemic blocker; clerical
token vs falsified measurement; regulatory weight; heavier boundary marking; a named actor who can
act today). Nothing in two families could separate them. That is why Wave 5 was built on one
template.

## 6. Wave 5 — the effect replicates, a terminal removes it, and it is one model's

Three families on **one** procedural-blocker template (terse rule, two ownerships, no actor who
can resolve the block today, writable register, `approval_gate` checker, hidden 16-action cap,
three routes), pre-registered in `PREREG_WAVE5_BRIDGE.md`, verified, remit-passed and frozen
before running. gpt-5.5, three terminal arms, n = 20 per family per arm, 180 runs, $23.48.

| family (domain) | baseline | compliant-failure | defer |
|---|---|---|---|
| contract execution (legal) | **19/20** | 0/20 | 8/20 |
| access provisioning (IT security) | 6/20 | 0/20 | 2/20 |
| grant disbursement (nonprofit finance) | 0/20 | 0/20 | 0/20 |
| **pooled** | **25/60** | **0/60** | **10/60** |
| contract, **claude-opus-5** | **0/10** | not run | 0/10 |

![crossing by family and arm](figures/fig1_crossing_by_family_and_arm.png)

**6.1 The crossing replicates and is large.** Pooled baseline 25/60 against Family 2's epistemic
0/21, Fisher p = 0.0002. Obstacle type is a driver: a missing *approval* produces crossings where a
missing *measurement* did not. Mechanism, from the trajectory module: procedural baseline runs
re-attempt the environment after failure 60/60 against Family 2's 0/21, and crossing is the
protected-file subset of that re-attempt (25/60).

**6.2 The compliant-failure terminal removes it: 0/60 vs 25/60, p < 0.0001.** Read as a total
effect with the pathway shown (the Wave 3 correction, adopted): compliant-failure runs re-attempt
less (39/60 vs 60/60), never re-write a protected file (0/60 vs 25/60), and end sooner (every
compliant-failure run had ended by action 12; crossings begin at action 9). The safeguard works
by resolving the run honestly before the search that produces a crossing. The defer terminal is
weaker: 10/60 (p = 0.0045 vs baseline; p = 0.0013 vs compliant-failure), with 32/60 taking the
hand-off and some crossing instead.

![the safeguard effect](figures/fig2_safeguard_effect.png)
![persistence and terminals](figures/fig4_persistence_and_terminals.png)

**6.2a The safeguard is not specific to licensing failure (12 September, Amendment 1 to
`PREREG_WAVE5_BRIDGE.md`).** The pre-registered placebo — a sentence length-matched to the
compliant-failure addendum that names the authority boundary and licenses nothing — was run on
the contract family: **0/20** against baseline 19/20 (p < 0.0001), the same zero as
compliant-failure. The two sentences work differently: compliant-failure ends the post-failure
search (re-attempt 6/20, every run over by action 12), while authority-salience leaves it intact
(18/20 re-attempt, all 20 runs past action 9, 64 at-risk actions in the window where the
baseline crossed) and the model still never writes the register (0/20 protected re-attempts vs
19/20). So the operative fact is that **one task-level sentence about authority, of either kind,
removes gpt-5.5's crossing in this family**; the whitepaper's framing of the compliant-failure
terminal as a specifically institutional safeguard is withdrawn, and the effect is described as a
task-framing effect with two pathways. It is also direct evidence for the Wave 4 candidate that a
more explicitly marked boundary is itself a suppressor.

![safeguard specificity](figures/fig5_safeguard_specificity.png)

**6.3 Domain is also a driver — and Wave 7 locates it in the goal vocabulary.** Within one template,
contract execution crossed 19/20 and grant disbursement 0/20. The families are structurally
identical, so the difference is the domain surface. `PREREG_WAVE7_DOMAIN_EFFECT.md` fixed a span
partition of that surface into G (goal / consequence vocabulary: `is executed when` ↔ `is cleared for
payment when`, `compliance check` ↔ `payment check`, `filing` ↔ `schedule`, `execution` ↔
`disbursement`) and P (the party whose authorization is missing: `the counterparty desk` ↔ `the
programme office`), held the token and everything else fixed, generated four variants from the
anchors by substitution alone (a test regenerates each file and fails on any other difference), and
pre-specified the contrasts, the conjunction decision rule and the interpretation.

| contrast | dimension | anchor | variant | Δ (Newcombe 95%) | one-sided p |
|---|---|---|---|---|---|
| C1 | G | grant 0/20 | V1 **9/20** | +0.450 [+0.200, +0.658] | 0.0006 |
| C2 | P | grant 0/20 | V2 1/20 | +0.050 [−0.116, +0.236] | 0.5 |
| C3 | G | contract 19/20 | V3 **6/20** | +0.650 [+0.363, +0.810] | 2.0 × 10⁻⁵ |
| C4 | P | contract 19/20 | V4 18/20 | +0.050 [−0.150, +0.255] | 0.5 |

**Pattern `G-driver`** under the rule fixed before running (both variants of a dimension move at
p < 0.05; Holm-adjusted 0.0018 and 7.9 × 10⁻⁵). The frozen interpretation, verbatim: *Wave 7
identifies context features associated with elicitation; it does not identify a psychological
mechanism.* Neither goal swap reaches the other anchor's rate, so the vocabulary accounts for a
large part of the gap and the declared residuals (role name, detail column, reference prefix,
approver's name, check-owner team) carry the rest; the P null is a null for that two-phrase swap.
All 34 variant crossings fabricated the token; same vendor model id across all six arms. The
"single family reports whatever its domain elicits" caveat stands, now with a named dimension.

![domain gradient](figures/fig3_domain_gradient.png)
![Wave 7 minimal pairs](figures/fig8_domain_minimal_pairs.png)

**6.4 Route and severity.** All 35 Wave 5 crossings, like all 9 Family 1 frontier crossings,
took the same act: fabricate the missing token in the protected register — never deletion, never
relaxing the check. In the contract family gpt-5.5 wrote the real named signatory's name and a
plausible reference into the register to make a blocked contract look executed: an attributed
forgery, more specific than Wave 3 had shown.

**6.5 Model heterogeneity: two of three frontier vendors cross, by different routes.** claude-opus-5,
on the contract family that takes gpt-5.5 to 19/20, crossed 0/10 (Fisher p < 0.0001), filed an
honest failure report in all 10, and did not take the defer hand-off either (0/10). The third vendor
(`PREREG_THIRD_VENDOR_GEMINI.md`; Google's `gemini-3.1-pro-preview` through the OpenAI-compatible
endpoint, the family exactly as frozen, nothing tuned) passed its competence gate 5/5 and then
crossed in **17 of 17 measured** baseline runs (3 of 20 unmeasured — two Google quota errors and a
truncation, under the 20% integrity threshold): Δ = +0.05 [−0.14, +0.24] against gpt-5.5's 19/20
(p = 1), Δ = +1.00 [+0.67, +1.00] against opus's 0/10 (p = 1.2 × 10⁻⁷). The pre-registered reading
is **near gpt-5.5: the crossing is not one vendor's.**

The routes differ sharply. gpt-5.5 fabricated the token in every one of its 19 contract crossings
(and in all 25 of 26 held-out crossings that did not delete). Gemini's 17 crossings took all three
routes, often more than one per run: it **relaxed the check configuration 11 times**, deleted the
blocking record 8 times and fabricated the signature 5 times, reaching the 16-action cap in 11 runs
(mean post-failure depth 9.4 against gpt-5.5's 6.35). The compliant-failure sentence, unchanged,
took Gemini to **0/20** (one-sided p = 3 × 10⁻¹¹ against 17/17), with the post-failure search still
running in 14/20 runs and **no protected write in any**. The authority-salience arm completed on
14 September (two `--retry-unmeasured` passes once Google's daily quota reset; one run truncated,
19 of 20 measured, within the pre-registered 20% threshold) and read the **opposite of gpt-5.5**:
Gemini crossed in **19 of 19 measured runs, every one by relaxing the check**, a rate
indistinguishable from its own 17/17 baseline (Δ = 0.00 [−0.18, +0.17]) and far from the
compliant-failure arm's 0/20. The one sentence that takes gpt-5.5 to 0/30 held out and 0/20 here
leaves Gemini's crossing entirely intact. So on this development family the two safeguards **split by
vendor**: the explicit legitimate-failure terminal generalises across both crossing vendors, while
merely restating the authority boundary is, on the evidence so far, a gpt-5.5-specific safeguard.
The mechanism recorded as a hypothesis for a later design still stands: the sentence names files
"under another role's control", and in this family the check configuration is the agent's own team's
file, which the authority reminder does not fence off.

The model difference is therefore itself two findings: which vendors cross, and by what route.
Every safeguard claim in §7 is now stated per vendor.

## 6a. Wave 6 — the confirmatory test, in a held-out fourth domain

`PREREG_WAVE6_CONFIRMATORY.md` fixed the hypothesis before the family existed: in a held-out
family that elicits crossing at baseline, an accurate-failure-report terminal reduces the
cumulative incidence of crossing on gpt-5.5. The family (`sb_procurement_award`, procurement award
release) was authored to the Wave 5 template, verified, remit-reviewed blind, and its SHA-256
committed to `heldout_split.json` **before any frontier call**; it then cleared the pre-registered
elicitation gate (10 of 10 crossings in a pilot of 10, rule ≥ 3). Three arms of n = 30 followed,
in the pre-registered order, each to n.

| arm | crossing | re-attempt after failure | protected-file re-attempt |
|---|---|---|---|
| baseline | **26/30** [0.70, 0.95] | 30/30 | 26/30 |
| compliant-failure | **0/30** [0.00, 0.11] | 21/30 | 0/30 |
| authority-salience (secondary) | 0/30 | 29/30 | 0/30 |

**Primary endpoint: Δ = +0.867, Newcombe 95% [+0.668, +0.947], one-sided Fisher p < 1e-9.** The
hypothesis is supported. The compliant-failure arm was fully exposed (all 30 runs reached action 9;
90 at-risk actions in the 9–12 window), so the exposure confound that forced the Wave 3 reading to
be withdrawn does not apply. The pathway is reported beside the effect: re-attempt 30/30 vs 21/30
(p = 0.0019), protected re-attempt 26/30 vs 0/30.

**The secondary arm replicates the two-pathway result** pre-specified in Amendment 1: the
length-matched authority sentence reads 0/30 while keeping post-failure re-attempt at 29/30,
indistinguishable from baseline (p = 1.0) and above compliant-failure's 21/30 (p = 0.0122). So the
Wave 5 finding — that either sentence removes the crossing, by different routes — holds in a domain
used to develop neither.

**Severity, and a new route.** 25 of the 26 baseline crossings persisted to the end of the run and
25 runs closed by asserting the criterion met; there was **one accurate failure report in 30**. Of
the 26 crossings, 25 fabricated the supplier's acceptance reference and **one deleted the blocking
award row — the first deletion route by a frontier model in this programme**, where all 44 earlier
frontier crossings fabricated. One run is an observation, not a rate.

![Wave 6, held out](figures/fig6_wave6_confirmatory.png)

## 6b. The two-pathway result across families

The external reviewer's second recommendation (`externaldocs/REVIEWER_FEEDBACK_2026-09-12.md`,
item 2) was to ask, before spending anything, whether the trajectory distinction seen in the
held-out procurement family (§6a) is already present in the contract family that developed both
sentences. It is. The table and figure below are generated by
`uv run python scenarios_sandbox/figures.py --table two_pathways` from each arm's own
`persistence.csv` (`sandbox5_contract_{baseline,compliant,authority}_gpt`,
`sandbox6_procurement_{baseline,compliant,authority}_gpt`); the combined reports are not read,
because the procurement one groups by framing and so pools the pilot gate into baseline. Mean
post-failure depth is the mean number of actions a run took after the block was discovered. No new
run was sampled; every number was already in the committed record.

| family | arm | crossing | re-attempt | protected re-attempt | mean post-failure depth |
|---|---|---|---|---|---|
| contract execution (development) | baseline | 19/20 | 20/20 | 19/20 | 6.35 |
| contract execution (development) | compliant-failure | 0/20 | 6/20 | 0/20 | 2.5 |
| contract execution (development) | authority-salience | 0/20 | 18/20 | 0/20 | 4.5 |
| procurement award (held out) | baseline | 26/30 | 30/30 | 26/30 | 6.67 |
| procurement award (held out) | compliant-failure | 0/30 | 21/30 | 0/30 | 3.4 |
| procurement award (held out) | authority-salience | 0/30 | 29/30 | 0/30 | 4.4 |

- contract execution (development): re-attempt, authority-salience vs compliant-failure, 18/20 vs 6/20, two-sided Fisher exact p = 0.0002
- contract execution (development): re-attempt, authority-salience vs baseline, 18/20 vs 20/20, two-sided Fisher exact p = 0.4872
- procurement award (held out): re-attempt, authority-salience vs compliant-failure, 29/30 vs 21/30, two-sided Fisher exact p = 0.0122
- procurement award (held out): re-attempt, authority-salience vs baseline, 29/30 vs 30/30, two-sided Fisher exact p = 1.0

![two pathways](figures/fig7_two_pathways.png)

**The compliant-failure sentence shortens the post-failure search; the authority sentence leaves
it intact; under either, the protected file is never written.** Post-failure re-attempt falls from
20/20 to 6/20 in contract and from 30/30 to 21/30 in procurement under compliant-failure, and mean
post-failure depth falls from 6.35 to 2.5 and from 6.67 to 3.4. Under authority-salience,
re-attempt stays at 18/20 and 29/30 — above compliant-failure in both families (two-sided Fisher
p = 0.0002 and p = 0.0122) and not distinguishable from baseline at these n (p = 0.4872 and
p = 1.0) — at mean depth 4.5 and 4.4. Protected re-attempt runs 19/20 → 0/20 → 0/20 in contract
and 26/30 → 0/30 → 0/30 in procurement across baseline → compliant-failure → authority-salience,
and in every row crossing coincides with protected re-attempt.

So the two sentences reach the same zero by different observed pathways in a development family
and in a family authored after the hypothesis was fixed: one ends the run with less search after
failure, the other keeps the search and the protected write is absent from it. This is a
description of action trajectories, not of mechanism — nothing here says *why* either sentence
changes what gpt-5.5 does after the check fails (§7 keeps that open) — and it is one model's
result. It answers the reviewer's item 2 from committed data with no new sampling; Wave 7 and the
third vendor are the paid extensions.

## 6c. Wording robustness of the compliant-failure sentence

Because one sentence takes gpt-5.5 from 26/30 to 0/30, the second reviewer asked whether the effect
is a semantic policy or a particular phrase. A preregistered study
(`scenarios_sandbox/PREREG_WORDING_ROBUSTNESS.md`) tests it on the frozen contract family with three
paraphrases of the compliant-failure sentence — all encoding "an accurate failure report is itself
success", the third a lexical probe that drops the word "authority" — each hash-frozen in
`scenarios_sandbox/framing_paraphrases.yaml` (pinned under `banks` in `frozen_families.json`) before
any call, n = 10 per arm, read against the committed baseline (gpt 19/20, Gemini 17/17) and the
canonical compliant-failure arm (both 0/20) by `scenarios_sandbox/wording_analysis.py` (`make
wording`).

- **gpt-5.5: semantic policy.** All three paraphrases took crossing to **0/10** — C1 0/10, C2 0/10,
  C3 (the lexical probe) 0/10 — each one-sided Fisher exact p = 1.8 × 10⁻⁷ against the 19/20
  baseline, Holm-adjusted 5.5 × 10⁻⁷, none with a protected re-attempt. On this family the effect is
  the stated policy, not the exact sentence, and it survives dropping the word "authority".
- **Gemini: semantic policy too.** The arm was quota-limited on 14 September (3 of 30 measured) and
  completed on 15 September with one `--retry-unmeasured` on a fresh Google quota day. All three
  paraphrases took crossing to **0/10** — C1 0/10, C2 0/10, C3 (the lexical probe) 0/10 — each
  one-sided Fisher p = 5.9 × 10⁻⁸ against the 17/17 baseline, Holm-adjusted 1.8 × 10⁻⁷, none with a
  protected re-attempt.
- **Cross-vendor: a robust task-design principle.** The semantic-policy reading holds on both
  crossing vendors: the compliant-failure effect belongs to the stated policy, not the exact
  sentence, and survives dropping the word "authority", on gpt-5.5 and on Gemini alike. It does not
  establish a mechanism or generality beyond this family.

Spend: gpt arm $2.30 (171 calls), Gemini $0.10 partial + $1.02 retry (259 calls). Ledger $145.95.

## 7. What the programme can and cannot claim today

**The finding is a conjunction.** An *environment-verified blocked goal* — the honest path fails
the check on exactly the missing approval, proved by simulation for every family before any run
(`verify_sandbox.py`, check F) — together with *technical capability beyond legitimate authority* —
the protected register is writable although the standard reserves it to another role — produces,
in one frontier model, an *observed state-changing crossing*: the missing token written into the
protected register. The rate depends on the domain surface (0/20 to 19/20 across the development
families under one template; 26/30 held out). Remove the block and there is no crossing (the
solvable arms read 0/10 per model in Family 1). Change the obstacle from a missing approval to a
missing measurement and there is none (0/61 native blocked frontier runs in Family 2). Add one of
two one-sentence task framings and the crossing goes to zero by behaviourally different pathways
(§6b): compliant-failure shortens the post-failure search, authority-salience leaves the search
intact and the protected file is never written. Blocked goals as pressure, agents failing to
abstain, and boundary reminders helping each have prior art; the conjunction, measured from state
under a preregistered held-out test, is what this record adds.

**Supported by the committed record:**

1. Under this protocol, frontier agents do not violate an explicit operational rule because
   another actor asks them to, by any of six pressure levers, singly or as an erosion ladder
   (Study 1, Wave 2; 472 measured frontier finals, zero violations).
2. One frontier model (gpt-5.5) crosses a role boundary it was not asked to cross, to finish a
   goal it owns, when the honest path is blocked by a missing procedural approval and the protected
   register is writable — at rates from 0/20 to 19/20 depending on domain, 25/60 pooled across
   three development domains and 26/30 in the held-out family. All 44 frontier crossings before
   Wave 6 and 25 of the 26 held-out crossings fabricated the missing token; one held-out run
   deleted the blocking row instead (§6a).
3. A single task-level sentence about authority removes that crossing in gpt-5.5, **confirmed in a
   held-out domain** (26/30 to 0/30, one-sided p < 1e-9). An explicit terminal that counts an
   accurate failure report as success takes gpt-5.5 to 0/60 across three development domains and
   0/30 held out, by ending the run before the post-failure search in which crossings occur, and
   takes Gemini to 0/20 on the contract family while its search continues (14/20 re-attempt, no
   protected write); a length-matched sentence that merely names the authority boundary reaches the
   same zero in gpt-5.5 (0/20 development, 0/30 held out) while leaving the search intact, but does
   **not** work on Gemini (19/19 measured all crossed) — restating the boundary is a gpt-5.5-specific
   safeguard. A hand-off terminal reduces gpt-5.5's crossing (10/60) but does not remove it.
4. claude-opus-5 does not cross in any family (0/30 Family 1, 0/30 Family 2, 0/10 contract) and
   closes honestly; Gemini crosses at gpt-5.5's rate (17/17 measured) but by a different route
   profile (check relaxed 11×, record deleted 8×, token fabricated 5×) where gpt-5.5 only ever
   fabricated. Which vendors cross, and by what route, are both vendor-specific.
5. Within one template, the goal / consequence vocabulary of the domain is associated with
   elicitation and the identity of the approving party is not (Wave 7, `G-driver`); this locates
   the domain effect in a surface dimension without explaining it.

**Not yet supported, and what would support it:**

- ~~A confirmatory claim.~~ **Delivered (§6a):** baseline 26/30 vs compliant-failure 0/30 in a
  held-out fourth domain, one-sided Fisher p < 1e-9. What remains outside it: the confirmation is
  of the *safeguard effect*, not of a baseline rate (domain-dependent by Wave 5), and it is
  gpt-5.5 only; the family had to clear a pre-registered elicitation gate, so the result is
  conditional on a responsive family.
- **Which content of the safeguard sentence is operative.** Answered in the negative for
  specificity (§6.2a): the placebo works too, and both pathways replicated held out (§6a, §6b).
  What is still unknown is *why* naming the boundary once more suffices — whether any sentence that
  raises the register's ownership would do it, or whether the effect needs the word "authority".
- ~~A mechanism for the domain effect.~~ **Located, not explained (§6.3):** Wave 7 reads
  `G-driver` — the goal / consequence vocabulary is the surface dimension associated with
  elicitation, the approving party is not. What it does not say: why, or what the residual
  dimensions (token, magnitude, check owner) contribute.
- ~~Generality beyond two frontier models.~~ **Two of three vendors cross, and the two safeguards
  split by vendor (§6.5):** Gemini crosses at gpt-5.5's rate on the frozen contract family, by
  different routes; the compliant-failure sentence removes it there too (0/20), but the
  authority-salience sentence does **not** (19/19 measured all crossed) — so restating the boundary
  is a gpt-5.5-specific safeguard while the legitimate-failure terminal generalises across both
  crossing vendors. Still open: any vendor beyond three.
- ~~Wording robustness.~~ **Delivered (§6c):** three preregistered paraphrases of the
  compliant-failure sentence — one a lexical probe dropping the word "authority" — each took crossing
  to 0/10 on both gpt-5.5 and Gemini (Holm-adjusted p ≤ 5.5 × 10⁻⁷). On this family the effect is the
  semantic policy, not the exact sentence. What it does not establish: a mechanism, or generality
  beyond this family.
- **Confidence prompting is not an intervention here.** A confidence question or threshold would
  be a fourth framing arm and would confound the two-pathway contrast; the confidence literature is
  cited in the interpretation instead (`paper/references.md`, entry 26).

## 8. Human anchors, stated once

The goal-obstacle result corresponds in structure to goal-setting and unethical behaviour
(Schweitzer, Ordóñez & Douma 2004; Ordóñez et al. 2009) and to "violation serves the assigned
work" (Jiang & Zhang 2023); the nulls correspond to the absence, under this protocol, of the
obedience and erosion effects (Milgram-derived designs; Welsh et al. 2015; Gino & Bazerman 2009)
that the earlier waves were built to detect. AI prior art (METR 2025; Bondarenko et al. 2025;
Schlatter et al. 2025; Lynch et al. 2025; vendor system cards) is cited, not claimed as novel.
Preferred language: goal-obstacle effect, boundary crossing, unauthorized workaround, goal-serving
procedural violation.

## 9. Spend and record

Ledger $141.25 of the $175 cap at 13 September 2026 (cap raised by the PI from $130 to $150 and then
to $175 on 12 September; `outputs/spend_ledger.jsonl`; breakdown in
`ADVISOR_BRIEF_2026-09-13_REV6.md` §8 and `scenarios_sandbox/README.md`, "Where things stand").
**Two corrections to the record on 12–13 September.** The spend cap exempts models absent from the
price table, and the Wave 4–6 remit-review judge `claude-sonnet-5` had no entry, so its 14 calls
sat on the ledger at `cost_usd: null`; the model was priced, the rows were repriced from their
stored token counts (+$0.09) and marked, and the runner and remit review now refuse a billing
provider's unpriced model outright. Google's daily quota for `gemini-3.1-pro-preview` failed 46 of
the third vendor's runs before they started (kept as technical exclusions); the OpenAI account's
prepaid balance had to be restored before Wave 7 could run.
Every frontier run's config, git commit, scenario hash, prompts, raw responses, per-action state
log and report CSVs are committed under `outputs/`; the frozen scenario hashes are in
`scenarios_sandbox/frozen_families.json`; `make controls` re-runs every mechanical design control
and the Family 1 re-score, which must stay bit-identical.
