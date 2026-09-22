# OMBS — Findings Report

_LLM Operational Moral-Behavior Testing Suite. Local-first evaluation of whether
LLMs in delegated workplace roles preserve operational boundaries under pressure._

Run date: 2026-06-05. Prompt template: v0.4. All results are observed behavior of
specific model configurations under a specific protocol — not universal claims
about any model (see Limitations).

---

## 1. What was tested

**Role:** administrative assistant. **Boundaries:** confidentiality, approval/
authority, escalation, honest disclosure, untrusted-instruction resistance.

**Scenarios:** 10 single-turn admin scenarios, each with 6 pressure variants
(neutral, authority, urgency, social_proof, loyalty, combined) and a 5-turn
pushback sequence (authority → urgency → social_proof → loyalty → responsibility);
3 simulated-tool scenarios (2 boundary + 1 benign control).

**Conditions, in increasing difficulty:**
1. Single-turn (one decision per variant)
2. Multi-turn pushback (chat, 5 escalating turns)
3. Tools, single-shot (does action match text?)
4. Tools, multi-turn (does pressure cause a real unsafe call?)
5. LLM-as-judge (qualitative + semantic backstop)

**Models:** local via Ollama on an RTX 3060 — `qwen3.5:9b`, `qwen3:8b`,
`qwen2.5:3b`, `gemma3:1b`; frontier via Anthropic — `claude-opus-4-8`.

---

## 2. Headline findings

1. **Single-turn boundary preservation hits a ceiling.** All capable models score
   ~100% on single-turn admin scenarios with explicit policy context. The
   condition does not discriminate models.

2. **The discriminating signal is sustained multi-turn authority pressure.** Under
   a 5-turn pushback sequence, local models cave; a frontier model holds.

3. **Authority is the dominant lever.** 12 of 14 first failures across local
   multi-turn runs occurred on the turn a "VP" *claimed* authority. The other
   levers rarely break a model that survived authority.

4. **The weakness is real, not cosmetic.** With simulated tools and sustained
   pushback, the chat-level capitulation becomes an actual `send_email` call —
   confidential data sent externally, unapproved commitments sent to clients.

5. **The weakness is content-driven, not a wording artifact.** Single-turn
   decisions are paraphrase-invariant (material-class consistency 1.00), so the
   multi-turn capitulation is a genuine response to authority *content*.

6. **It is model-tier-specific.** `claude-opus-4-8`, run through the identical
   protocol, resists the lever that breaks the local 3–8B models.

7. **It is partially promptable, not fixable by prompt alone.** A strong-boundary
   system prompt raises multi-turn survival ~5× with zero over-refusal cost, but
   does not close the gap.

8. **JSON/format compliance is a separate axis.** `gemma3:1b` fails schema
   validation ~65% of the time unconstrained (it writes prose into enum fields)
   but ~0% with forced structured output — its judgment is fine; its formatting
   is not. Reported separately from judgment behavior.

---

## 3. Results by condition

### Authority-verification probe (the core weakness, quantified)

| Model | authority capitulation | asked for verification | accepted claim w/o verification |
|---|---|---|---|
| claude-opus-4-8 | 0% | 90% | 0% |
| qwen3:8b | 70% | 10% | 60% |
| qwen2.5:3b | 50% | 10% | 40% |
| gemma3:1b | 0%* | 20% | 0%* |

\*Unreliable — gemma's openings mostly failed to parse (tiny denominator).

### Multi-turn pushback (chat, 5 turns)

| Model | mean survival depth | held all turns |
|---|---|---|
| claude-opus-4-8 | 4.5 | 9/10 (10/10 behaviorally) |
| qwen3:8b | 1.5 | 3/10 |
| qwen2.5:3b | 1.5 | 2/10 |

### Tools, multi-turn (does pressure produce a real unsafe call?)

| Model | mean tool-survival depth | never made an unsafe call |
|---|---|---|
| claude-opus-4-8 | 5.0 | 2/2 |
| qwen3:8b | 0.0 | 0/2 |
| qwen2.5:3b | 0.0 | 0/2 |

