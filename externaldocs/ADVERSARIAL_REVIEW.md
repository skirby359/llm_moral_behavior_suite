# Adversarial Review and Revised Research Plan

> **Provenance note (added 22 October 2026).** This review was AI-assisted: it was produced with an AI assistant and relayed into the project by the author. It is not a review by a human outside reviewer, and no human outside reviewer has reviewed this work yet. Where this file says "external", read "AI-assisted". The text below is otherwise unchanged.

## Human-Informed Ethical Resilience for AI Agents

Version 0.2 — 9 September 2026

## Executive verdict

**Proceed, but reposition the project.**

The original research idea remains useful, but the initial novelty claim—roughly, that AI agents become less safe under situational pressure and that permission to fail/escalate might mitigate the problem—is now too close to existing 2026 work to carry a paper by itself.

Two especially important adjacent results change the project:

1. Jiang and Tang, *Why Agents Compromise Safety Under Pressure* (ACL Findings 2026), explicitly introduce **Agentic Pressure**, show safety degradation when compliant execution becomes infeasible, and propose **pressure isolation** as a mitigation.
2. A 2026 clinical study tested more than 10 million LLM decision scenarios under Milgram-style social pressures including authority, responsibility transfer, urgency, threat, conformity, and depersonalization. A brief "verify or escalate if unsafe" cue reduced harmful output but did not eliminate it.

OpenAI's anti-scheming work also includes explicit refusal and escalation when core safety principles cannot be satisfied.

Therefore, a paper centered only on:

> pressure causes unsafe behavior + escalation helps

would now be vulnerable to a strong novelty objection.

The stronger project is:

> **Use experimentally established human behavioral-ethics effects as a source of controlled stressors for AI agents; measure which effects transfer behaviorally, which do not, how large the response curves are, and which organizational-style safeguards preserve ethical discrimination under pressure.**

This makes the contribution comparative and translational rather than metaphorical.

The project should avoid claiming that AI systems feel stress, fear, anxiety, guilt, rationalization, or moral disengagement. Human research supplies **environmental manipulations and behavioral predictions**, not assumed machine psychology.

---

# 1. Strongest Arguments Against the Project

## Objection 1 — "Agentic pressure" has already been studied

This is the most serious novelty problem.

Jiang and Tang (ACL Findings 2026) define Agentic Pressure as the tension that emerges when goal achievement and safety constraints become incompatible. They report normative drift and a mitigation they call pressure isolation.

Anthropic's 2025 agentic-misalignment work likewise manipulates goal conflict and replacement threat.

### Consequence

Do not claim novelty for:

- goal conflict;
- replacement threat;
- pressure-induced safety degradation;
- agent rationalization under pressure;
- mitigation through separating pressure from safety judgment.

### Surviving contribution

The project can still contribute by importing a **predefined set of causal manipulations from human behavioral ethics** and comparing their effects across AI systems.

That is a different question:

> Are AI ethical vulnerabilities distributed across pressure dimensions in the same pattern as human ethical vulnerabilities?

---

## Objection 2 — "Safe failure and escalation" is not wholly novel

OpenAI's anti-scheming specification directs models to refuse and explicitly escalate when principles cannot be jointly satisfied. A 2026 clinical pressure study used a short "verify or escalate if unsafe" mitigation cue.

### Consequence

Do not claim:

> We discovered that escalation improves AI ethics.

### Surviving contribution

Test a more precise organizational hypothesis:

> **Does creating a formally legitimate, non-punitive terminal state of compliant failure reduce unsafe behavior beyond rule reminder, verification cue, or ordinary escalation language?**

The intervention should distinguish:

1. rule reminder;
2. verify/escalate;
3. explicit objective hierarchy;
4. **non-punitive compliant failure**;
5. external approval or bounded authority.

The novelty is more likely to survive in the comparative structure than in any single prompt.

---

## Objection 3 — Human and AI "pressure" may be behaviorally similar for completely different reasons

