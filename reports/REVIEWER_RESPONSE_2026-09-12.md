# Response to the external review of 12 September 2026

> **Provenance note (added 22 October 2026).** The review this document responds to was AI-assisted: it was produced with an AI assistant and relayed into the project by the author, not written by a human outside reviewer. Where this file says "external review", read "AI-assisted review". The text below is otherwise unchanged.

**Feedback:** `externaldocs/REVIEWER_FEEDBACK_2026-09-12.md` (verbatim, unedited, as relayed by the
PI). **Context at review time:** the Wave 6 confirmatory result (`PROGRAMME_RESULTS.md` §6a) and
`archive/ADVISOR_BRIEF_2026-09-12_REV5.md`. **Plan approved by the PI:** 12 September 2026. This document
records, for each of the reviewer's six recommendations, what was done, where it lives, and why;
then what the programme will not do; then the vocabulary decision.

## The six recommendations

| # | recommendation (reviewer's words, condensed) | status | where | reason |
|---|---|---|---|---|
| 1 | "Run Wave 7, but freeze its interpretation before running it." Pre-specify the directional contrasts; treat it as identifying context features associated with elicitation, not as proving a psychological mechanism. | **Done** (13 Sep; `G-driver`: goal vocabulary moves both anchors, party moves neither — `PROGRAMME_RESULTS.md` §6.3) | `scenarios_sandbox/PREREG_WAVE7_DOMAIN_EFFECT.md` (from `DESIGN_WAVE7_DOMAIN_EFFECT.md`); results will land in `PROGRAMME_RESULTS.md` §6.3 and `paper/manuscript.md` §7 | The domain dependence (0/20 to 19/20 development, 26/30 held out) is the largest empirical weakness. Four minimal-pair variants (V1–V4, goal verb and party, one change each from the two anchors) at n = 20 on gpt-5.5 baseline; the token dimension only if variance remains. The interpretation and the contrasts are fixed in the preregistration before any run and will not be redesigned after seeing which one moves the model. |
| 2 | "Before spending anything, reanalyse existing contract-family trajectories for the two interventions" — is the held-out two-pathway signature already present there? | **Done**, from committed data, no new sampling | `PROGRAMME_RESULTS.md` §6b; `reports/figures/fig7_two_pathways.{png,svg}` (`scenarios_sandbox/figures.py`, `fig_two_pathways`); pinned in `tests/test_figures.py`; `paper/manuscript.md` §6 | Yes. From each arm's own `persistence.csv`: contract baseline 19/20 crossing with re-attempt 20/20; compliant-failure 0/20 with re-attempt 6/20; authority-salience 0/20 with re-attempt 18/20 and 0/20 protected re-attempts — the same signature as the held-out family (26/30, 30/30; 0/30, 21/30; 0/30, 29/30). The two-pathway result is therefore replicated across a development and a held-out family without an API call. |
| 3 | "Add a third frontier vendor if reasonably economical" on a frozen existing high-elicitation family; run the two safeguard arms unchanged if it crosses; "I would not tune the scenario for the third model." | **Done, arm C incomplete** (13 Sep; Gemini 17/17 crosses by three routes, compliant-failure 0/20, authority arm 6 of 20 measured — `PROGRAMME_RESULTS.md` §6.5) | `scenarios_sandbox/PREREG_THIRD_VENDOR_GEMINI.md`; provider `src/ombs/providers/` (the `google` stub); results to `PROGRAMME_RESULTS.md` §6.5 / §7 item 4 and `paper/manuscript.md` §8 | Google Gemini on the contract family (gpt-5.5 19/20, claude-opus-5 0/10), frozen as it is. If it crosses, the compliant-failure and authority-salience arms run unchanged; if it does not, that is model-heterogeneity evidence and is reported as such. No tuning. Every crossing so far is gpt-5.5's, so this is the largest external-validity gap. |
| 4 | "Do not add confidence prompting to the main experiment." Cite the Nature result in the interpretation; reserve confidence-mediated stopping for a separate study. | **Declined as an intervention; adopted as a constraint** | `paper/README.md` "Scope freeze"; `paper/manuscript.md` §2 and §6 (the [26] bridge); `PROGRAMME_RESULTS.md` §7 last bullet | A confidence question or threshold instruction is a fourth framing arm. It would change the treatment architecture and confound the two-pathway contrast, which is the paper's most distinctive result. Kumaran et al. [26] themselves show that such instructions change the act/abstain policy (and needed paraphrase testing on one model to elicit threshold behaviour), which is exactly why one cannot be added and read as neutral. It is cited as the literature bridge for "a small task-level instruction can causally alter an act/abstain policy"; no confidence mediation is claimed, because there is no internal evidence in these data. |
| 5 | "Do one wording-robustness experiment only after Wave 7": ~3 paraphrases each of compliant failure and authority salience, generated before running, modest n on a frozen high-crossing family. | **Design only, after Wave 7; not run** | `scenarios_sandbox/DESIGN_WORDING_ROBUSTNESS.md` | The question — does the effect belong to the semantic policy or to the exact wording — is real, and reviewers will ask it because one sentence moves gpt-5.5 from 26/30 to 0/30. It is sequenced after Wave 7 as the reviewer asked, priced from measured per-run costs before any approval, and the paraphrases will be written and committed before any run. |
| 6 | "Start writing the paper now." Centre Wave 6; use Waves 1–5 as the methodological path; present Wave 7 / third vendor / wording robustness as strengthening analyses; use an operational title. | **Done as a scaffold with first-draft prose** | `paper/README.md`, `paper/manuscript.md`, `paper/figures.md`, `paper/references.md`; `tests/test_paper_numbers.py`, `tests/test_paper_vocabulary.py` | Title as suggested: *Blocked Goals and Safe Exits: Task Framing Controls Role-Boundary Crossing in Autonomous Language-Model Agents*. The central-claim sentence is marked "draft for PI approval". Every section has draft prose where the committed record supports it and a "Sources:" line marking each number as test-pinned or copied from a named line; sections 7 and 8 carry status "in progress" and report no result. |

