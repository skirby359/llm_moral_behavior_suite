# W3 — does session amnesia buy real independence?

**Runs:** 2026-08-03 (local), 2026-08-04 (frontier, then a second frontier vendor).
**Models:** `qwen2.5:3b`, `qwen3:8b` (Ollama), `claude-opus-5` (Anthropic),
`gpt-5.5` (OpenAI).
**Tasks:** 8 seeded defects in a 30-line document; 20 in a ~180-line document; and
**cross-document** conflicts across a contract set at three sizes — 24 defects over 4
documents / 6 pairs (`corpus_xdoc/`), 52 over 9 / 36 (`corpus_xdoc_ext/`), 87 over
15 / 105 (`corpus_xdoc_ext2/`).
Raw records in `results_*.json` and `variance_*.json`.

## Verdict

**Task-dependent, not falsified. Resampling recovers the gap between what one pass
reaches and what repeated passes reach in aggregate — and that gap is a property of the
model-task PAIR, not of the model.**

**Scope, which took four attempts to get right and is the part most easily
over-claimed:**

1. **Within one model, across tasks, the gain tracks headroom and does so cleanly.**
   `claude-opus-5`, k=8, same harness: gain **0.20 → 4.50 → 11.50** as its own
   single-pass headroom goes **0 → 3 → 10** defects. This is the controlled comparison,
   because capability is held fixed and only the task varies.
2. **Across models, it does not hold.** On the 15-document corpus the local models are
   73–82 defects short of ground truth against the frontier models' 7–12 — roughly ten
   times the headroom — and they gain **less**: `union − best single` runs 9.50, 9.50,
   6.50, 5.00 across gpt-5.5, qwen2.5:3b, claude-opus-5, qwen3:8b, with no relationship
   to headroom at all. Headroom and capability move together across models and the
   effect does not separate. **Earlier versions of this verdict stated the relationship
   without that restriction. The local runs are the counterexample that forces it.**
3. **The gain is multiplicative on a model's reach, so it cannot rescue a weak one.**
   `qwen2.5:3b` reaches a union of 15 of 87 — 5.5× its best single call, and still
   leaving **71–73 defects found by none of its eight calls.** Multiplying a small reach
   by eight is still a small reach.
4. **Blind spots survive resampling at every capability level**, frontier included:
   `E15_rpo_tolerates_data_loss` is missed by **all 16 `gpt-5.5` calls** on a corpus
   where it finds 84.5 of 87 in aggregate. Volume does not reach a hole.

So the usable form of the claim is narrow: **on a given model, more headroom means more
recoverable by resampling, up to that model's reach and excluding its blind spots.** It
says nothing about which model to pick, and it does not license comparing gains across
models.

**Report `union − best single`, not `gain vs call 1`.** The latter is
`union − recall(call 1)` and inherits call-1 luck: `qwen3:8b` opened with 12 and 11 and
looks like a small gainer while `qwen2.5:3b` opened near 2.5 and looks like a large one,
on a comparable union.

> **DECISIVE CONFIRMATION (2026-08-04, nine-document corpus).** The prediction this
> document has carried unresolved for three sessions — *"Opus would benefit from
> resampling on a task genuinely beyond one pass, which is precisely the task I could
> not construct"* — now has its task, and the prediction holds.
>
> `claude-opus-5` on `--doc xdoc9` (52 cross-document defects, 9 documents, 36 pairs),
> k=8, **2 independently-sampled repeats**:
>
> | | mean ± sd | values |
> |---|---|---|
> | per-call recall | 47.75 ± 0.35 | 47.5, 48.0 |
> | best single call | 48.50 ± 0.71 | 48, 49 |
> | union across k=8 | 51.50 ± 0.71 | 52, 51 |
> | **gain from calls 2–8** | **4.50 ± 2.12** | 6.0, 3.0 |
> | defect-set Jaccard | 0.956 ± 0.004 | |
>
> **No single call reaches what eight reach together** — best single 48.5 against a
> union of 51.5. On the same model the 20-defect document gave 0.20 ± 0.45. Nothing
> about the model changed; only the headroom did. That is the verdict below,
> demonstrated on the one model whose null result originally produced the wrong
> conclusion.
>
> It also kills the retracted "k=2 for Opus" rule: union curves
> `46 48 49 50 50 50 52 52` and `48 49 50 51 51 51 51 51` — saturation at call 7 in one
> repeat and call 4 in the other, against call 2 on the easy document. **k is a
> property of the model-task pair and has to be measured, not inherited.**
>
> Cost: **$3.54 ± 0.08** for all 8 calls, **$0.43** for call 1, so **$3.11 after call 1
> bought 4.5 defects — about $0.69 each.** A real purchase, where the same spend bought
> 0.2 on the easy document.
>
> **A correction of my own, recorded because it is this document's recurring lesson.**
> I published these numbers at n=1 as `gain +6.00, union 52/52` before the second
> repeat finished. Both were the high end: the gain is 4.50 ± 2.12, and only one repeat
> reached 52 — the other stalled at 51, never finding `E10_review_cadence` in eight
> calls. The sd of 2.12 on n=2 is large. **The direction is robust and the magnitude is
> not yet pinned down**; n=2 is barely better than n=1 for a spread that wide.