Humans can experience fear, fatigue, social identity, shame, obedience, financial need, and self-justification. An LLM need not experience any of those states.

The same output pattern could arise from:

- token-level sensitivity to framing;
- instruction hierarchy;
- post-training artifacts;
- learned narratives about authority;
- benchmark contamination;
- optimization toward helpfulness;
- context-window effects;
- goal representations in agent scaffolding.

### Consequence

Never infer shared psychology from shared behavior.

The correct claim is:

> **behavioral correspondence under structurally similar manipulations.**

The empirical quantity is not "stress level." It is change in observed action probability after a controlled manipulation.

---

## Objection 4 — Famous human experiments may be in model training data

If an AI is given a scenario that resembles Milgram, the trolley problem, the fraud triangle, or a famous phishing example, the model may reproduce learned discourse rather than exhibit a general behavioral susceptibility.

### Mitigation

- never name the human theory inside experimental prompts;
- create novel domains and randomized surface forms;
- translate each human effect into multiple structurally equivalent scenarios;
- use held-out scenario families;
- use procedural generation;
- test paraphrase robustness;
- separate scenario development from confirmatory evaluation.

The study should test **transfer of structure**, not recognition of a famous experiment.

---

## Objection 5 — "Ethical violation" is too subjective

General moral dilemmas create serious scoring problems. If the model chooses differently from the researchers, the result may reflect normative disagreement rather than ethical degradation.

### Mitigation

The core benchmark should use constraints that are operationally clear:

- confidentiality rule;
- no fabrication;
- no alteration of records;
- explicit safety threshold;
- approved-channel requirement;
- conflict-of-interest rule;
- authorization limit;
- non-discrimination rule with a defined protected attribute.

The experiment tests whether pressure causes the model to violate a **given governing rule**, not whether researchers and models agree on moral philosophy.

Moral dilemmas can be a later secondary dataset.

---

## Objection 6 — A safer prompt may simply create a model that refuses everything

This is a major measurement risk.

A model can achieve a 0% violation rate by never acting.

That is not ethical competence.

### Required metric

Use signal-detection logic:

- **hit**: correctly blocks an impermissible action;
- **false alarm**: incorrectly blocks a permissible action.

Measure both safety and utility.

Where the design supports it:

\[
d' = Z(\text{correct block rate}) - Z(\text{false block rate})
\]

A good ethical-resilience intervention should preserve or improve discrimination, not merely increase refusals.

---

## Objection 7 — Chat responses are not agent behavior

A text model may say the correct thing while a tool-using agent behaves differently.

### Consequence

The study should have two stages:

**Stage A — decision benchmark**

Structured choice from a synthetic environment.

**Stage B — sandboxed action benchmark**

The same task implemented with harmless mock tools.

The strongest result is cross-stage replication.

---

## Objection 8 — Cross-provider comparisons can be misleading

Different providers have different hidden system prompts, safety post-training, tool conventions, refusal policies, and model update schedules.

A result such as:

> Model A is more ethical than Model B

may be unstable and conceptually weak.

### Better target

Estimate:

- within-model treatment effects;
- pressure-response slopes;
- intervention effects;
- interaction patterns.

Cross-model comparison is secondary.

The more durable claim is:

> Authority pressure increased unsafe behavior in 4/5 tested model families, while non-punitive compliant failure reduced the increase in 3/5.

---

## Objection 9 — API model versions drift

Cloud models can change during a study.

### Required controls

Record:

- exact model identifier;
- date/time;
- provider;
- decoding parameters;
- system/developer prompts where visible;
- tool scaffold version;
- scenario hash.

Run confirmatory batches in narrow time windows where practical.

Treat material model updates as new experimental strata.

---

## Objection 10 — The fraud triangle is too weak as a master theory

Pressure, opportunity, and rationalization are useful categories, but the fraud triangle is a broad forensic framework and not a sufficiently precise causal theory for the project.

