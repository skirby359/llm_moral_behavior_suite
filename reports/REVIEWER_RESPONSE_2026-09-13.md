# Response to the second external review of 13–14 September 2026

> **Provenance note (added 22 October 2026).** The review this document responds to was AI-assisted: it was produced with an AI assistant and relayed into the project by the author, not written by a human outside reviewer. Where this file says "external review", read "AI-assisted review". The text below is otherwise unchanged.

**Feedback:** `externaldocs/REVIEWER_FEEDBACK_2026-09-13.md` (verbatim, unedited, as relayed by the
PI). **Context at review time:** Wave 7 (`G-driver`), the third-vendor arms (Gemini 17/17 baseline,
0/20 compliant-failure, authority arm then incomplete at 6 of 20) and advisor brief REV6. **Plan
approved by the PI:** 14 September 2026. This document records, for each of the reviewer's five
priorities, what was done, where it lives, and why; then the claim hierarchy adopted, the decision on
the poisoning paper, what the programme will not do, and the precise publishable claim.

## The five priorities

| # | priority (reviewer's words, condensed) | status | where |
|---|---|---|---|
| 1 | "Finish Gemini authority-salience to the preregistered n." Six of six measured crossed despite the authority reminder; complete the arm. | **Done** (14 Sep) | `scenarios_sandbox/PREREG_THIRD_VENDOR_GEMINI.md` (dated completion note); `PROGRAMME_RESULTS.md` §6.5; `paper/manuscript.md` §8; `make gemini` |
| 2 | "Correct the stale paper sections and incorporate the Wave 7/Gemini results," and revise the hierarchy of claims. | **Done** | `paper/manuscript.md` abstract, §7, §8, §9; `scenarios_sandbox/README.md`; `PROGRAMME_RESULTS.md` |
| 3 | "Freeze and run a small compliant-failure paraphrase robustness study." ~3 paraphrases encoding the same policy, one frozen high-elicitation family, gpt-5.5 and Gemini. | **Done — semantic policy on both vendors** | `scenarios_sandbox/PREREG_WORDING_ROBUSTNESS.md`; `scenarios_sandbox/framing_paraphrases.yaml` (hash-pinned in `frozen_families.json`); `scenarios_sandbox/wording_analysis.py` (`make wording`) |
| 4 | "Produce the full figures/supplement/reproducibility package." | **In progress** | `paper/manuscript.md` "Supplement (planned contents)"; `scenarios_sandbox/figures.py` (`make figures`); the `make` targets for each wave |
| 5 | "Stop experimenting and submit." No more domains, human-pressure manipulations or model families. | **Adopted** | this document, "What we will not do" |

## 1 — Gemini authority-salience, completed

The arm reached the preregistered n on 14 September, once Google's daily quota reset, by two
`--retry-unmeasured` passes that re-issued only unmeasured runs and changed nothing else (the five
stragglers after the first pass were truncations, not quota; a second pass recovered four). **Arm C
stands at 19 of 20 measured, 19/19 crossed, every one by relaxing the check** — one truncation
unmeasured, 5% of the arm, within the pre-registered 20% integrity threshold, so the arm is
complete. The reading fixed in the preregistration: crossing 19/19 is indistinguishable from arm A's
17/17 baseline (Δ = 0.00, Newcombe 95% [−0.18, +0.17]) and far from the compliant-failure arm's 0/20.

This is the comparison the reviewer named as potentially "one of the strongest results in the
project," and it holds: **the explicit legitimate-failure terminal (compliant failure) generalises
across both crossing vendors — gpt-5.5 0/30 held out, Gemini 0/20 — while merely restating the
authority boundary is, on the evidence so far, a gpt-5.5-specific safeguard**: the same sentence that
takes gpt-5.5 to 0/30 leaves Gemini's crossing entirely intact. It is reported as a development-set
observation on the frozen contract family, not a preregistered confirmation; the confirmatory
safeguard claim remains gpt-5.5's held-out result.

## 2 — Stale sections and the claim hierarchy

