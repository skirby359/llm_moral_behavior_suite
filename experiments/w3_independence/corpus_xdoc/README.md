# Cross-document corpus — a task designed to exceed one pass

## The problem this exists to solve

W3 needs a task that a frontier model **cannot cover in a single call**. Two
attempts failed:

| document | seeded defects | Opus 5, call 1 | headroom? |
|---|---|---|---|
| `document.md` | 8 | 8/8 | none |
| `document_long.md` | 20 | 20/20 (all 5 repeats) | none |

The overnight conclusion was that the honest fix was a much longer corpus — tens of
pages — where attention cannot cover everything. That is a real authoring job and
length alone had already shown weak returns: going from 8 to 20 defects moved
section Jaccard only 0.883 → 0.841.

**This takes a different route to the same goal. Length is not the only thing that
outruns a single pass; combinatorics is.**

Every seeded defect here is a contradiction between **two** of four documents.
Four documents give six pairs; the pairs to check grow quadratically while the
token count grows linearly. A model can read all four documents attentively and
still miss a conflict, because **no single document is wrong**.

## Contents

| file | document | ~lines |
|---|---|---|
| `01_msa.md` | Master Services Agreement | 190 |
| `02_sow.md` | Statement of Work 1 (Schedule 1) | 120 |
| `03_dpa.md` | Data Processing Addendum | 150 |
| `04_sla.md` | Service Level and Support Schedule (Schedule 2) | 115 |

~19,700 characters total. Ground truth: `../defects_xdoc.py`, **24 defects**, all
cross-document, graded obvious (9) / medium (9) / subtle (6).

## Design rules

1. **Every seeded defect spans two documents.** None can be found by reading one
   document in isolation. That is what makes this a different test rather than a
   longer one.
2. **Each document is internally consistent.** SOW phase durations sum to the
   stated 36-month programme; the team roster sums to the stated headcount of 11.
   So single-document reading yields nothing, and any within-document finding is a
   genuine bonus or matcher noise — counted and dumped either way, as the harness
   already does.
3. **Both sides of a conflict are accepted.** A model may report a numeric clash
   from either document's point of view.
4. **Distinctive fingerprints chosen at authoring time, not fitted to model
   output** — `Bengaluru`, `set-off`, `Annex 3`, `£250,000`, `99.9%`, `Saturday`,
   `SOC 2`. This is the methodological improvement `defects_long.py` introduced and
   it is kept deliberately.
5. **Plausible conflicts.** Each pair is the sort of drafting failure that occurs
   when a contract set is assembled from templates by different people — not
   absurd. An implausible conflict would be easy in a way that teaches nothing.

## The prompt tells the model the task is cross-document

`PROMPT_XDOC` in `run_w3.py` explicitly says to look for conflicts *between*
documents. That is deliberate: the headroom is supposed to come from the
combinatorics of checking six document pairs, not from concealing the assignment.
Hiding it would measure whether the model guesses what is being asked, which is a
different and less interesting question.

## The conflict map

Each row needs both documents to be held at once.

| defect | pair | the clash |
|---|---|---|
| X01 | MSA 4.1 · SOW 5.1 | monthly fee £12,400 vs £12,800 |
| X02 | MSA 3.1 · SOW 2.1 | 24-month term governs a 36-month programme |
| X03 | MSA 3.3 · SOW 2.3 | convenience notice 90 days vs 30 days |
| X04 | MSA 14.2 · SOW 1.2 | **circular precedence** — each prevails over the other |
| X05 | MSA 1.2 · SLA 1.1 | "Business Day" Mon–Fri/England vs Mon–Sat/US |
| X06 | MSA 11.1 · DPA 1.4 | confidentiality needs marking vs "whether or not marked" |
| X07 | DPA 1.6 · SLA 7.1 | "Security Incident" any access vs confirmed access + loss |
| X08 | DPA 6.1 · SLA 7.3 | incident notification 24h vs 72h |
| X09 | MSA 12.4 · DPA 8.2 | retain 7 years vs delete within 30 days |
| X10 | MSA 9.3 · DPA 5.1 | subcontract freely vs per-Subprocessor written consent |
| X11 | MSA 13.1 · SOW 9.2 | cap = 12 months' fees vs £250,000 |
| X12 | MSA 13.3 · DPA 11.1 | each disapplies the other's liability provision |
| X13 | SLA 3.1 · SOW 7.2 | availability 99.9% vs 99.5% |
| X14 | SLA 4.2 · SOW 7.4 | credits capped 10% vs 25% |
| X15 | MSA 4.5 · SLA 4.1 | credits applied automatically vs no set-off permitted |
| X16 | MSA 15.1 · DPA 13.2 | England and Wales vs Republic of Ireland |
| X17 | MSA 6.2 · SOW | points to "Schedule 1, Section 12"; SOW ends at 10 |
| X18 | SLA 7.4 · DPA | points to "Annex 3"; DPA has Annexes 1–2 |
| X19 | MSA date · SOW 2.2 | programme starts 1 March, MSA effective 1 April |
| X20 | MSA 4.3 · SOW 5.3 | payment 30 days vs 45 days |
| X21 | DPA 4.1 · SOW 3.4 | processing UK/EEA only vs delivery team in Bengaluru |
| X22 | MSA 10.2 · DPA 9.1 | SOC 2 report only, no audit vs annual on-site audit |
| X23 | MSA 6.1 · SOW 6.3 | express written acceptance vs deemed accepted in 5 days |
| X24 | MSA 16.1 · SOW 9.4 | PI insurance £5,000,000 vs £2,000,000 |

## Verify before spending

```bash
python experiments/w3_independence/corpus_xdoc/verify_corpus.py
```