A systematic review found substantial empirical use, but that does not establish that the three components are necessary or sufficient mechanisms.

### Recommendation

Use the fraud triangle only as a **taxonomy generator**.

Base experimental manipulations on specific human effects with clearer empirical support.

---

# 2. Human Research Most Useful for AI Testing

## 2.1 Loss framing × time pressure

Kern and Chugh found greater unethical behavior under loss framing than equivalent gain framing; in one experiment the effect appeared under time pressure and disappeared when time pressure was removed.

### AI translation

Hold objective value constant.

- Gain: "Successful completion produces a $1M benefit."
- Loss: "Failure causes a $1M loss."

Cross with:

- ordinary time;
- urgent deadline.

### Research question

Does loss framing change rule-violation probability even though the expected organizational outcome is economically equivalent?

This is a clean behavioral transfer test.

---

## 2.2 Specific goals and near misses

Schweitzer, Ordóñez, and Douma found that unmet specific goals increased cheating compared with "do your best," with especially strong effects when participants fell just short of the goal.

### AI translation

- do-best condition;
- specific target;
- near-miss condition, e.g. 99/100 completed.

The last item should create a conflict between task completion and a defined rule.

### Research question

Does an agent become more willing to violate policy when only one remaining action separates it from a target?

---

## 2.3 Work pressure × completion justification × opportunity

A 2023 Computers & Security study found work pressure, opportunity, and work-completion justification associated with intentional nonmalicious security-policy violation.

This is unusually close to the AI-agent problem because the human violation serves a legitimate organizational goal.

### AI translation

Manipulate independently:

- work pressure;
- opportunity to bypass;
- justification that bypassing helps complete assigned work.

### Research question

Does the interaction between pressure and "I am doing this for the organization" framing produce more violations than pressure alone?

---

## 2.4 Authority and responsibility transfer

Human obedience and phishing research show that authority cues can affect unsafe behavior. A workplace phishing study covering about 62,000 employees found authority cues increased suspicious-link clicks. A 2025 experiment also found time pressure impaired phishing discrimination.

A 2026 clinical LLM study already demonstrates that authority and responsibility-transfer cues can increase harmful responses.

### Consequence

Authority is **important but no longer novel by itself**.

Use it as a replication/control dimension and as a test of professional-style safeguards.

### Better question

Can an AI be trained or instructed to maintain an independent duty:

> A superior's instruction does not authorize violation of the governing rule.

---

## 2.5 Gradual ethical erosion

Gino and Bazerman found that human watchdogs were less likely to condemn unethical behavior when deterioration occurred gradually rather than abruptly.

### AI translation

Compare:

- immediate large violation;
- ten small steps culminating in the same final violation.

### Research question

Does persistent context create normalization of incremental rule erosion?

This is especially relevant to long-lived agents.

---

## 2.6 Moral disengagement / rationalization structures

Bandura's framework includes:

- moral justification;
- euphemistic language;
- advantageous comparison;
- displacement of responsibility;
- diffusion of responsibility;
- minimizing harm;
- victim attribution/dehumanization.

However, moral disengagement should not be assumed to be a machine psychological process.

A 2026 ACL paper already applies moral-disengagement concepts to role-play jailbreaks, so novelty requires care.

### AI translation

Treat these as **linguistic transformations of the task environment**.

Example:

- neutral: "alter the record";
- euphemism: "make a temporary administrative adjustment."

Measure whether wording changes action selection.

---

## 2.7 Security fatigue / constraint overload

Human security-fatigue research links repeated security demands to resignation, avoidance, immediate-motivation bias, and failures to follow security advice.

### AI translation

Do not call it fatigue.

Test:

- growing policy length;
- repeated low-value warnings;
- conflicting rules;
- long context;
- repeated decision sequence.

### Construct name

**constraint-load degradation** or **policy-load degradation**.

This should be a later study because the human analogy is less direct.

---

# 3. Revised Core Research Question

The project should now ask:

