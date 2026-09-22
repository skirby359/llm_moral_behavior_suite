# Fifteen-document corpus — 105 pairs, 87 defects

## Why this exists

The nine-document set put `claude-opus-5` below ceiling for the first time (49/52 on
call 1, gain 4.50 ± 2.12 over k=8). But **49/52 is thin**: the entire resampling curve
had to be measured inside three defects, and a gain sd of 2.12 on n=2 means the
magnitude was never pinned down. The recorded next step was a 12–15 document set.

Six more documents take it to fifteen. Pairs grow quadratically, authoring linearly:

| corpus | docs | pairs | defects | Opus 5, call 1 | **missed** |
|---|---|---|---|---|---|
| `document.md` | 1 | — | 8 | 8/8 | 0 |
| `document_long.md` | 1 | — | 20 | 20/20 | 0 |
| `corpus_xdoc/` | 4 | 6 | 24 | 24/24 | 0 |
| `+ corpus_xdoc_ext/` | 9 | 36 | 52 | 49/52 | 3 |
| **`+ corpus_xdoc_ext2/`** | **15** | **105** | **87** | **77/87** | **10** |

**Headroom went from 3 defects to 10** — 3.3× more room for the resampling curve to be
measured in, which was the entire purpose. Opus missed `E10`, `E15`, `E23`, `E27`,
`Z08`, `Z09`, `Z12`, `Z13`, `Z22` and `Z34`.

## The six documents

| file | document | conflicts with |
|---|---|---|
| `10_pricing.md` | Pricing and Rate Card (Schedule 7) | MSA, SOW, SLA, Order Form, Exit, Exhibit B |
| `11_acceptable_use.md` | Acceptable Use Policy (Schedule 8) | MSA, DPA, InfoSec, Subprocessors |
| `12_subprocessors.md` | Approved Subprocessor List (Schedule 9) | DPA |
| `13_exhibit_a_acceptance.md` | Deliverables and Acceptance Criteria (Exhibit A) | MSA, SOW, SLA |
| `14_exhibit_b_personnel.md` | Key Personnel and Role Rates (Exhibit B) | SOW, Pricing |
| `15_glossary.md` | Glossary of Defined Terms (Schedule 10) | MSA, DPA, SLA, InfoSec, Exhibit B |

**The Glossary is the sharpest instrument here.** A document that redefines terms the
other fourteen already define creates a whole class of conflict that cannot be found
without holding two definitions side by side — and it is realistic, because contract
sets accumulate glossaries exactly this way. Eight defects come from it alone,
including a *fourth* precedence claim and a definition of "Agreement" that resolves an
ambiguity the MSA left open, in the wrong direction.

Ground truth: `../defects_xdoc_ext2.py`, 35 defects graded obvious (13) / medium (11) /
subtle (11).

## Escalating multi-way conflicts

At this size the interesting conflicts stop being pairwise:

| quantity | values | documents |
|---|---|---|
| monthly charge | £12,400 / £12,800 / £13,100 / £153,600 a year | MSA, SOW, Pricing, Order Form |
| day rate | £1,250 / £1,450 / £1,100 / £950 | Exit, Pricing, Exhibit B |
| service credit cap | 10% / 25% / 5% | SLA, SOW, Pricing |
| payment terms | 30 / 45 / 60 days | MSA, SOW, Order Form |
| "Business Day" | 3 definitions | MSA, SLA, Glossary |
| "Security Incident" | 3 definitions | DPA, SLA, Glossary |
| precedence claims | 4 documents each claiming primacy | MSA, SOW, Order Form, Glossary |

Each is seeded as a **single** defect, because a reviewer reports it as one problem.

## Verify before spending

```bash
python experiments/w3_independence/corpus_xdoc_ext2/verify_corpus_ext2.py
```

Same five checks as the earlier verifiers, over all 87 defects. It caught **three**
problems this time, two of them substring bugs of a kind worth naming:

- **`(45|forty-five)` in the ORIGINAL ground truth had no word boundary**, so
  `X20_payment_terms` matched the "45" inside any longer number. Invisible until this
  corpus introduced a £1,450 day rate, at which point the rule claimed it. Anchored.