Checks three things that would each masquerade as a result:

- **a rule that matches nothing** — recall understated, corpus looks harder than it
  is. Guarded by a hand-written exemplar finding per defect, phrased the way a
  reviewer would phrase it and deliberately *not* copied from the `desc` field.
- **a rule that matches everything** — cross-talk inflates recall. Each exemplar
  must match its own defect and only declared overlaps.
- **a defect not actually in the documents** — ground truth asserting a
  contradiction nobody wrote. Guarded by fingerprint presence checks per file.

It found a bug in itself on first run: the fingerprint check compared raw text, and
two phrases straddled a markdown line wrap, so it reported them absent from
documents that plainly contained them. Whitespace is now normalised. Worth
recording because the failure direction was "ground truth looks wrong", which is
the direction that wastes a run.

## Run

```bash
python run_w3.py --provider anthropic --model claude-opus-5 --doc xdoc --repeats 3
python run_w3.py --provider openai --model gpt-5.5 --doc xdoc --repeats 3
python run_w3.py --model qwen3:8b --doc xdoc --repeats 3
```

Section signatures use `XDOC_SECTION_RE`, which captures two-digit clause numbers
and document identity (`MSA`/`SOW`/`DPA`/`SLA`). `SECTION_RE` is left untouched:
changing it would silently alter the section-Jaccard figures already published for
`document.md` and `document_long.md`.

`--doc xdoc` also changes two defaults, both because the originals were actively
wrong for this corpus:

- `--max-output-tokens` → **24000**. At 8000 Opus 5 spent the whole budget thinking
  and returned no JSON at all, scoring 0/24 in 92 seconds. Above ~8192 the Anthropic
  SDK requires streaming, so the frontier path streams.
- `--num-ctx` → **8192** for Ollama. Its default context window is a few thousand
  tokens and it **truncates a longer prompt silently**, so at the default the local
  models would never have seen the last document or two, and "locals cannot do
  cross-document reasoning" would have been an artifact of the harness. 16384 was
  tried first and made `qwen3:8b` exceed a 600s timeout.

  **The reason for that timeout was originally recorded here as "KV cache pushed into
  swap on a 12GB box". That explanation was wrong** — the machine has 47.8 GB of RAM
  and `qwen3:8b` loads entirely into VRAM (9.8 GB per Ollama's `/api/ps`). The 12 GB
  figure was carried over from this repo's README, which describes the *target* class
  of hardware for the local models, not the machine these runs happened on. The actual
  cause of the timeout is not established; it is GPU-side rather than swap. Recorded as
  unexplained rather than left with a plausible-sounding wrong reason attached.

## Result: it did NOT create headroom against Opus 5

**Opus 5 scored 24/24 on the first call.** So the combinatorial route failed at this
scale, and this is the third failed attempt at a task beyond Opus's single pass. The
honest verdict is a negative result about the method, not about the corpus's
construction — the conflicts are real and it found all of them.

It also surfaced ~20 unseeded real defects, several of them worth having: the DPA
carries a `PRECEDENCE` heading with no precedence rule under it; MSA 12.2 makes
records available "in accordance with clause 10.2" while 10.2 *removes* the
inspection right; SLA 5.4 starts the response clock at the Provider's own
acknowledgement, so the 15-minute target measures nothing.

Where the corpus earns its keep is the **width of its headroom range**, which is what
testing the W3 headroom claim needs:

| model | best single /24 | union k=8 | union − best single | defect Jaccard |
|---|---|---|---|---|
| `claude-opus-5` | 24 (single call) | 24 | 0 | — |
| `gpt-5.5` (n=3) | 22.67 ± 0.58 | 23.33 ± 1.15 | 0.67 | 0.970 |
| `qwen3:8b` (n=2) | 13.00 ± 0.00 | 17.50 ± 0.71 | **4.50** | 0.27 |
| `qwen2.5:3b` (n=3) | 4.67 ± 0.58 | 7.67 ± 0.58 | 3.00 | **0.15** |

Four models, one task, and what extra calls buy tracks how much a single pass misses.
`qwen2.5:3b`'s Jaccard of 0.15 is the lowest in the W3 programme: on a task far
beyond one pass, eight independent calls genuinely find different defects. Note the
gain is **not** monotone in headroom — `qwen3:8b` recovers more than the 3B despite
reaching further per call. Full discussion in `../FINDINGS.md`.

The corpus also produced the clearest separation yet between *where* calls look and
*what* they find: `gpt-5.5`'s section-signature union rises 42 → 75 clause references
across eight calls (+79% breadth, section Jaccard 0.547) while its defect-set Jaccard
is 0.970 and it gains 0.67 defects. Different places, same findings.

⚠ Section-signature figures produced before the `XDOC_SECTION_RE` fix are invalid — a
capturing group made `re.findall` discard every clause number, collapsing each
signature to the four document names (`sections_union` 4.00, Jaccard exactly 1.000).
Use `../recompute_sections.py`, which re-derives them from the stored findings with no
new API calls.

**Next step, now done:** `../corpus_xdoc_ext/` adds five more documents, taking the set
to **nine documents / 36 pairs / 52 defects** via `--doc xdoc9`. **It creates the
headroom this corpus could not: Opus 5 scores 49/52 on the first call**, missing three
defects, where here it scores 24/24. The pair count squaring for a linear authoring
cost is exactly the mechanism that worked.

This directory is deliberately **unchanged** by that work — `--doc xdoc` still sends
exactly these four documents, so the 24-defect figures above stay reproducible. The
cost is a visible seam in the nine-document set: these four are headed "DOCUMENT n
of 4", and Opus notices.