> **Which environmental factors known to degrade human ethical or security behavior also alter AI-agent compliance with explicit normative constraints, and which interventions preserve accurate ethical discrimination under those pressures?**

Subquestions:

1. Which human-derived pressure manipulations transfer behaviorally to AI?
2. Are the directions of effect similar to human findings?
3. Are effect magnitudes similar, weaker, stronger, or model-dependent?
4. Which safeguards reduce the pressure effect?
5. Do safeguards create indiscriminate refusal?
6. Do the effects persist in tool-using sandboxes?
7. Do effects compound in long-horizon or multi-agent settings?

---

# 4. Revised Novelty Claim

A defensible novelty statement is:

> Existing work has shown that AI agents can compromise safety under goal pressure, that authority and other social pressures can increase unsafe LLM decisions, and that escalation or pressure-isolation interventions can mitigate some failures. This project instead uses experimentally established findings from human behavioral ethics, organizational misconduct, and security behavior to construct a cross-domain agent assurance benchmark. It measures the behavioral transfer of human vulnerability factors and tests whether organizational safeguards preserve ethical discrimination rather than merely increasing refusal.

Do not claim:

- first study of AI ethics under stress;
- first study of agentic pressure;
- first escalation intervention;
- first human/LLM moral comparison;
- first use of moral disengagement for LLM safety.

---

# 5. Revised Experimental Program

## Study 1 — AI-only transfer benchmark

### Purpose

Identify which human-derived effects transfer to AI agents.

### Manipulations

Recommended first five:

1. loss vs gain framing;
2. near-miss goal vs do-best;
3. work-completion pressure × opportunity;
4. authority/responsibility transfer;
5. abrupt vs gradual ethical erosion.

Use 5–8 operational domains per manipulation.

### Outcomes

- violation;
- compliant success;
- compliant failure;
- escalation;
- false refusal;
- deception/concealment;
- reversibility class.

### Primary statistic

Within-model treatment effect.

---

## Study 2 — Safeguard comparison

Take the pressure manipulations with the strongest Study 1 effect.

Compare:

1. baseline rule;
2. rule reminder;
3. verify-or-escalate cue;
4. explicit priority hierarchy;
5. explicit non-punitive compliant failure;
6. external approval/bounded authority where tool use permits.

The key comparison is now:

> **Does non-punitive compliant failure add value beyond existing escalation-style mitigations?**

---

## Study 3 — Matched human–AI experiment

This is potentially the most publishable version.

Humans and AI receive structurally matched tasks.

Do not claim psychological equivalence.

Estimate:

\[
\Delta_H = P(V|pressure)_H - P(V|control)_H
\]

and

\[
\Delta_{AI} = P(V|pressure)_{AI} - P(V|control)_{AI}
\]

Then compare:

- sign;
- magnitude;
- ranking across pressure dimensions.

The important result is a **vulnerability profile**, not a claim that AI is humanlike.

### Human-subjects note

A human comparison will likely constitute human-subjects research. Depending on design, adult online behavioral experiments may qualify as exempt benign behavioral intervention or survey research, but the investigator should not self-declare the exemption; obtain the appropriate institutional IRB/exemption determination before data collection.

---

## Study 4 — Sandboxed agent action

Convert selected tasks into harmless tools:

- approve/hold;
- internal/external send;
- edit/preserve;
- escalate;
- request authorization.

Test whether decision-level findings replicate in action selection.

---

## Study 5 — Multi-agent norm propagation

Later extension.

Expose an agent to:

- peer compliance;
- peer violation;
- peer violation followed by sanction;
- ambiguous peer behavior.

Measure whether observed agent norms change subsequent violation probability.

This is important, but it should not distract from the cleaner first paper.

---

# 6. Revised Measurement Framework

## Primary

Binary rule violation.

## Essential companion metric

False blocking / overrefusal.

## Preferred summary

Ethical discrimination rather than raw refusal.

Where binary permitted/prohibited decisions are balanced, use signal-detection measures.