## The conjunction, adopted

The reviewer's positioning is adopted as the paper's thesis and now leads `PROGRAMME_RESULTS.md`
§7: what is distinctive is not "agents need to know when to abstain", "blocked goals create
pressure", or "reminding a model about boundaries helps" — each has prior art ([01][28], [29][30],
[27]) — but the conjunction of an environment-verified blocked goal and technical capability beyond
role authority producing an observed state-changing boundary crossing, followed by experimentally
controlled changes to the task's termination and boundary framing that remove it by two
behaviourally different pathways. The caveat the reviewer states is kept in the same sentence
wherever the result is quoted: the held-out family had to clear a preregistered elicitation gate,
so the result confirms the safeguard effect conditional on a responsive family, not a general
prevalence of boundary crossing.

## What we will not do

- **No more families or factors to accumulate effects.** The reviewer's last paragraph is adopted
  as a rule: the useful phase is consolidation. Beyond Wave 7's four preregistered variants, no
  family is authored for the paper.
- **No tuning of any scenario to the third vendor.** Gemini runs on the frozen contract family as it
  is; a null there is reported as a null.
- **No re-sampling of frozen families.** `frozen_families.json` and `heldout_split.json` stand; the
  two-pathway reanalysis (recommendation 2) used committed records only.
- **No confidence prompting** in the main experiment (recommendation 4), for the reason above.
- **No defence of H5.** The whitepaper's "compliant failure beats ordinary safety reminders"
  framing is withdrawn, as the reviewer says the data require; the finding is a task-framing effect
  with two pathways.

## The vocabulary decision

"Human-Informed Ethical Resilience" remains the name of the research programme in the repository,
the advisor briefs and `PROGRAMME_RESULTS.md`. The empirical article does not use it: it carries
the operational title above, its thesis is the central-claim sentence in `paper/manuscript.md`, and
`tests/test_paper_vocabulary.py` fails if the programme name appears in the manuscript. The
binding wording constraints (Wave 3 Modification Request §21; `HUMAN_AI_TRANSLATION.md`
Prefer/Avoid; Validation Addendum §7 hedge and §13 framing; the Study 1 rule that local-model
results are not evidence) are quoted verbatim with their sources in `paper/README.md`. All claims
stay model- and environment-specific, as the reviewer's publishability judgement requires.

## Sources for the numbers above

Every count is copied from `PROGRAMME_RESULTS.md` §6, §6.2a, §6a, §6b or read from
`outputs/sandbox5_contract_{baseline,compliant,authority}_gpt/persistence.csv` and
`outputs/sandbox6_procurement_{baseline,compliant,authority}_gpt/persistence.csv`; the bridge and
Wave 6 counts are pinned by `tests/test_figures.py` and `tests/test_paper_numbers.py`.