> **The second frontier vendor is what makes the tier explanation untenable.**
> Until 2026-08-04 the evidence came from comparing local models (which gained) against
> Opus 5 (which did not) — and there, headroom was perfectly confounded with capability
> tier, so "frontier models don't benefit" fitted the data just as well. `gpt-5.5`
> breaks that: it is a frontier model that **has** headroom on the 20-defect document
> (14.77/20 per call) and **does** gain, **2.00 ± 1.22**, where Opus 5 on the identical
> document sits at 19.67/20 and gains 0.20 ± 0.45. Two frontier models, same document,
> opposite results — so the tier is not what determines it.
>
> **What this does NOT establish is that headroom determines the gain across models.**
> It rules out one rival explanation; it does not promote headroom to a general law.
> The 15-document runs later showed the local models holding ~10× the headroom of both
> frontier models and gaining less, which is flatly inconsistent with a cross-model
> headroom law. See scope point 2 above.

> **This verdict has been wrong four times, and the corrections all run the same
> way: a conclusion drawn on too narrow a sample, stated without its scope.**
>
> 1. *"Falsified, and the stronger the model the harder it fails."* Drawn from one
>    easy document.
> 2. *"A capability threshold, not a gradient."* Corrected to this when variance bars
>    showed the 8B and Opus indistinguishable — still on the same easy document.
> 3. *"The gap belongs to the model-task pair."* Right, and it survives — but I then
>    stated the headroom relationship as though it held **across** models, on evidence
>    (locals gained, Opus did not) where headroom and capability were confounded.
> 4. *The cross-model version.* Refuted by the 15-document runs: ten times the
>    headroom on the local models, and less gain.
>
> Each correction came from widening the sample, never from thinking harder about the
> same data. And each wrong version was *consistent with everything measured at the
> time* — which is why the scope restrictions above are stated explicitly rather than
> left implicit in a table.

Measured over 5 repeats per model on two documents:

| model | doc | mean/call | best single | union k=8 | **gain from calls 2–8** |
|---|---|---|---|---|---|
| `qwen2.5:3b` | short (8) | 1.73 | 3.4 | 5.0 | 3.20 ± 1.48 |
| `qwen2.5:3b` | long (20) | 2.00 | 4.4 | 9.0 | **7.20 ± 1.92** |
| `qwen3:8b` | short (8) | 4.95 | 5.0 | 5.0 | 0.20 ± 0.45 |
| `qwen3:8b` | long (20) | 7.35 | 10.4 | 13.2 | **6.60 ± 1.82** |
| `claude-opus-5` | short (8) | 7.52 | 8.0 | 8.0 | 0.40 ± 0.55 |
| `claude-opus-5` | long (20) | 19.67 | 20.0 | 20.0 | 0.20 ± 0.45 |
| **`gpt-5.5`** | **long (20)** | **14.77** | **16.6** | **17.2** | **2.00 ± 1.22** |
| `claude-opus-5` | xdoc (24, 4 docs) | — | 24.0 | 24.0 | 0 by construction |
| `gpt-5.5` | xdoc (24, 4 docs) | 22.33 | 22.7 | 23.3 | 0.67 ± 0.58 |
| `qwen3:8b` | xdoc (24, 4 docs) | 5.88 | 13.0 | 17.5 | 10.50 ± 4.95 |
| `qwen2.5:3b` | xdoc (24, 4 docs) | 1.93 | 4.7 | 7.7 | 7.00 ± 1.73 |
| **`claude-opus-5`** | **xdoc9 (52, 9 docs)** | **47.75** | **48.5** | **51.5** | **4.50 ± 2.12** (n=2) |
| **`claude-opus-5`** | **xdoc15 (87, 15 docs)** | **76.13** | **80.0** | **86.5** | **11.50 ± 2.12** (n=2) |
| **`gpt-5.5`** | **xdoc15 (87, 15 docs)** | **69.63** | **75.0** | **84.5** | **14.00 ± 4.24** (n=2) |
| `qwen3:8b` | xdoc15 (87, 15 docs) | 8.29 | 13.5 | 18.5 | 7.00 ± 2.83 (n=2) |
| `qwen2.5:3b` | xdoc15 (87, 15 docs) | 2.75 | 5.5 | 15.0 | 12.50 ± 0.71 (n=2) |

Read the `claude-opus-5` rows together, because that is the controlled comparison.
**Same model, same harness, same k: gain 0.20 on the long document, 4.50 on xdoc9,
11.50 on xdoc15** as its own headroom goes 0 → 3 → 10 defects. On the hard tasks no
single call reaches what eight reach together (80.0 vs 86.5). Capability did not change
between those rows; only how much a single pass left on the table.

Within a model, the gain is large exactly where `best single < union` and ~zero where a
single pass already exhausts that model's reach.

**Do not read the table down the columns across models.** An earlier version of this
paragraph said "capability enters only through how much one pass reaches — it is not
itself the variable." **That is wrong**, and the local xdoc15 rows are why: `qwen2.5:3b`
is 81 defects short of ground truth and `claude-opus-5` is 7 short, yet their
`union − best single` figures are 9.50 and 6.50 — the same order of magnitude. Ten times
the headroom does not buy ten times the recovery, because a model can only recover what
it is capable of finding at all. Capability sets both the starting point *and* the
ceiling on the gain, so it is very much a variable.

`gpt-5.5` on the long document is the row that killed the "frontier models don't
benefit" story. Same document as Opus 5, per-call recall 5 defects lower, and it gains
**2.00 ± 1.22** (nonzero in 4 of 5 repeats) where Opus gains 0.20 ± 0.45. Its
defect-set Jaccard is 0.834 against Opus's ~0.98 — genuinely different findings per
call, not restatements. Had the tier story been right, this row would look like the
Opus row.