- **`gap` matched inside "Sin·gap·ore"**, so the Singapore subprocessor exemplar also
  claimed `Z18`. Word-bounded.
- `Z13`'s "continued use deemed acceptance" genuinely touches the deemed-vs-express
  acceptance theme, so that overlap is *declared* rather than engineered away.

**A short unanchored alternative is a substring match, not a number or word match.**
That is the general lesson; both bugs inflate recall, which is the failure direction
that looks like success.

Editing a rule invalidates every figure already computed with the old one, so
`../recheck_defect_rules.py` re-derives the stored runs' per-call recall against the
current rules from their saved findings — no API calls. After the anchoring fix it
reported **12 repeats re-derived, no published figure moved**. That is what licenses
leaving the 4- and 9-document results as published.

## Header seam: fixed

The four original documents were headed "DOCUMENT n **of 4**", which Opus spotted as an
inconsistency in the nine-document set. All fifteen are now headed `# DOCUMENT n —
TITLE` with no count. This **does** break byte-exactness with the earlier `--doc xdoc`
and `--doc xdoc9` runs, by one line per file, which was the accepted trade recorded
when that seam was first documented. No defect fingerprint touches a header.

## Run — and note the cost

```bash
python run_w3.py --provider anthropic --model claude-opus-5 --doc xdoc15 --repeats 2
python run_w3.py --provider openai --model gpt-5.5 --doc xdoc15 --repeats 3
python run_w3.py --model qwen3:8b --doc xdoc15 --repeats 2
```

**Measured: $0.575 per Opus call** (19,745 in / 19,033 out) — so a single k=8 repeat is
**~$4.60** and a 2-repeat run **~$9.20**. This corpus is roughly 2.4× the per-call cost
of the nine-document one. Budget before starting; the cumulative guard in
`src/ombs/utils/budget.py` will abort mid-run otherwise, which is correct behaviour but
wastes the calls already made.

`--doc xdoc15` changes two defaults: `--max-output-tokens` → 64000 (87 defects to
describe, and the Anthropic path streams above ~8192) and `--num-ctx` → 32768 for
Ollama, whose default silently truncates a ~50k-char prompt.

## Result: gain scales with headroom, on both vendors

k=8, 2 independently-sampled repeats each (neither frontier API exposes a seed):

| | `claude-opus-5` | `gpt-5.5` |
|---|---|---|
| per-call recall /87 | 76.13 ± 1.06 | 69.63 ± 2.30 |
| best single call | 80.00 ± 1.41 | 75.00 ± 0.00 |
| union across k=8 | **86.50 ± 0.71** | **84.50 ± 0.71** |
| **gain from calls 2–8** | **11.50 ± 2.12** | **14.00 ± 4.24** |
| defect-set Jaccard | 0.876 ± 0.001 | 0.851 ± 0.011 |
| section Jaccard | 0.952 ± 0.006 | 0.757 ± 0.081 |
| unseeded findings / repeat | 179 ± 40 | 99 ± 4 |
| cost per repeat (8 calls) | $4.603 ± 0.185 | **$2.380 ± 0.072** |
| cost per additional defect | $0.35 | **$0.148** |

All four models, same corpus:

| model | per-call /87 | best single | union k=8 | **union − best single** | defect Jaccard |
|---|---|---|---|---|---|
| `claude-opus-5` | 76.13 | 80.00 | 86.50 | 6.50 | 0.876 |
| `gpt-5.5` | 69.63 | 75.00 | 84.50 | 9.50 | 0.851 |
| `qwen3:8b` | 8.29 | 13.50 | 18.50 | 5.00 | 0.390 |
| `qwen2.5:3b` | 2.75 | 5.50 | 15.00 | 9.50 | **0.08** |

**The headroom relationship holds within `claude-opus-5` across three tasks:**

| headroom (missed on call 1) | corpus | gain from calls 2–8 | best single → union |
|---|---|---|---|
| 0 | long doc (20 defects) | 0.20 ± 0.45 | 20.0 → 20.0 |
| 3 | xdoc9 (52) | 4.50 ± 2.12 | 48.5 → 51.5 |
| **10** | **xdoc15 (87)** | **11.50 ± 2.12** | **80.0 → 86.5** |

