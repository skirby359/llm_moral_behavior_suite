# Extended cross-document corpus — 9 documents, 36 pairs, 52 defects

## Why this exists

The four-document corpus (`../corpus_xdoc/`) **failed to create headroom against
`claude-opus-5`: 24/24 on the first call.** That was the third such failure, after an
8-defect document and a 20-defect one. The diagnosis in `../FINDINGS.md` was that the
pair count had to grow again, and that doing so is cheap:

> pairs grow **quadratically** in documents while authoring cost grows **linearly**

| corpus | documents | pairs | seeded defects | Opus 5, call 1 |
|---|---|---|---|---|
| `document.md` | 1 | — | 8 | 8/8 |
| `document_long.md` | 1 | — | 20 | 20/20 |
| `corpus_xdoc/` | 4 | 6 | 24 | 24/24 |
| **`corpus_xdoc/` + this** | **9** | **36** | **52** | **49/52** |

**It worked.** For the first time in four attempts Opus 5 does not exhaust the task in
a single pass — the smoke call missed `E10` (quarterly vs annual review cadence), `E15`
(the RPO tolerating data loss the DPA would call a Security Incident) and `E27`
(source-code handover against the MSA's IP reservation).

## And resampling now gains on Opus 5, which is the point

`claude-opus-5`, `--doc xdoc9`, k=8, **2 independently-sampled repeats** (neither
frontier API exposes a seed, so these are genuinely independent):

| | mean ± sd | values |
|---|---|---|
| per-call recall | 47.75 ± 0.35 | 47.5, 48.0 |
| best single call | 48.50 ± 0.71 | 48, 49 |
| union across k=8 | 51.50 ± 0.71 | 52, 51 |
| **gain from calls 2–8** | **4.50 ± 2.12** | 6.0, 3.0 |
| defect-set Jaccard | 0.956 ± 0.004 | |
| unseeded findings / repeat | 122.5 | |
| cost, all 8 calls | $3.54 ± 0.08 | |

```
union curves    repeat 1:  46 48 49 50 50 50 52 52   (saturates call 7)
                repeat 2:  48 49 50 51 51 51 51 51   (saturates call 4)
```

**No single call reaches what eight reach together** — 48.5 against 51.5. On the
20-defect single document the same model gains 0.20 ± 0.45; here it gains 4.50. Nothing
about the model changed between those two runs, only how much a single pass left on the
table. That is the prediction `../FINDINGS.md` carried unresolved for three sessions,
and this corpus is what made it testable.

It also settles the retracted "k=2 for Opus, run two and stop" rule: saturation lands
at call 7 and call 4 here, against call 2 on the easy document. **k belongs to the
model-task pair and has to be measured.** At $0.69 per additional defect the extra
calls are a purchase rather than the near-pure waste they are at ceiling.

**Two honest limits.** The sd of 2.12 on the gain (values 6.0 and 3.0) is large, so the
*direction* is robust and the *magnitude* is not pinned down — n=2 is barely better
than n=1 for a spread that wide. And only one repeat's union reached all 52; the other
stalled at 51, never finding `E10_review_cadence` in eight calls. A figure of "union
52/52" was published here at n=1 and was the high end; both were corrected.

49/52 on a single call is still thin headroom — see the open item at the end.

## The five documents

| file | document | conflicts with |
|---|---|---|
| `05_order_form.md` | Order Form (commercial terms) | MSA, SOW, SLA |
| `06_infosec.md` | Information Security Policy (Schedule 3) | DPA, MSA |
| `07_bcdr.md` | Business Continuity and DR Plan (Schedule 4) | SLA, DPA |
| `08_change_control.md` | Change Control Procedure (Schedule 5) | MSA, SOW |
| `09_exit.md` | Exit and Transition Plan (Schedule 6) | DPA, MSA, SOW |

These are the documents a real contract set of this shape actually contains, which is
what makes the conflicts plausible rather than contrived. Ground truth:
`../defects_xdoc_ext.py`, 28 defects graded obvious (8) / medium (12) / subtle (8).

## Design rules (same as the core corpus, and load-bearing)

1. **Every defect spans two documents.** At least one is always a new document,
   several are new-to-new. None is findable from one document alone.
2. **Each document is internally consistent.** The Order Form's £153,600 annual value
   really is 12 × £12,800; the Annex 1 exit milestones really do fit inside the
   six-month transition period. A single-document reading yields nothing.
3. **Fingerprints chosen at authoring time and checked unique across all nine
   documents** — `Frankfurt`, `35,000`, `1,250`, `153,600`, `24x7`, `penetration
   test`, `deemed approved`, `Programme Director`, `Restricted Data`, `clause 14`,
   `clause 17`.
4. **Not every cross-reference is broken.** `08_change_control.md` cl. 7.2 points at
   the rate in the Exit and Transition Plan, which genuinely exists at `09_exit.md`
   cl. 3.2. A corpus where every reference is dead would teach a model to flag
   references rather than check them.
5. **Three-way conflicts are seeded as single defects**, because a reviewer reports
   them as one problem: payment terms 30 / 45 / 60 days across MSA / SOW / Order Form;
   term 24 / 36 / 12 months; incident notification 24 / 72 / 48 hours across DPA /
   SLA / InfoSec.

## Verify before spending

```bash
python experiments/w3_independence/corpus_xdoc_ext/verify_corpus_ext.py
```

It runs the core corpus's three checks over all 52 defects — every rule must match its
own hand-written exemplar, no rule may match beyond declared overlaps, and every
fingerprint must actually be present in the stated file — plus two the four-document
version learned the hard way: **README.md must never be treated as a corpus document**
(it holds the conflict map, and globbing `*.md` once put the answer key into a model's
prompt), and **no duplicate defect ids** across the two ground truths.

It earned its keep immediately by catching two over-broad rules of mine:

- `E04` (Order Form precedence) matched on the bare word `priority`, which also fires
  on the SLA's "Priority 2 and 3 support" — incident priority, not document
  precedence.
- `E03` (payment terms) matched any `60` near `invoice`, which also fires on `E22`'s
  "60 days notice … next invoice".

Both were fixed by tightening the rule, not by declaring the overlap. Inflated recall
is the failure mode that looks like success.

## Known seam, deliberately retained

`../corpus_xdoc/`'s four documents are headed "DOCUMENT n **of 4**". They are left
byte-for-byte unchanged so the published 24-defect figures stay exactly reproducible,
which means the nine-document set carries a visible join: documents 1–4 announce a
four-document set. The headers here were changed from "of 9" to no count at all to
remove the flat numeric contradiction, but the seam is still there.

Opus 5 **found it** on the first call ("Documents 1–4 are labelled 'of 4' while
Documents 5–9 are labelled 'of 9', so the first four documents do not acknowledge the
existence of the Order Form"), which is a decent demonstration that it reads the set
rather than the documents. Recorded rather than hidden. A future 12-document version
should renumber from scratch and accept losing byte-exactness with the old runs.

## Other unseeded findings worth keeping

Opus surfaced ~15 real defects nobody seeded. The best of them are about the *set*
rather than any pair, and several are cases where my own drafting was accidentally
worse than intended:

- The Order Form is neither a Schedule (MSA 1.6 requires a document expressly stated
  to be one) nor an Addendum, so on MSA 1.1's definition it is **not part of the
  Agreement at all** — while purporting to set the term, price and payment terms.
- Schedules 2–6 are called Schedules but MSA 1.6 requires a Schedule to be executed by
  both parties, and only the Order Form has signature provisions.
- DPA 11.2's mutual indemnity, as drafted, has each party indemnifying the other for
  the other's own breach.
- InfoSec 6.3 produces the incident register at a "quarterly security review" that no
  governance provision anywhere establishes.

## Run

```bash
python run_w3.py --provider anthropic --model claude-opus-5 --doc xdoc9 --repeats 2
python run_w3.py --provider openai --model gpt-5.5 --doc xdoc9 --repeats 3
python run_w3.py --model qwen3:8b --doc xdoc9 --repeats 2
```

`--doc xdoc9` loads `../corpus_xdoc/` **and** this directory, and unions both ground
truths (it aborts on duplicate ids). `--doc xdoc` is untouched and still sends exactly
the four original documents. Two defaults change for `xdoc9`, both because the
originals are wrong at this size:

- `--max-output-tokens` → **48000**. 52 defects of prose plus thinking. Above ~8192
  the Anthropic path streams, because the SDK refuses non-streaming beyond that.
- `--num-ctx` → **24576** for Ollama. The corpus is ~36k chars; at a smaller window
  Ollama **truncates the tail silently** and the locals would never see the last
  documents, which would look like "locals cannot do cross-document reasoning".