That is a refutation of one rival explanation, not a promotion of headroom to a law.
The two claims are easy to run together and I did exactly that for several hours.

Cost, measured the same way: all 8 calls **$0.885 ± 0.042**, call 1 alone
**$0.118 ± 0.015**, so **$0.767 ± 0.029 spent after call 1** to buy 2.0 defects.
That is a real purchase rather than the near-pure waste it is on Opus — about
$0.38 per additional defect.

So Opus 5 gains nothing here not because it is a frontier model but because **both
documents are within its single-pass reach.** The prediction that follows is that
Opus *would* benefit from resampling on a task genuinely beyond one pass — which was
for three sessions the task I could not construct (see "the ground truth was a
ceiling").

**That task now exists and the prediction is confirmed: 4.50 ± 2.12 on the
nine-document corpus, union 51.5 against a best single call of 48.5.** The paragraph
above was written as a hedge against a null result; it turned out to be a correct
prediction, and the thing that made it testable was not a better model or a better
metric but a task with enough headroom to measure.

| | `qwen2.5:3b` | `qwen3:8b` | `claude-opus-5` |
|---|---|---|---|
| mean per-call recall | 1.3/8 | 4.9/8 | **7.4/8** |
| best single call | 3/8 | 5/8 | **8/8** |
| union across k=8 | 4/8 | 5/8 | 8/8 |
| **gain from calls 2–8** (n=5) | **3.20 ± 1.48** | **0.20 ± 0.45** | **0.40 ± 0.55** |
| repeats with zero gain | 0 / 5 | 4 / 5 | 3 / 5 |
| defect-set Jaccard | 0.232 | **0.950** | 0.933 |
| beyond-ground-truth findings | 6 (≈3 fabricated) | 0 | 35 (real) |
| cost of all 8 calls | — | — | **$0.359** |
| cost of call 1 alone | — | — | **$0.041** |

On Opus 5, **call 1 alone delivered ~7.5 of the 8 seeded defects** for ~$0.045.
Seven further independent calls added 0.40 ± 0.55 more, for a further $0.32 — and
added *nothing at all* in three of the five repeats. Every repeat had at least one
call reach 8/8. So the robust claim is "call 1 gets 7–8 of 8, and seven more calls
add at most one," not "exactly zero."

## Why the two stronger models both land at zero

- **`qwen2.5:3b`** — union (5.0 ± 0.7) clearly beats best single (3.4 ± 0.6).
  Resampling recovers 3.20 ± 1.48 defects, and helped in **5 of 5** repeats. But it
  bundles fabrications in with the extra recall (see below), so the recall is not
  free.
- **`qwen3:8b`** — union equals best single at 5.00 (sd 0.00 on both). Gains
  0.20 ± 0.45. At temp 0.0 the eight outputs are byte-identical; at temp 0.8 they
  are textually distinct (token Jaccard 0.769) with near-identical substance
  (defect-set Jaccard 0.980 ± 0.027). **It cannot find more than 5/8.**
- **`claude-opus-5`** — best single = union = 8.00 (sd 0.00 in both, every repeat).
  Gains 0.40 ± 0.55. **It has already found all 8.**

Parallel resampling is therefore a **substitute for capability, not an addition to
it**: it lifts a weak model toward where a stronger one starts, and contributes
nothing once the model is at its own ceiling — whether that ceiling is below the
task (the 8B) or at the top of it (Opus). That is bad news specifically for
frontier-model fan-out patterns, which is where "run it N times independently"
usually gets deployed.

## Methodological correction: the ground truth was a ceiling

The 8-defect ground truth answers W3 on local models and **cannot** answer it on
Opus 5, which scored 7/8 on the very first smoke call and surfaced six further
*real* defects that were never seeded — 2.1's per-employee cap being
unreconcilable with 2.2's trip total, 4.2's unlimited discretion nullifying 4.1's
mandatory deadline, "trip completion" (which starts the clock) never defined,
Section 5's definitions placed after the clauses that use them.

Against a ceiling the model exceeds, defect-set Jaccard saturates near 1.0 for
reasons unrelated to any attractor. Reporting 0.946 as "no diversity" would have
been re-measuring this repo's known ceiling effect (see `README.md`) and calling
it a W3 result.

So the analysis adds a **ground-truth-free** track: section signatures — the set
of clause references each call cites, capturing *where the model looked*
regardless of seeding or wording. On Opus 5:

```
sections per call    [16, 19, 17, 18, 18, 15, 19, 16]
sections union       20   curve [16, 19, 19, 19, 20, 20, 20, 20]
mean pairwise J      0.877
```

Call 1 touched 16 clauses. Seven more calls raised the union to 20 and saturated
by call 5. Genuine but marginal variation — **+25% coverage breadth for 8× the
cost**, on the measure specifically built to be immune to the ceiling.

### The ceiling was attacked twice, and length was the wrong axis

The prediction above — that Opus *would* gain on a task genuinely beyond one pass —
needs such a task to exist. Two attempts:

1. **More seeded defects in a longer document** (`document_long.md`, 20 defects,
   ~180 lines). Failed: 20/20 on call 1 in all five repeats. Escalating to 50 would
   likely go the same way, and the target moves each time.
2. **Cross-document contradiction** (`corpus_xdoc/`, 24 defects across four
   documents). **Every seeded defect is a conflict between two documents, so none
   can be found by reading one document in isolation, and each document is
   internally consistent.** Four documents give six pairs; pairs to check grow
   quadratically while tokens grow linearly.

The reasoning behind attempt 2 is that **length is not the only thing that outruns a
single pass — combinatorics is**, and it is far cheaper to author. The overnight plan
had been "tens of pages of authored prose"; that would have bought a linear increase
in what attention must cover, when the evidence from attempt 1 was already that
linear increases do not bite (section Jaccard moved only 0.883 → 0.841 for a 5×
length increase).

Design, conflict map and verification: `corpus_xdoc/README.md`. The matcher is
verified against hand-written exemplar findings before any run
(`corpus_xdoc/verify_corpus.py`), because a rule that matches nothing would
understate recall and make the corpus look harder than it is — the single most
expensive way to be wrong here.

**Attempt 2 also failed to beat Opus 5: 24/24 on the first call** at four documents
and 24 defects. **Attempt 3 succeeded.** `corpus_xdoc_ext/` adds five more documents
(Order Form, InfoSec Policy, BCDR Plan, Change Control Procedure, Exit Plan), taking
the set to **nine documents, 36 pairs and 52 seeded defects** via `--doc xdoc9`:

| corpus | docs | pairs | defects | Opus 5, call 1 | missed |
|---|---|---|---|---|---|
| `document.md` | 1 | — | 8 | 8/8 | 0 |
| `document_long.md` | 1 | — | 20 | 20/20 | 0 |
| `corpus_xdoc/` | 4 | 6 | 24 | 24/24 | 0 |
| **+ `corpus_xdoc_ext/`** | **9** | **36** | **52** | **49/52** | **3** |
| **+ `corpus_xdoc_ext2/`** | **15** | **105** | **87** | **77/87** | **10** |

**Headroom scales with pairs, and the gain scales with headroom.** Measured on
`claude-opus-5`, k=8, 2 independent repeats per corpus:

| headroom (missed on call 1) | corpus | **gain from calls 2–8** | best single → union |
|---|---|---|---|
| 0 | long doc (20 defects) | 0.20 ± 0.45 | 20.0 → 20.0 |
| 3 | xdoc9 (52) | 4.50 ± 2.12 | 48.5 → 51.5 |
| **10** | **xdoc15 (87)** | **11.50 ± 2.12** | **80.0 → 86.5** |

One model, one harness, one k, three tasks: **0.20 → 4.50 → 11.50 as single-pass
headroom goes 0 → 3 → 10.** This also refutes the alternative reading of a low call-1
score. Ten missed defects could have been ten defects *no* sampling reaches — a
capability floor rather than recoverable headroom. Resampling recovers 11.5, so they
were reachable.

### The relationship is WITHIN a model. It does not hold across models.

All four models on `xdoc15`, k=8, n=2 each:

| model | per-call /87 | best single | union k=8 | gain vs call 1 | **union − best single** | defect Jaccard |
|---|---|---|---|---|---|---|
| `claude-opus-5` | 76.13 | 80.00 | 86.50 | 11.50 ± 2.12 | 6.50 | 0.876 |
| `gpt-5.5` | 69.63 | 75.00 | 84.50 | 14.00 ± 4.24 | 9.50 | 0.851 |
| `qwen3:8b` | 8.29 | 13.50 | 18.50 | 7.00 ± 2.83 | 5.00 | 0.390 |
| `qwen2.5:3b` | 2.75 | 5.50 | 15.00 | 12.50 ± 0.71 | 9.50 | **0.08** |

**The locals have roughly ten times the headroom of the frontier models — 73 to 82
defects short of the ground truth against 7 to 12 — and they do not gain more.** On the
stable measure (`union − best single`) the ordering is 9.50, 9.50, 6.50, 5.00 with no
relationship to headroom at all.

So "gain scales with headroom" is a **within-model** statement, and it is only clean
because capability is held fixed while the task varies. Across models, headroom and
capability move together and the effect does not separate. An earlier version of this
section stated the relationship without that restriction; the local runs are the
counterexample that forces the qualification.

Note also which column is noisy. `gain vs call 1` is `union − recall(call 1)`, so it
inherits call-1 luck: `qwen3:8b` happened to open with 12 and 11 and looks like a small
gainer, while `qwen2.5:3b` opened near 2.5 and looks like a large one, on nearly the
same union. **Quote `union − best single`.**

The local numbers also put a hard limit on what resampling buys. `qwen2.5:3b` reaches a
union of 15.00 of 87 — 5.5× its best single call, and still leaving **71–73 defects
found by none of its eight calls.** Multiplying a small reach by eight is still a small
reach.

`gpt-5.5` on the same corpus: per-call 69.63 ± 2.30, best single 75.00, union
84.50 ± 0.71, **gain 14.00 ± 4.24**. More headroom than Opus and a larger gain, in the
predicted direction — but 11.50 ± 2.12 against 14.00 ± 4.24 at n=2 **overlap heavily
and must not be quoted as different.** What is clear is that both sit far above the
near-zero gains either shows at ceiling.

**Neither model saturates at k=8** — three of the four union curves are still climbing
on the last call, so k=8 is a floor for this corpus, not an optimum.

**Cost inverts the usual story.** gpt-5.5 buys an additional defect for **$0.148**
against Opus's **$0.35**, at half the cost per repeat ($2.38 vs $4.60), because it
starts lower, climbs further, and bills output cheaper. Opus still reaches the higher
aggregate (86.5 vs 84.5). Resampling gets *more* economical as headroom grows: on Opus
the cost per additional defect runs $∞ (at ceiling) → $0.69 (xdoc9) → $0.35 (xdoc15).

Design, conflict map and the blind-spot analysis: `corpus_xdoc_ext2/README.md`.

**So the mechanism was right and the dose was too small.** Quadrupling the seeded
defects on one document (8 → 20) changed nothing; sextupling the *pairs* (6 → 36) put
Opus below ceiling for the first time in four attempts. It missed `E10` (quarterly vs
annual review cadence), `E15` (an RPO that designs in data loss the DPA would call a
Security Incident) and `E27` (source-code handover against the MSA's IP reservation) —
all three in the "subtle" grade, and all three requiring a document pair to be held
together.

49/52 is thin headroom, and worth being precise about: it is **structurally** different
from 24/24 rather than merely numerically different. At ceiling the union across k
calls cannot exceed the best single call and the gain is zero as arithmetic. Below
ceiling it can, so resampling becomes measurable at all.

Recorded as a negative result for attempt 2 rather than dressed up, and the
correction is that the four-document version was under-powered, not that
combinatorics does not work.
Opus additionally surfaced ~20 unseeded real defects, several of them good — the DPA
carries a `PRECEDENCE` heading with no precedence rule under it; MSA 12.2 makes
records available "in accordance with clause 10.2" while 10.2 *removes* the
inspection right; SLA 5.4 starts the response-time clock at the Provider's own
acknowledgement, so the 15-minute target measures nothing.

What the corpus *is* good for is a task with a very wide headroom range, which is
what testing the headroom claim actually requires:

| model | mean/call | best single /24 | union k=8 | **gain vs call 1** | union − best single | defect Jaccard |
|---|---|---|---|---|---|---|
| `claude-opus-5` | — | **24** (single call) | 24 | 0 by construction | 0 | — |
| `gpt-5.5` (n=3) | 22.33 | 22.67 ± 0.58 | 23.33 ± 1.15 | **0.67 ± 0.58** | 0.67 | 0.970 |
| `qwen3:8b` (n=2) | 5.88 | 13.00 ± 0.00 | 17.50 ± 0.71 | **10.50 ± 4.95** | 4.50 | 0.27 |
| `qwen2.5:3b` (n=3) | 1.93 | 4.67 ± 0.58 | 7.67 ± 0.58 | **7.00 ± 1.73** | 3.00 | **0.15** |

**Four models, one task, and the gain moves with the headroom.** Model identity is
the only thing varying and the task is held exactly constant, which makes this the
strongest form of the claim available here.

Two columns, because `gain vs call 1` is noisier than it looks: it is
`union − recall(call 1)`, so it inherits however lucky the first call happened to be.
`qwen3:8b`'s ±4.95 comes from call 1 scoring 4 in one repeat and 10 in the other, not
from any instability in what eight calls reach (`union` sd is 0.71). **`union − best
single` is the more stable statement of what extra calls buy** and is reported
alongside. The ordering is the same under both.

### But the gain is not monotone in headroom, and that is new

`qwen3:8b` recovers more than `qwen2.5:3b` on both measures (10.50 vs 7.00 against
call 1; 4.50 vs 3.00 against best-single) **despite having less headroom** — its
best single call reaches 13/24 against the 3B's 4.67/24. So the recoverable gap is
not headroom alone; it is closer to the product of per-call ability and headroom. A
model has to be good enough to find things before extra samples have anything to
accumulate: the 3B averages 1.93 findings per call, so eight calls cannot reach far
even though nearly everything is left to find. Peak benefit sits in the *middle* of
the capability range for a given task, not at the bottom.

This refines rather than overturns the verdict above. "Resampling recovers the gap
between one pass and repeated passes" still holds; what this adds is that the gap is
only *recoverable* to the extent the model can traverse it.

### A within-model confirmation, which removes the last confound

`gpt-5.5` on two tasks, model identity held fixed:

| task | per-call reach | **gain from calls 2–8** |
|---|---|---|
| long document (20 defects) | 14.77/20 | **2.00 ± 1.22** |
| cross-document corpus (24) | 22.33/24 | **0.67 ± 0.58** |

Same model, same k, same harness. The task with more headroom yields the larger
gain. Combined with the cross-model row above and the two-frontier-vendor comparison
on the long document, the headroom claim now holds across models on one task, across
tasks on one model, and across vendors — which is as close to a controlled result as
this setup allows.

Cost on the corpus: all 8 calls **$1.610 ± 0.074**, call 1 alone
**$0.203 ± 0.039**, so **$1.407 ± 0.093 after call 1 to buy 0.67 defects** — roughly
$2.10 per additional defect, versus $0.38 on the long document. Spend efficiency
degrades exactly as headroom shrinks.

### Breadth of attention varies far more than substance does

The section-signature track (the ground-truth-free measure) separates *where a call
looked* from *what it found*, and on this corpus the two come apart sharply.
`gpt-5.5`, per repeat: 35–55 clause references per call, union rising **42 → 75**
across eight calls (+79% breadth), section Jaccard **0.547 ± 0.014**. Over the same
eight calls the defect-set Jaccard is **0.970** and the seeded gain is 0.67/24.

**The extra calls look in substantially different places and come back with the same
findings.** That is the attractor hypothesis W3 started from, isolated: positional
diversity without substantive diversity. It is only visible because the two tracks
are measured separately, and it is the clearest argument in this document for keeping
the ground-truth-free measure even when a seeded metric is available.

Corrected section figures for the corpus (see the regex bug below):

| model | sections union (k=8) | section Jaccard |
|---|---|---|
| `gpt-5.5` (n=3) | 76.67 ± 1.53 | 0.547 ± 0.014 |
| `qwen3:8b` (n=2) | 40.00 ± 15.56 | 0.490 ± 0.062 |
| `qwen2.5:3b` (n=3) | 41.00 ± 1.73 | 0.178 ± 0.067 |

### A regex bug invalidated every cross-document section figure

`XDOC_SECTION_RE` was written with a **capturing** group for the document names.
`re.findall` returns only the groups when a pattern has any, so every clause number
matched by the first alternative came back as `''` and was discarded. Each call's
signature collapsed to the set of document names, and every corpus run reported
`sections_union = 4.00` with section Jaccard **exactly 1.000**.

That is the shape of a finding — "all eight calls looked in precisely the same
places" — and it was a one-character bug. The fix is `(?:...)`.

The affected runs cost real money and did **not** need repeating:
`variance_*.json` stores each call's raw `findings`, so `recompute_sections.py`
re-derives the signatures offline. It recomputes the single-document runs too, as a
control: those used `SECTION_RE`, which has no capturing group, and their stored and
recomputed values agree to the digit in all five files — which is what licenses
trusting the corrected corpus numbers. `SECTION_RE` itself is deliberately left
alone so previously published figures stay reproducible.

**A k=8 Opus arm on this corpus was deliberately not run, and that is a cap on
coverage rather than an omission.** Its single call already hits 24/24, so the union
across k cannot exceed it and the gain is zero as arithmetic, not as measurement.
~$1.85 to put an error bar on a certainty is worse value than leaving the budget for
the larger corpus this document keeps asking for. The Opus figure above is therefore
**n=1 call**, twice reproduced (once invalidly — see the answer-key bug — and once
cleanly), not a variance estimate.

`qwen2.5:3b`'s defect-set Jaccard of **0.15** is the lowest figure in the whole W3
programme. On a task far beyond its single-pass reach, eight independent calls
genuinely find *different* defects, and the union is still climbing at call 8 in two
of three repeats. **This is the amnesia-buys-independence claim behaving exactly as
W3 originally predicted** — and it was only ever visible once the task was hard
enough for the model, which is the whole thesis of this document restated from the
other end.

Robustness check on the harness rather than the model: `qwen2.5:3b` was run at both
`num_ctx=16384` (n=3) and `num_ctx=8192` (n=2). Gain 7.00 ± 1.73 vs 8.00 ± 1.41,
Jaccard 0.15 vs 0.14 — the context change does not move the finding. Worth checking
because Ollama **truncates an over-long prompt silently**, and at its default context
the locals would never have seen the last document or two.

## Variance bars (5 repeats × 8 calls per model, parallel condition)

`variance_*_r5.json`. 120 calls. At n=5 the SD is itself noisy, so the range and
the per-repeat values carry more weight than the SD.

**Gain from calls 2–8 — the number the whole wager reduces to:**

| model | mean ± sd | range | per-repeat values | repeats with **zero** gain |
|---|---|---|---|---|
| `qwen2.5:3b` | 3.20 ± 1.48 | 1–5 | 5, 1, 4, 3, 3 | **0 / 5** |
| `qwen3:8b` | 0.20 ± 0.45 | 0–1 | 0, 0, 1, 0, 0 | **4 / 5** |
| `claude-opus-5` | 0.40 ± 0.55 | 0–1 | 0, 1, 0, 1, 0 | **3 / 5** |

Opus 5 detail, all tight:

| metric | mean ± sd | range |
|---|---|---|
| mean per-call recall | 7.52 ± 0.18 | 7.25–7.75 |
| best single call | **8.00 ± 0.00** | 8–8 |
| union across k=8 | **8.00 ± 0.00** | 8–8 |
| defect-set Jaccard | 0.937 ± 0.009 | 0.929–0.946 |
| section Jaccard | 0.883 ± 0.023 | 0.866–0.922 |
| sections on call 1 | 16.80 ± 0.84 | 16–18 |
| sections union | 19.20 ± 1.10 | 18–20 |
| cost of all 8 calls | $0.3662 ± 0.0055 | $0.359–0.373 |
| cost of call 1 | $0.0454 ± 0.0034 | $0.042–0.049 |
| **spent after call 1** | **$0.3208 ± 0.0081** | $0.311–0.331 |

In **every** repeat, at least one call hit all 8 (best single = 8.00, sd 0.00), and
the union never exceeded 8. Seven extra calls bought 0.4 defects on average and
**nothing at all in three of five repeats**, for a stable $0.32.

Stated as a rate rather than a ratio, because the denominator is near zero: call 1
delivers ~7.5 of 8 defects for ~$0.045 — about **$0.006 per defect**. The remaining
$0.32 buys, on average, four tenths of one more.

### Correction: it's a threshold, not a gradient

I earlier called the trend "monotonic with capability." The variance bars don't
support that. `qwen3:8b` (0.20 ± 0.45) and `claude-opus-5` (0.40 ± 0.55) have
**completely overlapping ranges** — they are indistinguishable from each other and
from zero. Only the 3B separates cleanly.

So resampling has a **threshold**, not a gradient: a weak, high-variance model
benefits substantially; both stronger models do not. And the two stronger models
arrive at the same near-zero for *opposite* reasons — `qwen3:8b` gains nothing
because 5/8 is its ceiling and it cannot find more; Opus 5 gains nothing because it
already found all 8. Same number, different mechanism, and the distinction matters
for anyone deciding whether to fan out.

One further nuance from the ground-truth-free track: `qwen3:8b`'s section union
(10.4 ± 2.2) nearly doubles its call-1 figure (5.6 ± 1.1), yet it yields
~0.2 beyond-ground-truth findings. Its extra calls cite *different clauses for the
same five defects* — coverage breadth that never converts into new findings. Section
diversity is therefore necessary but not sufficient evidence of useful independence.

## Long document (20 defects, ~180 lines) — and the one positive prescription

`variance_claude-opus-5_long_r5.json`, 5 repeats × 8 calls. This tests the standing
caveat that a 30-line document may suppress the differential attention a longer
corpus would produce.

**First, the document failed to create headroom.** Opus 5 scored **20/20 on the
first call in every one of the five repeats** (best single = union = 20.00, sd 0.00),
and surfaced ~51 further real defects per repeat that were never seeded. Eight
defects and twenty defects give the same answer: **deliberate defect injection cannot
create headroom against this model at these scales.** So the seeded metric is dead
here too, and the ground-truth-free track is the whole instrument.

| metric | short doc | long doc |
|---|---|---|
| gain from calls 2–8 (seeded) | 0.40 ± 0.55 | **0.20 ± 0.45** |
| section Jaccard | 0.883 ± 0.023 | **0.841 ± 0.017** |
| sections on call 1 | 16.8 ± 0.8 | **42.0 ± 2.7** |
| sections union across 8 | 19.2 ± 1.1 | **50.8 ± 1.9** |
| marginal breadth from 7 extra calls | +14% | **+21%** |
| beyond-ground-truth findings | 32.2 ± 2.8 | **51.2 ± 2.3** |
| cost of all 8 calls | $0.366 ± 0.006 | **$0.837 ± 0.023** |
| **spent after call 1** | $0.321 ± 0.008 | **$0.731 ± 0.020** |

**The differential-attention hypothesis is weakly supported and does not rescue
resampling.** Length does buy more cross-call variation — section Jaccard falls
0.883 → 0.841, marginal breadth rises +14% → +21%, and saturation moves from call 5
to call 7. But the seeded gain stays at ~0, and because a longer document costs more
per call, the *absolute* waste more than doubles: $0.73 thrown after call 1 versus
$0.32. Resampling gets worse in dollar terms as the document grows.

### There is no universal k — measure the union curve

I briefly concluded from Opus alone that "k=2 gets 91% of k=8, so run two and stop."
**That was over-generalised.** The local runs on the same document refute it outright:

```
                 defect union curve (mean of 5 repeats)      k=2 gets   saturates
claude-opus-5    19.8 20.0 20.0 20.0 20.0 20.0 20.0 20.0       100%      call 2
qwen3:8b          6.6  8.4  9.6 11.2 11.8 12.0 12.8 13.2        64%      call 7
qwen2.5:3b        1.8  3.4  5.0  5.6  6.0  6.8  7.8  9.0        38%      never
```

The 3B is **still climbing at call 8** and k=2 gets it barely a third of the way. A
fixed k is the wrong kind of answer.

**The right rule is a method, not a number:** resampling yield ≈ (aggregate
reachable) − (single-pass reach), so plot the union curve for your own model-task pair
on a sample and stop where the increment dies. That costs a few calls and replaces
guesswork. Concretely, on this task it would tell you k≈2 for Opus, k≈7 for the 8B,
and k>8 for the 3B.

Note also that saturation depends on *which target you measure*: Opus exhausts the
seeded defects by call 2 but keeps citing new clauses (finding new unseeded issues)
until call 7. Pick the target that matches what you actually want out of the fan-out.

What survives unambiguously is the negative half: **on a model that already covers
the task in one pass, additional identical calls are close to pure spend** — $0.73 ±
0.02 of Opus's $0.84 in the long-document run bought 0.2 defects. And the alternative
is unchanged: past the point where the curve flattens, vary the prompt rather than the
seed.

## What resampling actually costs

Token usage is now recorded per call, so the cost claim rests on measured spend
rather than call count. `claude-opus-5` at $5/$25 per MTok:

| | parallel k=8 | sequential k=8 |
|---|---|---|
| tokens in / out | 6,920 / 12,972 | 37,905 / 10,659 |
| wall clock | 176s | 164s |
| **total** | **$0.359** | **$0.456** |
| call 1 | $0.041 | $0.045 |
| **spent after call 1** | **$0.318** | **$0.411** |
| …which bought | +1 defect, +3 sections | **+0 defects**, +5 sections |

The sharpest way to put it, using the 5-repeat means: **call 1 finds ~7.5 defects at
~$0.006 each; the remaining $0.32 buys 0.4 more.** In three of five repeats it bought
nothing at all, so a marginal cost-per-defect ratio is undefined as often as not —
the honest statement is the rate, not a ratio.

Sequential is the *more* expensive condition here — 5.5× the input tokens, because
context accumulates — and it bought no additional seeded defect at all.

Two honest qualifications on the cost figures:

- **Prompt caching was not enabled** (cache read and write tokens were both zero —
  no `cache_control` was set). With it, sequential's repeated prefix would bill at
  0.1×, cutting roughly $0.17 of its $0.19 input cost and likely making sequential
  *cheaper* than parallel overall. The cost *ordering* between the two conditions is
  therefore an artifact of this configuration; the finding that turns 2–8 buy nothing
  substantive is not.
- Output tokens dominate either way ($0.27 of sequential's $0.46), and on Opus 5
  output includes thinking tokens, which are on by default.

## Sequential looked like a win; inspection refuted it

Sequential (one conversation asked "any more?" eight times) reached a *wider*
section union than parallel — 22 vs 20 — with 87 beyond-ground-truth findings vs
37. Read naively, accumulation beat amnesia.

It doesn't. The later turns degrade into drafting nitpicks (inconsistent
`must`/`shall` usage, dollar-amount formatting, "a one-clause section padded"),
and **Opus 5 says so itself, unprompted**:

> *turn 7:* "Diminishing returns note: the substantive defects have been exhausted
> in prior rounds; the items below are the remaining minor or structural
> observations"
>
> *turn 8:* "No further genuine defects identified; the substantive, structural,
> and drafting-level issues appear exhausted after six rounds. Remaining items
> below are marginal"

Turn 1 alone found 8/8. Turns 2–6 add some legitimate coverage; 7–8 are
acknowledged padding. Sequential's breadth advantage is an artifact of being
pushed to produce output after it had nothing substantive left.

**This is a direct hit for Phase 20's central metric.** Opus 5 volunteered its own
diminishing-returns signal with no instruction to do so. A coverage- or
finding-count metric scores those turns as wins; NVAR, which rewards legible
uncertainty over raw volume, scores them correctly. The behavior the metric was
designed to select for is already present and measurable.

The local models behaved differently under the same prompt: `qwen3:8b` returned
*nothing* from turn 3 onward (correct — it declined to invent), and `qwen2.5:3b`
sat flat at 2/8. Neither padded, and neither explained itself.

## Blind spots survive resampling — on frontier models too

**D5** ("the reviewer", never defined) and **D7** (Appendix B referenced, absent)
were found by **zero of 48 local calls**, across both models and all three
conditions. Opus 5 found both on nearly every call.

So blind spots are a capability property, not a sampling property: repetition
resamples the same distribution including its holes, while a stronger model simply
doesn't have those holes. Another reason resampling doesn't substitute for
capability.

**Confirmed on the frontier once the task was hard enough (xdoc15, 2026-08-04).** The
paragraph above was written from local-model data, where "a stronger model simply
doesn't have those holes" was the whole explanation. It is incomplete: strong models
have holes too, and resampling does not fill them either.

| defect | missed by every one of |
|---|---|
| `E15_rpo_tolerates_data_loss` | **all 16 `gpt-5.5` calls**, both repeats |
| `E10_review_cadence` | 8 Opus calls (r2) and 8 gpt-5.5 calls (r1) |
| `Z08_immediate_suspension_vs_cure_period` | 8 gpt-5.5 calls (r1) |
| `Z26_engineer_rate_vs_standard_rate` | 8 gpt-5.5 calls (r2) |

`E15` — a Recovery Point Objective that designs in 24 hours of data loss the DPA would
classify as a Security Incident — is invisible to gpt-5.5 across **sixteen independent
calls**, on a corpus where it finds 84.5 of 87 defects in aggregate. Volume does not
reach a blind spot.

Both persistent misses are "subtle" grade and share a shape: they require reasoning
about the **implication** of a stated value rather than comparing two stated values.
Every conflict of the "these two numbers differ" kind was found by nearly every call.
That is a sharper characterisation of what resampling cannot buy than the local-model
data supported.

## What this does and does not condemn

**Condemned.** "Run it N times with the same prompt and take the union." Adversarial
verification by N *identical* skeptics. Any expectation that repetition compensates
for a blind spot. On a frontier model, all three buy approximately nothing.

**Not tested.** Varying the *prompt* across sessions. An AB/BA synthesis check that
swaps which topic serves as lens, and a run-1/run-2 swap of label assignment, both
vary the input, which is a different manipulation. This
experiment falsifies only the weaker assumption that fresh context alone yields
diversity.

**Actionable.** Diversity must be *injected* through prompt variation, not hoped for
from sampling — empirical support for a distinct lens per verifier over N identical
refuters. And on a capable model, prefer one good pass plus a targeted second look
over a fan-out of identical passes.

## Caveats

- **No temperature control on Opus.** Opus 5/4.8/4.7 reject
  `temperature`/`top_p`/`top_k` with a 400, so the frontier path ran default
  sampling only and the temp-0.0 convergence control could not be re-established
  there. It holds on Ollama (8 byte-identical outputs, 1/8 distinct) and the
  scoring code is shared, so the control transfers — but it was not re-run.
- **Cost figures assume no prompt caching**, which was not enabled — see the two
  qualifications under "What resampling actually costs."
- **5 repeats on the parallel condition only.** Sequential was run once per model;
  its conclusion is qualitative (Opus labelling its own late turns as marginal) and
  would not sharpen with more samples. At n=5 the SDs are noisy — the ranges and
  per-repeat values are the more honest summary, which is why both are reported.
- One short synthetic document, eight coarse seeded defects, matchers tuned against
  smoke output and demonstrably missing real hits on the 3B — local recall figures
  are floors, not point estimates.
- A 30-line document may suppress variation a long corpus would produce through
  differential attention. The saturation-by-call-5 result in particular deserves
  re-testing at length.
- Local runs used `think:false`, per this repo's existing convention.