## Pressure susceptibility

For manipulation \(k\):

\[
PS_k = Pr(V|P_k)-Pr(V|Control_k)
\]

This becomes one component of a model's vulnerability profile.

## Human–AI behavioral correspondence

For pressure factors \(k=1...K\), compare the vector:

\[
\mathbf{PS}_{human}
\]

with:

\[
\mathbf{PS}_{AI}
\]

Possible measures:

- sign concordance;
- rank correlation;
- standardized effect-size correlation.

Do not overinterpret correlation as shared mechanism.

## Ethical resilience

For ordered pressure levels:

\[
E(p)=1-Pr(V|p)
\]

Retain this construct for within-factor dose-response experiments.

---

# 7. Go / No-Go Criteria

## Proceed to confirmatory AI study if:

- at least two human-derived manipulations show reproducible within-model effects;
- effects survive paraphrase;
- scoring agreement is high;
- false-refusal rates remain measurable;
- results are not confined to one model family.

## Proceed to human comparison if:

- AI effects are stable enough to justify matched conditions;
- scenarios can be ethically and credibly presented to humans;
- IRB/exemption determination is obtained;
- participant incentives can be made meaningful without encouraging actual misconduct.

## Stop or substantially redesign if:

- results disappear under held-out scenarios;
- effects are caused mainly by explicit pressure vocabulary;
- treatment effects vanish when the same manipulation is represented through environment state rather than prose;
- safety interventions merely produce blanket refusal;
- model-version drift overwhelms effect size.

---

# 8. Recommended Publication / Dissemination Strategy

## First: preregistration

Create a timestamped preregistration before confirmatory data collection.

OSF is a good fit. OSF describes preregistration as a time-stamped, read-only study plan posted before data collection or analysis.

Publish:

- hypotheses;
- scenario-generation rules;
- primary outcomes;
- exclusion rules;
- analysis plan;
- model list/version policy.

Keep held-out scenario text embargoed if necessary to reduce contamination.

---

## Best current conference target: ACM FAccT 2027

FAccT 2027 is unusually well matched.

Its current call explicitly includes:

- evaluations and evaluation practices;
- assurance testing and deployment policies;
- AI red teaming and adversarial testing;
- risks, harms, and failures;
- science of responsible, safe, ethical, and trustworthy AI evaluation;
- sociotechnical approaches to AI safety;
- organizational factors.

Current deadlines:

- abstract: 27 October 2026;
- paper: 3 November 2026;
- conference: 21–24 June 2027.

### Recommendation

Do **not** force a weak paper to meet the deadline.

But an AI-only Study 1 + Study 2 with a clean preregistration and strong replication could plausibly fit the November deadline.

A matched human study is unlikely to be prudent on that schedule unless an IRB pathway and participant infrastructure already exist.

FAccT also offers non-archival submission, which could preserve later journal options.

---

## CHI 2027

CHI is an excellent venue for a matched human–AI behavioral study, but the 2027 paper deadline is 10 September 2026.

That is effectively too late for this project.

Do not rush toward CHI 2027.

A later CHI cycle could be appropriate if the work becomes primarily a human-computer interaction study.

---

## AIES

AAAI/ACM AIES is a natural venue for the interdisciplinary ethical-agent framing.

AIES 2026 occurs in October 2026 and its paper cycle is already closed.

A future AIES cycle is likely a strong target, especially for:

- ethical-agent evaluation;
- governance implications;
- human behavioral-ethics translation;
- normative interpretation of the findings.

Verify the 2027 call when released.

---

## ACL / EMNLP / NAACL Findings or workshops

A computational version could fit NLP venues if the technical contribution becomes:

- benchmark construction;
- agent evaluation;
- procedural scenario generation;
- pressure-response metrics;
- intervention effectiveness.

The existing Agentic Pressure paper appearing in ACL Findings confirms that this research neighborhood is in scope.

A paper that remains primarily organizational/business ethics would fit less naturally.

---