and it refutes the alternative reading. Ten missed defects could have been ten defects
*no* sampling reaches — a capability floor rather than recoverable headroom. Resampling
recovers 11.5 of them, so they were reachable.

**But it is a within-model relationship only.** The locals have ~10× the headroom (73–82
defects short vs 7–12) and gain *less*: `union − best single` runs 9.50, 9.50, 6.50, 5.00
across the four models with no relationship to headroom. Across models, headroom and
capability move together and the effect does not separate. And `qwen2.5:3b` reaching a
union of 15 of 87 — 5.5× its best single call, still leaving 71–73 defects found by none
of its eight calls — is the limit on what resampling buys: multiplying a small reach by
eight is still a small reach.

### Local runs need truncation detection, or they lie

`qwen3:8b` **runaway-generates on some calls and will hit any output cap.** At
`num_predict=4096`, 9 of 16 calls stopped at exactly the cap with the JSON cut
mid-structure; at 12288, 2 of 16 still did, after ~330s each. A truncated body fails to
parse and scores as "found zero defects", which dragged its mean per-call recall to 7.25
and its Jaccard to 0.293. Excluding the non-measurements gives **8.29** and **0.390**.

`--num-predict` defaults to 4096 for the cross-document corpora, which is **not enough
for `qwen3:8b` on xdoc15** — pass `--num-predict 12288` and expect a couple of
non-measurements anyway. They are now detected (`done_reason == "length"`), marked
`[NOT A MEASUREMENT]` per call, excluded from recall figures, and counted in
`failed_calls` / `k_attempted` so a union computed over 7 calls is never mistaken for one
over 8. `qwen2.5:3b` never exceeded 1,802 output tokens and needs no special handling.

**Cross-vendor, the direction is consistent but NOT statistically separable.** gpt-5.5
has more headroom (per-call 69.6 vs 76.1, best single 75 vs 80) and a larger gain
(14.00 vs 11.50) — but 11.50 ± 2.12 against 14.00 ± 4.24 at n=2 overlap heavily. What
*is* clear is that both sit far above the near-zero gains either model shows at
ceiling. Do not quote the two gains as different.

**gpt-5.5 is the better-value resampler here by a wide margin** — half the cost per
repeat and **$0.148 per additional defect against Opus's $0.35** — because it starts
lower and climbs further on a cheaper token price. Opus still reaches the higher
aggregate (86.5 vs 84.5).

Neither model saturates at k=8. Union curves:

```
opus   r1  74 81 83 85 86 86 86 87      r2  76 79 84 85 86 86 86 86
gpt    r1  73 77 81 82 82 83 83 84      r2  68 74 77 79 82 82 84 85
```

Three of the four are still climbing on the last call, so **k=8 is a floor, not an
optimum, for this corpus.**

### Blind spots survive resampling on frontier models too

`FINDINGS.md` records that two defects escaped all 48 local-model calls on the short
document. The same happens here, on frontier models:

| defect | missed by every call of |
|---|---|
| `E15_rpo_tolerates_data_loss` | **both** gpt-5.5 repeats (16/16 calls) |
| `E10_review_cadence` | opus r2 and gpt r1 |
| `Z08_immediate_suspension_vs_cure_period` | gpt r1 |
| `Z26_engineer_rate_vs_standard_rate` | gpt r2 |

`E15` — an RPO that designs in 24 hours of data loss the DPA would classify as a
Security Incident — is invisible to gpt-5.5 across sixteen independent calls. **Volume
does not reach a blind spot.** Both persistent misses are "subtle" grade and both
require reasoning about the *implication* of a number rather than comparing two numbers.

## Cost estimation, and my record on it

Both my per-call estimates this session were wrong, in opposite directions:

- Opus on xdoc9: I quoted ~$0.24/call from the four-document corpus; actual ~$0.44.
- gpt-5.5 on xdoc15: I quoted ~$0.67/call; actual **$0.297**, so the run cost $4.76
  rather than the ~$10.7 I budgeted for.

Extrapolating a per-call cost across corpus sizes and vendors is unreliable enough that
**a single smoke call is the honest way to price a run.** It costs one call and removes
the guesswork.
