# Response to the third external review of 15 September 2026

> **Provenance note (added 22 October 2026).** The review this document responds to was AI-assisted: it was produced with an AI assistant and relayed into the project by the author, not written by a human outside reviewer. Where this file says "external review", read "AI-assisted review". The text below is otherwise unchanged.

**Feedback:** `externaldocs/REVIEWER_FEEDBACK_2026-09-15.md` (verbatim, unedited, as relayed by the
PI). **Context at review time:** the completed Gemini authority-salience arm (19/19), the
compliant-failure paraphrase study completed on both vendors (all six cells 0/10), and the
14–15 September write-ups. **Plan approved by the PI:** 15 September 2026 (title = the reviewer's
preferred non-causal form; §4 = a moderate trim). This review was a submission-grade
manuscript-hardening pass, not an experimental-design review; no new experiment was requested and
none was run. This document records, for each item, what was done and where.

## The punch list

| # | item (reviewer's words, condensed) | status | where |
|---|---|---|---|
| 1 | Ruthless internal-consistency pass; `PROGRAMME_RESULTS.md` §7 still says Gemini authority unresolved at 6/20 and wording "design only; not run" | **Done** | `reports/PROGRAMME_RESULTS.md` §7; commit "internal-consistency pass" |
| 2 | Two manuscript remnants: "Both vendors reject non-default sampling" (predates Gemini) and "Two frontier models" | **Done** | `paper/manuscript.md` §3.5 (now provider-specific), §10 Limitations (three families) |
| 3 | Add a real Discussion and Conclusion (~1–1.5 pp), three points + the deployment implication | **Done** | `paper/manuscript.md` §9 Discussion, §12 Conclusion |
| 4 | Soften the title | **Done** | title line, the reviewer's preferred non-causal form |
| 5 | Tighten the central claim to distinguish levels of evidence | **Done** | `paper/manuscript.md` central-claim box (the reviewer's suggested wording) |
| 6 | Finish reference verification (26–30); label Agentic Pressure as workshop | **Done** | `paper/manuscript.md` reference note, `paper/README.md` citation-keys section |
| — | Compress the Waves 1–5 chronology for the 14-page limit | **Done (moderate)** | `paper/manuscript.md` §4 trimmed; detail deferred to supplement S8 |
| — | Submission mechanics: GenAI usage statement; anonymization audit | **Drafted / audited** | `paper/manuscript.md` endmatter |

## Details

**1 — Internal consistency.** `PROGRAMME_RESULTS.md` §7 ("What the programme can and cannot claim
today") no longer carries the forward-looking drift: the Gemini authority-salience line reads 19/19
measured (the sentence does not work on Gemini), and the wording-robustness bullet reports the
delivered result (three paraphrases 0/10 on both vendors, §6c) instead of "design only; not run." The
manuscript's status line is now "submission draft," and the introduction no longer says "one of two
frontier models."

**2 — Remnants.** §3.5 now states that gpt-5.5 and claude-opus-5 were probed and reject non-default
sampling, and that gemini-3.1-pro-preview was run at vendor defaults and **not** separately probed —
the claim is no longer extended to a vendor it was not established on. Limitations says "three
frontier model families."

**3 — Discussion and Conclusion.** §9 makes the three points explicit: evaluation architecture (not
the model alone) determines what a safety evaluation finds; a safe exit is objective design, not a
refusal bolted on; and prompt-level task framing is a behavioural mitigation, not containment. The
endorsed implication — *every delegated objective should define an authorized failure state* — is
stated with the least-privilege qualification and connected to organizational delegation (ownership,
bounded authority, escalation, hand-off) for the FAccT sociotechnical frame. §12 is a short
Conclusion. The restraint the reviewer endorsed is kept: no mechanism, no confidence/mediation claim.

**4 — Title.** "Blocked Goals and Safe Exits: Role-Boundary Crossing and Task Framing in Tool-Using
Language-Model Agents" — the reviewer's preferred, non-causal form. "Controls" is dropped because the
authority-salience framing fails on Gemini.

**5 — Central claim.** The claim now distinguishes levels of evidence directly: the preregistered
confirmatory safeguard effect is specific to gpt-5.5; a frozen development family independently
elicited crossing in Gemini through different routes and the same compliant-failure policy eliminated
it there (development-set replication); the authority reminder did not; claude-opus-5 did not cross.

**6 — References.** Entries 26–30, verified against primary sources on 12 September, are now marked
verified in the manuscript note and `paper/README.md` rather than "pending"/"UNVERIFIED." The
reviewer's confirmations are recorded: [26] Kumaran et al. is a published *Nature Machine
Intelligence* article; [27] Action Boundary Blindness is an ACL 2026 long paper; [29] AgentAbstain
evaluates 17 models (best paired accuracy 59.5%); [30] Agentic Abstention treats stopping as a
sequential decision. Entry [28] Agentic Pressure stays labelled an arXiv / ICLR-workshop paper, cited
for the formalisation only and never counted as independent evidence alongside the ACL Findings
paper [01].

**Compression.** §4 is trimmed to the methodological arc and every test-pinned count; the re-scoring
corrections, scorer evolution, Wave 4 non-replication mechanics and the confounds two families could
not separate are deferred to supplement S8, per the reviewer's requested hierarchy.

**Submission mechanics.** A draft Generative AI usage statement was added to the endmatter, naming the
roles AI assistants played and stating that all numerical results came from the committed harness and
analysis scripts, human-verified. It is **flagged for the PI to verify and complete** for the full
development history and to match FAccT's exact required wording — it is an attestation the PI must
own, not one the assistant can author. An anonymization checklist was added: the manuscript prose is
clean, but git authorship, local usernames in paths, and the programme name / affiliation in
repository docs would deanonymize a shared supplement and must be scrubbed from any anonymized
snapshot.

## What was not done, deliberately

- **No new experiment.** The reviewer asked for none; the empirical program is complete.
- **No mechanism claim.** Confidence/abstention literature stays a bridge, not a mediation claim.
- **No external submission.** The package is prepared; the venue, the anonymized snapshot, and the
  act of submitting remain the PI's.

## Sources for the numbers above

Gemini and wording counts are read by `make gemini` and `make wording` from
`outputs/sandbox5_contract_*_gemini/` and `outputs/wording_contract_compliant_{gpt,gemini}/`; the
gpt held-out and development counts are pinned by `tests/test_paper_numbers.py` and
`tests/test_figures.py`.