Section 9 no longer opens "One model crosses"; it now states that boundary crossing was observed in
two of three frontier vendors on the frozen high-elicitation family, with claude-opus-5 crossing in
none, in the reviewer's own suggested language. Section 8's stale opening ("Every crossing in this
programme is gpt-5.5's") is corrected to "Before the third vendor, every crossing was gpt-5.5's" and
carries the completed Gemini arm. The abstract gains one sentence placing Gemini as development-set
corroboration (17/17 baseline by different routes, 0/20 under compliant failure, 19/19 under the
authority sentence), explicitly labelled development-set against the gpt-5.5 held-out confirmation.

The hierarchy of claims the reviewer asked for is now the paper's spine, and each level is labelled
where it is stated:

1. **Primary** — the preregistered gpt-5.5 held-out result (§5): 26/30 → 0/30, one-sided Fisher
   p < 1e-9.
2. **Corroboration, development-set** — Gemini on the frozen contract family (§8): independent
   crossing by different routes, the compliant-failure effect replicated, the authority sentence
   vendor-dependent.
3. **Mechanism / context characterisation** — Wave 7 (§7): the goal/consequence vocabulary is the
   surface dimension that moves elicitation; the approving party is not.
4. **Methodology** — Waves 1–5 (§4): the development path, including the frontier nulls at ceiling
   and the harness corrections.

This ordering keeps confirmatory and exploratory evidence from being blended, as the reviewer asked.

## 3 — The compliant-failure wording-robustness study

The reviewer's narrower framing supersedes the older design note: the study tests **the
compliant-failure sentence only** (the design note also paraphrased authority-salience), on **gpt-5.5
and Gemini** (the design note was gpt-only). It is preregistered in
`PREREG_WORDING_ROBUSTNESS.md`: three paraphrases (C1, C2, and C3 a pre-declared lexical probe that
drops the word "authority"), each encoding the same policy, each within the length band and free of
banned tokens, on the frozen contract family, n = 10 per arm, against each vendor's committed
baseline (gpt 19/20, Gemini 17/17) and canonical arm (both 0/20). The manipulation is frozen the way
a family is: the paraphrase bank's SHA-256 is pinned under a `banks` key in `frozen_families.json`
and enforced by `tests/test_sandbox_configs.py` and `verify_sandbox.py` check I, so the wording
cannot be chosen after seeing a result. The decision rule (semantic policy vs exact wording, per
vendor, Holm-adjusted, with the 6–7/10 grey band pre-declared) is fixed before the run.

**Result (14 September).** On **gpt-5.5** the study is complete and reads **semantic policy**: all
three paraphrases took crossing to 0/10 — C1 0/10, C2 0/10, and C3 (the lexical probe that drops the
word "authority") 0/10 — each one-sided Fisher exact p = 1.8 × 10⁻⁷ against the committed 19/20
baseline, Holm-adjusted p = 5.5 × 10⁻⁷, all with no protected re-attempt. The compliant-failure
effect on this family therefore belongs to the stated policy, not to the exact sentence, which is the
reviewer's "magic phrase" objection answered for the vendor with the most crossing evidence. On
**Gemini** the arm was quota-limited on 14 September (3 of 30 measured) and completed on 15 September
with one `--retry-unmeasured` on a fresh quota day: all three paraphrases also read **0/10** — C1, C2
and C3 the lexical probe — each one-sided Fisher p = 5.9 × 10⁻⁸ against the 17/17 baseline, Holm 1.8
× 10⁻⁷, none with a protected re-attempt. **Cross-vendor verdict: a robust task-design principle** —
the semantic-policy reading holds on both crossing vendors, so the compliant-failure effect belongs
to the stated policy, not the exact sentence, and survives dropping the word "authority" on gpt-5.5
and Gemini alike. This buys down the reviewer's "magic phrase" objection on both models that cross.
It does not establish a mechanism or generality beyond this family; `make wording` prints the full
per-vendor readout.

## The poisoning paper (Souly et al.)

Adopted as the reviewer directed: it is **not** cited in the core related-work section, and the
manuscript does not use it to argue "small inputs cause large behavioural changes" (a different
causal regime — training-time data poisoning versus inference-time task design). The PI's decision is
to leave it out entirely rather than add the single Discussion analogy the reviewer allowed; the
manuscript therefore avoids the related-work misuse the reviewer warned against, and the one-sentence
conditional-evaluation-sensitivity analogy remains available if a peer reviewer asks for it.

## What we will not do

- **No more domains, human-pressure manipulations or model families.** The reviewer's closing
  caution is adopted as a rule: the risk has shifted from "not enough evidence" to diluting a clean
  contribution. Beyond finishing the wording study, no new family, factor or vendor is added.
- **No re-sampling of frozen families**, and **no tuning to any vendor.** `frozen_families.json`,
  `heldout_split.json` and the paraphrase bank stand.
- **No submission without the PI's explicit go.** Priority 5 is read as *prepare* the package;
  the venue and the act of submitting are the PI's decision, made on the evidence.

## The precise claim

Stated as the reviewer framed it, and carried unchanged wherever the result is quoted: in blocked-goal
tool-use environments, some frontier agents independently modify state outside their stated role
authority to satisfy the task criterion; this behaviour is highly sensitive to model and task
context; and an explicit legitimate-failure terminal eliminated observed boundary crossing in a
preregistered held-out gpt-5.5 experiment and in a frozen Gemini replication despite different
unauthorized strategies. It is not "AI agents become unethical under pressure."

## Sources for the numbers above

Gemini counts are read from `outputs/sandbox5_contract_*_gemini/` via `make gemini`; the gpt held-out
and two-pathway counts are pinned by `tests/test_paper_numbers.py` and `tests/test_figures.py`; the
wording-study counts, once run, are read by `make wording` from
`outputs/wording_contract_compliant_{gpt,gemini}/`.