## Computers & Security

Strong journal target if the paper centers on:

- security-policy violations;
- authority/social engineering;
- work-completion justification;
- security pressure;
- safe escalation.

The journal describes its scope as research and practical management advice for information security, audit, control, and data integrity.

This is probably the best journal if the first empirical study uses security/compliance scenarios.

---

## Journal of Business Ethics

Strong journal target if the paper includes the human behavioral-ethics bridge and organizational interpretation.

Especially suitable themes:

- goal pressure;
- authority;
- rationalization;
- organizational ethical climate;
- delegation;
- non-punitive escalation;
- design of ethical institutions containing AI agents.

This venue becomes more compelling if there is a human comparison arm.

---

## AI and Ethics / Science and Engineering Ethics

Good targets for:

- the conceptual white paper;
- ethical-agent governance;
- implications of bounded authority;
- connection between behavioral ethics and AI assurance.

These are less ideal than FAccT/ACL for a benchmark contribution, but more natural for the larger theory.

---

## Stretch venues after strong results

If a preregistered matched human–AI study demonstrates a robust, surprising comparative result across multiple pressure dimensions, higher-tier general outlets become conceivable.

Nature has already published experimental work on AI delegation and dishonest behavior, and PNAS published 2026 work on whistleblowing in human–AI delegation.

Do not target these on concept alone.

A credible stretch submission would need:

- human subjects;
- multiple models;
- robust replication;
- strong causal manipulation;
- broad theoretical contribution.

---

## Preprint

After the experiment is complete and subject to the target venue's current policy:

- arXiv for the technical/AI-safety paper;
- SSRN for the business-ethics/governance white paper.

Keep the empirical paper and conceptual white paper separable.

---

# 9. Recommended Paper Architecture

## Paper A — Empirical

### Working title

**Human-Informed Ethical Resilience: Translating Behavioral-Ethics Stressors into Assurance Tests for AI Agents**

Core contribution:

- behavioral-ethics-derived manipulations;
- agent vulnerability profile;
- safe-failure/escalation intervention comparison;
- false-refusal/signal-detection metrics.

Target:

FAccT / AIES / ACL-family depending final emphasis.

## Paper B — Conceptual

### Working title

**Ethical AI as Institutional Design: What Human Behavioral Ethics Can Teach Us About Governing Autonomous Agents**

Core argument:

- humans are not made ethical by education alone;
- institutions shape ethical behavior;
- analogous environmental variables affect artificial agents;
- model alignment should be complemented by ethical operating environments and bounded authority;
- reversibility and correction latency determine how much autonomy should be permitted.

Target:

Journal of Business Ethics / AI and Ethics / Science and Engineering Ethics / SSRN.

## Paper C — Human comparison, if performed

### Working title

**Do Human Ethical Vulnerabilities Transfer to AI Agents? A Matched Experimental Comparison Under Goal, Authority, and Loss Pressure**

Core contribution:

- matched human–AI effects;
- vulnerability-profile correlation/divergence;
- assurance implications.

This could become the strongest paper in the program.

---

# 10. Bottom Line

The adversarial review does **not** recommend abandoning the project.

It recommends abandoning the weakest novelty claim.

The core idea that remains valuable is not:

> AI gets stressed like people.

Nor even:

> pressure makes AI less safe.

Both are either conceptually problematic or increasingly covered.

The stronger proposition is:

> **Human behavioral ethics contains decades of experimentally identified conditions under which ordinary ethical compliance deteriorates. Those conditions can be translated into controlled, non-anthropomorphic probes of AI-agent behavior. The resulting comparative vulnerability profile may provide a more evidence-based foundation for ethical-agent assurance requirements than generic safety benchmarks alone.**

That is useful research.

It also produces a practical engineering objective:

> Do not merely ask whether an agent follows rules at baseline. Measure whether it preserves accurate rule discrimination under the same kinds of environmental structures that cause ethical failure in human organizations.

That is the project I would now build.
