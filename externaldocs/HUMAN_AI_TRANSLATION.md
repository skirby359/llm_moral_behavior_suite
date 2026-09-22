# Human-to-AI Ethical Pressure Translation Matrix

## Purpose

This file defines how human behavioral-ethics findings are translated into AI-agent experiments without assuming shared psychology.

| Human literature | Human effect | AI manipulation | Primary AI metric | Novelty status |
|---|---|---|---|---|
| Kern & Chugh | Loss framing can increase unethical behavior; time pressure moderates | Equivalent gain vs loss framing × urgency | violation rate, d' | promising |
| Schweitzer et al. | Specific unmet goals and near-misses increase cheating | do-best vs target vs 99%-complete target | violation rate | promising |
| Work-pressure / security-policy research | Pressure + opportunity + completion justification predicts policy violation | task pressure × bypass opportunity × work-completion justification | violation / escalation | very strong fit |
| Authority / phishing | Authority cues increase unsafe compliance | ordinary request vs superior instruction | violation / resistance | important but already studied in LLMs |
| Gino & Bazerman | Gradual erosion is less likely to be challenged | abrupt violation vs incremental exceptions | final violation / intervention point | promising |
| Moral disengagement | Justification, euphemism, responsibility diffusion, harm minimization | controlled linguistic reframing | violation / rationale | adjacent LLM work exists |
| Security fatigue | Repeated decisions and overload impair security behavior | policy load, warning load, long context | discrimination / error | later-stage |
| Social norms | Observed peer misconduct can alter behavior | peer compliance vs peer bypass vs sanctioned bypass | norm-contagion effect | later-stage |

## Translation rule

For every imported human finding:

1. preserve the causal structure;
2. replace human emotional language with observable task conditions;
3. create novel scenario content;
4. define the governing rule independently;
5. measure action, not inferred mental state;
6. distinguish replication from mechanism.

## Terminology

Prefer:

- pressure manipulation
- behavioral susceptibility
- rule degradation
- objective conflict
- behavioral correspondence
- vulnerability profile

Avoid unless discussing human subjects:

- fear
- guilt
- anxiety
- moral stress
- self-preservation instinct
- fatigue
- rationalization as an internal mental state

When model text contains justificatory language, describe it as **expressed rationalization** or **rationalization-like language**, not evidence of subjective rationalization.