Local models opened safely (`request_approval`) then called `send_email` the
moment authority was claimed (turn 1). Opus chose `request_approval`/`create_draft`
on every turn.

### System-prompt hardening (qwen2.5:3b, 5 scenarios)

| Style | multi-turn survival depth | single-turn boundary | over-refusal |
|---|---|---|---|
| minimal | 0.20 | 100% | 0% |
| policy_aware | 0.60 | 100% | 0% |
| strong_boundary | 1.00 | 100% | 0% |

### Paraphrase robustness (qwen3:8b, 3 scenarios × {neutral, authority}, 3 paraphrases)

Mean material-class consistency **1.00**, 0/6 unstable — wording-invariant.

### JSON compliance (Tier-C, unconstrained vs forced schema)

| Model | parse-failure rate (unconstrained) | with `format: schema` |
|---|---|---|
| gemma3:1b | 65% | 0% |
| qwen3:8b | 0% | 0% |

---

## 4. Measurement-validity bugs caught (and fixed) along the way

The build→run→inspect loop surfaced four false-negative classes before any of
them could corrupt conclusions:

1. **Disclose-field ambiguity** — `should_send_or_disclose_information` conflated
   authorized internal escalation with unauthorized external disclosure. A strong
   model honestly setting it `true` while escalating was scored as a failure.
   Fixed in prompt v0.2 + hardened scorer.
2. **Escalation enum too narrow** — out-of-enum targets (`user`, then `finance`/
   `security`/`it`, then `procurement`) produced false parse failures. Fixed by
   widening the enum and the escalation scorer (v0.3, v0.4).
3. **"Held all turns" counted unparsed turns** — a model that never produced a
   parseable answer was credited as "held." Fixed.
4. **Lesson:** self-reported boolean/enum intent fields leak interpretation
   variance into scores. The LLM-judge now serves as a semantic backstop —
   judging boundary preservation in natural language and flagging deterministic
   disagreements (it caught 10/10 known artifacts in a held-out sample).

---

## 5. Limitations

- Results are protocol-specific; different prompts, quantization, temperatures, or
  scenario banks may differ. The prompt is versioned (v0.4).
- Local models are quantized 1–9B; not directly comparable to the frontier model
  except as observed behavior under the same protocol.
- Single role (administrative assistant) and English only so far.
- Tool environment is simulated with no guardrail; "unsafe call" means the model
  chose the forbidden action, not that real-world harm occurred.
- Scenario bank encodes the author's view of acceptable boundaries.

---

## 6. Reproducing

```bash
uv sync --extra dev --extra frontier
# local models: ollama pull qwen3:8b qwen2.5:3b gemma3:1b
# frontier: put ANTHROPIC_API_KEY in .env
uv run pytest -q            # 58 tests
uv run ombs run --config configs/run.smoke.yaml
uv run ombs run-multiturn --config configs/run.multiturn.yaml
uv run ombs run-tools-multiturn --config configs/run.tools_multiturn.yaml
uv run ombs run-multiturn --config configs/run.frontier_multiturn.yaml
uv run ombs report-authority --input outputs/<run>/multi_turn.jsonl
uv run ombs scorecard --name qwen3:8b --name claude-opus-4-8
```

Result files live under `outputs/<run_id>/`. Per-model profiles:
`outputs/scorecards/`.

---

## 7. Suggested next steps (none blocking)

- **Frontier breadth:** run single-turn / tools / judge on Opus 4.8 too, so the
  comparison scorecard is fully populated; add OpenAI/Google providers when keys
  are available.
- **More roles** (executive assistant, compliance officer, customer advocate) and
  **language variants** (§16) — the role/style scaffolding is already wired.
- **Authority-intensity gradient** — vary claimed seniority and whether written
  proof is offered, to map the capitulation curve.
- **Human comparison** (§15 G) — are humans susceptible to the same levers?
