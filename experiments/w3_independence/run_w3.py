"""W3 — does session amnesia buy real independence, or N samples from one attractor?

The wager: N fresh sessions over one input produce genuinely *different* findings.
Every "run it N times independently" pattern depends on it -- two-direction
synthesis checks, run-1/run-2 label swaps, and adversarial verify-with-N-skeptics.

Design
------
PARALLEL   : K independent calls, fresh context each, identical prompt.
SEQUENTIAL : one conversation asked K times ("any more?"), context accumulating.
             The control -- if accumulation beats amnesia, parallelism is the
             wrong primitive.

temperature 0.0 is a positive control for convergence: outputs should collapse
onto near-identical findings. A metric that does NOT show high overlap at temp 0
is broken, and its temp-0.8 numbers cannot be trusted.

Ground truth is 8 seeded defects in document.md, matched by hand-authored regex.
Unmatched findings are counted and dumped so matcher loss is auditable rather
than invisible.

Usage
-----
    python run_w3.py --smoke              # 1 call, timing check
    python run_w3.py                      # full run
    python run_w3.py --model qwen2.5:3b
    python run_w3.py --provider openai --model gpt-5.5 --doc long --repeats 5

Spend is capped in code -- cumulatively, across invocations, via
outputs/spend_ledger.jsonl -- plus a hard --max-calls backstop. See the guards
section below.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import os
import sys
import time
import urllib.error
import urllib.request
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent.parent
OLLAMA = "http://localhost:11434"

# The rate card and the spend guard live in ONE place -- src/ombs/utils/budget.py.
# This script predates that module and stays runnable standalone (`python
# run_w3.py`), so it puts src/ on the path rather than keeping a second copy of
# the prices. A duplicated price is a price that goes stale, and this file already
# carried a pessimistic gpt-5.5 placeholder that outlived the real figure being
# known.
sys.path.insert(0, str(REPO_ROOT / "src"))
from ombs.utils.budget import (  # noqa: E402
    PRICING,
    BudgetExceeded,
    BudgetGuard,
)
from ombs.utils.budget import call_cost as _shared_call_cost  # noqa: E402

PROMPT = """Review the document below and list every defect you can find.

Look for: internal contradictions, arithmetic errors, broken cross-references,
undefined terms, circular definitions, and logical gaps.

Return JSON only, in this shape:
{{"findings": [{{"issue": "<what is wrong>", "location": "<section number>"}}]}}

DOCUMENT:
{document}
"""

FOLLOWUP = "Any further defects you have not already listed? Same JSON shape."

# Prompt for the cross-document corpus (--doc xdoc). Every seeded defect there is a
# conflict BETWEEN documents, so the instruction says so explicitly.
#
# That is a deliberate choice and worth defending: the headroom this corpus is
# meant to create must come from the COMBINATORICS of checking six document pairs,
# not from concealing what the task is. Hiding the cross-document nature would
# measure whether the model guesses the assignment, which is a different and less
# interesting question. `location` asks for a document name so a finding can be
# attributed, and the section-signature metric still works over it.
PROMPT_XDOC = """The following four documents form a single contract set. Review them
together and list every defect you can find.

Look in particular for conflicts BETWEEN documents: the same term defined two
different ways, incompatible numbers or dates, obligations that cannot both be
satisfied, references to sections or annexes that do not exist, and circular
precedence. Also report any defect internal to a single document.

Return JSON only, in this shape:
{{"findings": [{{"issue": "<what is wrong>", "location": "<document and section>"}}]}}

DOCUMENTS:
{document}
"""

# Set by main() according to --doc. Defaults to the single-document prompt so
# importing this module (as the tests and the smoke path do) behaves as before.
_PROMPT = PROMPT

# Enforced output shape for the Anthropic path, so parsing is guaranteed rather
# than prompt-dependent. Matches Ollama's `format: "json"` so the two providers
# are compared under the same output constraint.
FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "issue": {"type": "string"},
                    "location": {"type": "string"},
                },
                "required": ["issue", "location"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}

# Prices: see PRICING in src/ombs/utils/budget.py, which is the single source of
# truth and carries the provenance for each figure. gpt-5.5 is now the VERIFIED
# $5.00 in / $0.50 cached / $30.00 out, replacing the pessimistic $15/$60
# placeholder this file used to carry while the real price was unknown --
# so cost figures for gpt-5.5 are no longer upper bounds, they are the price.
# Local Ollama models remain unpriced: token counts only, and NOT covered by the
# spend cap (they are free; the call cap below covers them instead).

# This script's own usage-dict shape, kept unchanged so previously written
# results_*.json / variance_*.json artifacts stay comparable key-for-key.
EMPTY_USAGE = {
    "input_tokens": 0,
    "output_tokens": 0,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
}


def call_cost(model: str, usage: dict) -> float | None:
    """USD for one call. None for models with no published per-token price.

    Translates this script's usage keys onto the shared module's, so there is one
    pricing implementation rather than two that can drift.
    """
    return _shared_call_cost(
        model,
        {
            "input_tokens": usage["input_tokens"],
            "cached_input_tokens": usage["cache_read_input_tokens"],
            "cache_write_tokens": usage["cache_creation_input_tokens"],
            "output_tokens": usage["output_tokens"],
        },
    )


# --------------------------------------------------------------------------- #
# Two enforced ceilings, because they cover different failure modes.
#
# 1. SPEND (BudgetGuard, ledger-backed): protects a finite prepaid balance. It is
#    CUMULATIVE ACROSS INVOCATIONS via outputs/spend_ledger.jsonl -- a per-run cap
#    would not protect a $30 balance, since twenty runs each safely under a
#    per-run limit still drains it. Covers only models present in PRICING.
# 2. CALL COUNT (--max-calls): the backstop for everything spend cannot see --
#    an unpriced model, a mispriced one, or a runaway loop. This is what the prior
#    session recommended for GPT while its price was unknown; it is kept now that
#    the price is known, because the reasons it was needed have not all gone away.
#
# Both can overshoot by at most one call: output length is unknown until the
# response arrives.
# --------------------------------------------------------------------------- #

_GUARD: BudgetGuard | None = None
_CALLS = 0
MAX_CALLS = 400

# Output-token budget for the frontier paths. On Anthropic this caps thinking +
# visible output together; on OpenAI it is max_completion_tokens, which caps
# reasoning + visible output. 8000 was the original value and is ample for the
# single-document tasks; the 24-defect cross-document corpus overruns it.
MAX_OUTPUT_TOKENS = 8000

# Ollama context window. None = leave Ollama's default alone (see call_ollama for
# why that default is dangerous on a long prompt).
NUM_CTX: int | None = None

# Ollama generation cap. None = Ollama's default, which is unbounded up to the context
# window -- see call_ollama. The frontier paths have always been capped; this is the
# equivalent, and it matters as soon as num_ctx is large.
NUM_PREDICT: int | None = None

# Per-call wall-clock ceiling for the frontier paths. A stalled request is worse
# than a failed one: results are only written when the whole run finishes, so a
# single hung call discards every completed repeat's analysis with it.
CALL_TIMEOUT_SECONDS = 900


class CallCapExceeded(RuntimeError):
    pass


def init_guards(run_id: str, max_calls: int) -> None:
    global _GUARD, MAX_CALLS
    cap_env = os.environ.get("W3_BUDGET_USD") or os.environ.get("OMBS_BUDGET_USD")
    _GUARD = BudgetGuard(
        run_id=run_id,
        cap_usd=float(cap_env) if cap_env else None,
        # Absolute: this script is run from its own directory, so a relative
        # "outputs/" would silently start a second, separate ledger.
        ledger_path=REPO_ROOT / "outputs" / "spend_ledger.jsonl",
    )
    MAX_CALLS = max_calls
    print(
        f"[budget] cap ${_GUARD.cap_usd:.2f} cumulative, "
        f"${_GUARD.spent_before:.4f} already on the ledger, "
        f"${_GUARD.remaining():.4f} remaining; call cap {MAX_CALLS}"
    )


def _charge(model: str, usage: dict) -> None:
    global _CALLS
    _CALLS += 1
    if _CALLS > MAX_CALLS:
        raise CallCapExceeded(
            f"{_CALLS} calls exceeds the --max-calls bound of {MAX_CALLS} -- aborting. "
            "This is the backstop for models the spend cap cannot price."
        )
    if _GUARD is None:  # --smoke and direct imports run without init_guards
        return
    _GUARD.check_before_call(model)
    _GUARD.charge(
        model,
        {
            "input_tokens": usage["input_tokens"],
            "cached_input_tokens": usage["cache_read_input_tokens"],
            "cache_write_tokens": usage["cache_creation_input_tokens"],
            "output_tokens": usage["output_tokens"],
        },
    )


def spent_so_far() -> float:
    return _GUARD.spent_this_run if _GUARD else 0.0


# Repo .env holds ANTHROPIC_API_KEY. Loaded into os.environ without echoing.
ENV_FILE = HERE.parent.parent / ".env"


def load_env() -> None:
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

# --------------------------------------------------------------------------- #
# Ground truth: 8 seeded defects, graded by subtlety.
#
# `rules` is a list of alternative conjunctions: a finding matches a defect when
# EVERY regex in ANY ONE inner list hits. Two smoke-test failures drove this shape.
# Single loose patterns cross-credited (a bare `qualifying receipt` matched D3 on
# findings unrelated to circularity), so each rule pairs a topic anchor with the
# defect-specific tell. And one defect can be articulated several ways -- the same
# problem reported by citation or by symptom -- so alternatives are needed to avoid
# discarding real hits.
#
# CAVEAT: these patterns were tuned against smoke output, which risks overfitting
# to one sample. `unmatched_finding_count` and the dumped unmatched text are the
# guard: if they are large, recall here is understated.
# --------------------------------------------------------------------------- #

DEFECTS = [
    {
        "id": "D1_meal_arithmetic",
        "grade": "obvious",
        "desc": "2.2 says $145 for a three-day trip; $45/day x 3 = $135",
        "rules": [[r"\b(145|135)\b"]],
    },
    {
        "id": "D2_approval_contradiction",
        "grade": "medium",
        "desc": "Section 3 approval rules are mutually incoherent "
                "(3.2 Finance for >=$500 vs 3.3 manager only for >$500; "
                "3.1/3.3 also collide at the $500 boundary)",
        # Any section-3 reference (or the dollar figure) plus contradiction language.
        # Smoke run cited 3.1/3.3 rather than 3.2/3.3, so anchoring on 3.2 alone
        # discarded a real hit.
        "rules": [[
            r"(\b3\.[123]\b|section 3\b|\$?500)",
            r"(contradict|conflict|inconsist|incoherent|overlap|only|ambiguous|not (explicitly )?addressed)",
        ]],
    },
    {
        "id": "D3_circular_definition",
        "grade": "medium",
        "desc": "5.1 defines Qualifying Receipt as a receipt that qualifies",
        "rules": [[
            r"(qualifying receipt|\b5\.1\b)",
            r"(circular|tautolog|defines? itself|self-referential|no (real|substantive) definition|does not define|vacuous)",
        ]],
    },
    {
        "id": "D4_dead_crossref",
        "grade": "medium",
        "desc": "5.2 points to Section 7; document ends at Section 6",
        # Two articulations of the same defect. Smoke run reported it as
        # "'Covered Employee' referenced but not defined" without ever naming
        # Section 7 -- the defect identified, the citation elided.
        "rules": [
            [r"(section 7|sec\.? ?7|§ ?7)"],
            [r"(covered employee|\b5\.2\b)",
             r"(undefined|not defined|never defined|no definition|missing definition)"],
        ],
    },
    {
        "id": "D5_undefined_reviewer",
        "grade": "subtle",
        "desc": "4.2 relies on 'the reviewer', never defined",
        "rules": [[
            r"reviewer",
            r"(undefined|not defined|unspecified|unclear|ambiguous|who\b|vague|no definition)",
        ]],
    },
    {
        "id": "D6_supersession_clash",
        "grade": "subtle",
        "desc": "4.3 keeps rev 2 governing post-Feb-28 reports, but rev 3 "
                "supersedes rev 2 from March 1",
        "rules": [[
            r"(rev\.? ?2|revision 2|supersed)",
            r"(contradict|conflict|inconsist|march 1|february 28|feb\.? ?28|effective|governed)",
        ]],
    },
    {
        "id": "D7_missing_appendix",
        "grade": "medium",
        "desc": "6.1 references Appendix B; no appendix is present",
        "rules": [[r"appendix"]],
    },
    {
        "id": "D8_no_cap_exception",
        "grade": "subtle",
        "desc": "No process for exceeding the lodging cap; Section 6 EXCEPTIONS "
                "covers only international travel",
        "rules": [[
            r"(lodging|\b210\b|\b2\.3\b)",
            r"(exceed|exception|no process|no procedure|over the cap|above the cap|waiver)",
        ]],
    },
]


def call_ollama(model: str, messages: list[dict], temperature: float) -> tuple[str, float, dict]:
    """One /api/chat call. Returns (content, seconds).

    ``NUM_CTX`` matters more than it looks. Ollama's default context window is a
    few thousand tokens and it **truncates a longer prompt silently** -- the model
    simply never sees the tail of the input, and the run still returns a confident
    answer. The cross-document corpus is ~5k tokens, so at the default the last
    document or two would be invisible and the resulting "the locals cannot find
    cross-document conflicts" would be an artifact of the harness, not a finding.

    Left at None for the short and long documents so the figures already published
    for those remain exactly reproducible.

    ``NUM_PREDICT`` closes a real gap: Ollama's default generation limit is unbounded
    up to the context window, so at ``num_ctx=32768`` with a ~12k-token prompt a model
    could emit ~20k tokens before stopping. Both frontier paths have always had an
    output cap (``max_tokens`` / ``max_completion_tokens``); this one did not.

    **It is NOT established that this is what fixed the fourteen-minute call.**
    `qwen3:8b` did spend ~14 minutes on its first xdoc15 call and then tripped the 900s
    timeout, and adding the cap coincided with calls dropping to ~48s -- but the call
    that succeeded generated only 1,471 tokens, far below the 4,096 cap, so the cap was
    not binding on it. The likelier explanation is a cold load: Ollama reloads a model
    when ``num_ctx`` changes, and that first call paid for the reload plus a 12k-token
    prompt evaluation at a new context size. Kept because an unbounded generation limit
    is worth closing on its own merits, not because it is the proven fix.

    Also left at None for the short and long documents.
    """
    options = {"temperature": temperature}
    if NUM_CTX:
        options["num_ctx"] = NUM_CTX
    if NUM_PREDICT:
        options["num_predict"] = NUM_PREDICT
    body = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "think": False,  # qwen3 emits <think> blocks otherwise
        "options": options,
    }
    req = urllib.request.Request(
        f"{OLLAMA}/api/chat",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=CALL_TIMEOUT_SECONDS) as resp:
        payload = json.loads(resp.read())
    usage = dict(EMPTY_USAGE)
    usage["input_tokens"] = payload.get("prompt_eval_count", 0) or 0
    usage["output_tokens"] = payload.get("eval_count", 0) or 0

    # TRUNCATION MUST NOT BE SCORED AS "FOUND NOTHING" -- on this path either.
    # Ollama reports done_reason "length" when it stops at num_predict. The JSON body
    # is then cut off mid-structure, `parse_findings` gets a JSONDecodeError and
    # returns [], and the call scores as zero defects. Measured before this check
    # existed: 9 of 16 `qwen3:8b` calls on the 15-document corpus hit exactly
    # num_predict=4096 and every one was recorded as finding nothing, dragging its
    # mean per-call recall to 2.50 while its best completing call found 13.
    #
    # This is the same defect already fixed on both frontier paths, reintroduced here
    # by the cap added to stop unbounded generation. A cap without truncation
    # detection just converts a visible hang into an invisible zero.
    if payload.get("done_reason") == "length":
        print(f"    !! TRUNCATED at num_predict={NUM_PREDICT} "
              f"({usage['output_tokens']} output tokens) -- this call is NOT a "
              "measurement. Raise --num-predict, and treat runs with truncated calls "
              "as invalid.")
        return json.dumps({"findings": [], "_truncated": True}), time.time() - t0, usage

    return payload["message"]["content"], time.time() - t0, usage


def call_anthropic(model: str, messages: list[dict], temperature: float) -> tuple[str, float, dict]:
    """One Messages API call. `temperature` is ACCEPTED AND IGNORED.

    Opus 5 / 4.8 / 4.7 reject temperature/top_p/top_k with a 400, so the
    frontier path cannot run the temp-0.0 convergence control that validates the
    metric on Ollama. The scoring code is identical across providers, so that
    control transfers -- but it is not re-established here. Thinking is on by
    default on Opus 5; max_tokens caps thinking + response text together.
    """
    import anthropic  # imported lazily so the Ollama path needs no SDK

    global _CLIENT
    if _CLIENT is None:
        load_env()
        _CLIENT = anthropic.Anthropic()

    kwargs = dict(
        model=model,
        max_tokens=MAX_OUTPUT_TOKENS,
        output_config={"format": {"type": "json_schema", "schema": FINDINGS_SCHEMA}},
        messages=messages,
    )
    t0 = time.time()
    # The SDK refuses a non-streaming request whose max_tokens implies a >10 minute
    # response ("Streaming is required for operations that may take longer than 10
    # minutes"), which the cross-document corpus's 24000-token budget trips. Stream
    # above the threshold and collect the final message, so the token budget is set
    # by what the task needs rather than by what non-streaming tolerates.
    if MAX_OUTPUT_TOKENS > 8192:
        with _CLIENT.messages.stream(**kwargs) as stream:
            resp = stream.get_final_message()
    else:
        resp = _CLIENT.messages.create(**kwargs)
    secs = time.time() - t0

    # Opus 5 runs safety classifiers; a decline is HTTP 200 with empty/partial
    # content, so stop_reason must be checked before reading content.
    u = resp.usage
    usage = {
        "input_tokens": u.input_tokens or 0,
        "output_tokens": u.output_tokens or 0,  # includes thinking tokens
        "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
    }

    if resp.stop_reason == "refusal":
        return json.dumps({"findings": [], "_refusal": True}), secs, usage

    # TRUNCATION MUST NOT BE SCORED AS "FOUND NOTHING". Opus 5 has thinking on by
    # default and max_tokens caps thinking + output together, so a large corpus can
    # consume the whole budget before any JSON is emitted. The first cross-document
    # smoke run did exactly that and reported 0/24 defects in 92 seconds -- which
    # would have read as "the corpus is brutally hard" rather than "the answer never
    # arrived". Loud, and flagged in the payload.
    if resp.stop_reason == "max_tokens":
        print(f"    !! TRUNCATED at max_tokens={MAX_OUTPUT_TOKENS} "
              f"({usage['output_tokens']} output tokens) -- raise --max-output-tokens. "
              "This call is NOT a measurement.")
        return json.dumps({"findings": [], "_truncated": True}), secs, usage

    text = next((b.text for b in resp.content if b.type == "text"), "")
    return text, secs, usage


_CLIENT = None
_OAI_CLIENT = None


def call_openai(model: str, messages: list[dict], temperature: float) -> tuple[str, float, dict]:
    """One Chat Completions call. `temperature` is ACCEPTED AND IGNORED.

    PROBED 2026-08-04 against gpt-5.5 (resolves to gpt-5.5-2026-04-23) rather
    than assumed:
      - `temperature=0` -> HTTP 400, "Only the default (1) value is supported";
        `top_p` -> 400. So gpt-5.5, EXACTLY LIKE OPUS 5, cannot run the temp-0.0
        convergence positive control that validates this metric on Ollama. That
        limitation is therefore a property of both frontier vendors, not an
        Anthropic quirk -- worth stating because the control is what licenses
        trusting the temp-0.8 numbers.
      - `max_tokens` -> 400; `max_completion_tokens` is the parameter, and it caps
        REASONING + visible output together (reasoning_tokens is reported
        separately below and is included in completion_tokens).
      - `response_format` json_schema strict works, so the output shape is
        enforced rather than prompt-dependent -- matching what the Anthropic path
        does with output_config, so the two frontier providers are compared under
        the same output constraint.
    """
    import openai  # imported lazily so the Ollama path needs no SDK

    global _OAI_CLIENT
    if _OAI_CLIENT is None:
        load_env()
        _OAI_CLIENT = openai.OpenAI()

    t0 = time.time()
    resp = _OAI_CLIENT.chat.completions.create(
        model=model,
        # Explicit, because there was no bound here at all: the SDK default plus
        # its automatic retries can stack well past 20 minutes on one call.
        # Observed on the cross-document corpus: a single request took ~25 minutes
        # and then completed normally. Nothing was hung, which is precisely why a
        # ceiling is worth setting — an unbounded call is indistinguishable from a
        # hung one while you wait, and results are only written when the whole run
        # finishes. `providers/openai.py` already passes a timeout; this path did not.
        timeout=CALL_TIMEOUT_SECONDS,
        max_completion_tokens=MAX_OUTPUT_TOKENS,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "findings", "schema": FINDINGS_SCHEMA, "strict": True},
        },
        messages=messages,
    )
    secs = time.time() - t0

    u = resp.usage
    details = getattr(u, "prompt_tokens_details", None)
    cached = (getattr(details, "cached_tokens", 0) or 0) if details else 0
    usage = dict(EMPTY_USAGE)
    # input_tokens excludes the cache-hit subset so the two price separately
    # without double-counting. OpenAI does not bill cache writes at all.
    usage["input_tokens"] = max((u.prompt_tokens or 0) - cached, 0)
    usage["cache_read_input_tokens"] = cached
    usage["output_tokens"] = u.completion_tokens or 0  # includes reasoning tokens

    choice = resp.choices[0]
    if getattr(choice.message, "refusal", None):
        return json.dumps({"findings": [], "_refusal": True}), secs, usage
    if choice.finish_reason == "length":
        # A reasoning model can spend the whole budget thinking and return
        # nothing. Flagged rather than silently scored as "found no defects".
        print(f"    !! TRUNCATED at max_completion_tokens={MAX_OUTPUT_TOKENS} "
              f"({usage['output_tokens']} output tokens) -- raise --max-output-tokens. "
              "This call is NOT a measurement.")
        return json.dumps({"findings": [], "_truncated": True}), secs, usage
    return choice.message.content or "", secs, usage


def call_model(provider: str, model: str, messages: list[dict], temperature: float) -> tuple[str, float, dict]:
    if provider == "anthropic":
        text, secs, usage = call_anthropic(model, messages, temperature)
    elif provider == "openai":
        text, secs, usage = call_openai(model, messages, temperature)
    else:
        text, secs, usage = call_ollama(model, messages, temperature)
    _charge(model, usage)  # aborts the run if either cap is crossed
    return text, secs, usage


def is_failed_call(raw: str) -> str | None:
    """Was this call a non-measurement? Returns the reason, or None.

    Three cases must never be read as "the model found no defects":
    truncation (any provider), a safety refusal, and a JSON body that does not
    parse. All three previously landed as a silent zero.
    """
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return "unparseable_json"
    if not isinstance(obj, (dict, list)):
        return "unparseable_json"
    if isinstance(obj, dict):
        if obj.get("_truncated"):
            return "truncated"
        if obj.get("_refusal"):
            return "refusal"
    return None


def parse_findings(raw: str) -> list[str]:
    """Extract finding strings. Tolerant: the shape varies across models."""
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return []
    items = obj.get("findings", obj if isinstance(obj, list) else [])
    out = []
    for it in items if isinstance(items, list) else []:
        if isinstance(it, str):
            out.append(it)
        elif isinstance(it, dict):
            out.append(" ".join(str(v) for v in it.values()))
    return [s.strip() for s in out if s and s.strip()]


def match_defects(findings: list[str]) -> tuple[set[str], list[str]]:
    """Map findings onto seeded defect ids. Returns (matched_ids, unmatched)."""
    matched: set[str] = set()
    unmatched: list[str] = []
    for f in findings:
        low = f.lower()
        hits = {
            d["id"] for d in DEFECTS
            if any(all(re.search(p, low) for p in rule) for rule in d["rules"])
        }
        if hits:
            matched |= hits
        else:
            unmatched.append(f)
    return matched, unmatched


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


# Ground-truth-free diversity. The 8 seeded defects are a CEILING that a strong
# model exceeds -- Opus 5 scored 7/8 in a single smoke call and surfaced six
# further real defects that were never seeded. Against that ceiling, defect-set
# Jaccard saturates at ~1.0 for reasons that have nothing to do with an attractor,
# so it cannot answer W3 on a capable model.
#
# Section signatures measure where each call LOOKED, independent of the seed set:
# a finding about clause 4.2 cites "4.2" however it is worded. Diversity in the
# space beyond the ground truth shows up here and nowhere else.
SECTION_RE = re.compile(r"\b\d\.\d\b|\bsection\s+\d\b", re.IGNORECASE)

# The cross-document corpus numbers clauses into double digits (14.2) and spans
# four documents, so a signature has to capture both the clause and which document
# it is in. `SECTION_RE` above is left untouched: changing it would silently alter
# the section-Jaccard figures already published for document.md and
# document_long.md, and those numbers are quoted in FINDINGS.md.
# NOTE THE `(?:...)`. This was written with a CAPTURING group, and `re.findall`
# returns only the groups when a pattern has any -- so every clause number matched
# by the first alternative came back as an empty string and was discarded. The
# result was that all four documents' section signatures collapsed to the four
# document names: `sections_union` 4.00 and section Jaccard exactly 1.000 in every
# xdoc run, which looks like a finding ("all calls looked in the same places") and
# is a regex bug. Any xdoc section-signature figure produced before this fix is
# invalid; `recompute_sections.py` re-derives them from the stored findings.
XDOC_SECTION_RE = re.compile(
    r"\b\d{1,2}\.\d{1,2}\b|\bsection\s+\d{1,2}\b|\bannex\s+\d\b|\bappendix\s+[a-c]\b"
    r"|\b(?:msa|sow|dpa|sla)\b|master services agreement|statement of work"
    r"|data processing addendum|service level",
    re.IGNORECASE,
)

# Set by main() according to --doc. A module global rather than a parameter because
# analyse() is called from several places and does not otherwise need to know the
# document mode.
_SIG_RE = SECTION_RE


def section_signature(findings: list[str]) -> set[str]:
    sig: set[str] = set()
    for f in findings:
        for m in _SIG_RE.findall(f):
            # A pattern with a capture group yields tuples; take whatever matched.
            if isinstance(m, tuple):
                m = next((x for x in m if x), "")
            if m:
                sig.add(m.lower().replace("section ", "s").strip())
    return sig


def run_parallel(provider: str, model: str, doc: str, k: int, temperature: float) -> list[dict]:
    """K calls, each with a fresh context. This is the amnesia condition."""
    runs = []
    for i in range(k):
        msgs = [{"role": "user", "content": _PROMPT.format(document=doc)}]
        raw, secs, usage = call_model(provider, model, msgs, temperature)
        findings = parse_findings(raw)
        failed = is_failed_call(raw)
        matched, unmatched = match_defects(findings)
        runs.append({
            "call": i,
            "raw": raw,
            "findings": findings,
            "matched": sorted(matched),
            "unmatched": unmatched,
            "failed": failed,
            "seconds": round(secs, 1),
            "usage": usage,
        })
        print(f"    parallel t={temperature} call {i+1}/{k}: "
              f"{len(matched)}/{len(DEFECTS)} defects, {len(findings)} findings, {secs:.0f}s"
              + (f"  [NOT A MEASUREMENT: {failed}]" if failed else ""))
    return runs


def run_sequential(provider: str, model: str, doc: str, k: int, temperature: float) -> list[dict]:
    """One conversation, asked k times. Context accumulates -- the control."""
    msgs = [{"role": "user", "content": _PROMPT.format(document=doc)}]
    runs = []
    for i in range(k):
        if i > 0:
            msgs.append({"role": "user", "content": FOLLOWUP})
        raw, secs, usage = call_model(provider, model, msgs, temperature)
        msgs.append({"role": "assistant", "content": raw})
        findings = parse_findings(raw)
        failed = is_failed_call(raw)
        matched, unmatched = match_defects(findings)
        runs.append({
            "turn": i,
            "raw": raw,
            "findings": findings,
            "matched": sorted(matched),
            "unmatched": unmatched,
            "failed": failed,
            "seconds": round(secs, 1),
            "usage": usage,
        })
        print(f"    sequential turn {i+1}/{k}: "
              f"{len(matched)}/{len(DEFECTS)} defects, {len(findings)} findings, {secs:.0f}s")
    return runs


def analyse(runs: list[dict], label: str, model: str) -> dict:
    # Recall statistics are computed over MEASURING calls only. A truncated,
    # refused or unparseable call produced no answer; scoring it as "found zero
    # defects" is a different claim and a false one. Measured on qwen3:8b at
    # xdoc15: 2 of 16 calls runaway-generate past any num_predict cap, and counting
    # them as zeros dropped mean per-call recall from 8.29 to 7.25 while leaving the
    # union a lower bound.
    #
    # Cost and token stats stay over ALL calls, because a failed call still spent
    # money and wall-clock.
    all_runs = runs
    runs = [r for r in all_runs if not r.get("failed")]
    sets = [set(r["matched"]) for r in runs]
    per_call = [len(s) for s in sets]

    # Marginal yield: union size after each successive call, in order.
    union, curve = set(), []
    for s in sets:
        union |= s
        curve.append(len(union))

    pairs = [jaccard(a, b) for a, b in combinations(sets, 2)]

    # Ground-truth-free track: section signatures + raw finding counts.
    sigs = [section_signature(r["findings"]) for r in runs]
    sig_pairs = [jaccard(a, b) for a, b in combinations(sigs, 2)]
    sig_union, sig_curve = set(), []
    for s in sigs:
        sig_union |= s
        sig_curve.append(len(sig_union))

    # Token + cost accounting. The load-bearing comparison for W3 is call 1 alone
    # versus all k calls: if the union does not grow, everything after call 1 is
    # pure spend.
    usages = [r.get("usage") or EMPTY_USAGE for r in all_runs]
    costs = [call_cost(model, u) for u in usages]
    priced = [c for c in costs if c is not None]

    # Non-measurements: truncated, refused, or unparseable. A run containing ANY of
    # these has invalid recall figures -- every one is scored as zero defects found,
    # which drags the per-call mean down and understates the union. Surfaced at the
    # top of the payload rather than buried, because 9 of 16 qwen3:8b calls on the
    # 15-document corpus were truncated and the resulting numbers looked plausible.
    failures = [r.get("failed") for r in all_runs if r.get("failed")]
    failure_counts: dict[str, int] = {}
    for f in failures:
        failure_counts[f] = failure_counts.get(f, 0) + 1

    return {
        "label": label,
        # k is the number of calls the recall figures are computed over, so it is the
        # MEASURING count. k_attempted is what was requested. When they differ, the
        # union is a union across fewer calls than intended -- a lower bound on what
        # k_attempted would have reached.
        "k": len(runs),
        "k_attempted": len(all_runs),
        "failed_calls": len(failures),
        "failed_call_reasons": failure_counts,
        "recall_figures_valid": not failures,
        "tokens_in": sum(u["input_tokens"] for u in usages),
        "tokens_out": sum(u["output_tokens"] for u in usages),
        "cache_read_tokens": sum(u["cache_read_input_tokens"] for u in usages),
        "cache_write_tokens": sum(u["cache_creation_input_tokens"] for u in usages),
        "tokens_per_call_out": [u["output_tokens"] for u in usages],
        "cost_usd_total": round(sum(priced), 4) if priced else None,
        "cost_usd_first_call": round(priced[0], 4) if priced else None,
        "cost_usd_wasted_after_first": (
            round(sum(priced[1:]), 4) if len(priced) > 1 else None
        ),
        "seconds_total": round(sum(r["seconds"] for r in runs), 1),
        "finding_counts": [len(r["findings"]) for r in runs],
        "sections_per_call": [len(s) for s in sigs],
        "sections_union": len(sig_union),
        "sections_union_curve": sig_curve,
        "mean_pairwise_jaccard_sections": round(statistics.mean(sig_pairs), 3) if sig_pairs else None,
        "sections_seen": sorted(sig_union),
        "per_call_recall": per_call,
        "mean_per_call": round(statistics.mean(per_call), 2) if per_call else 0,
        "best_single": max(per_call) if per_call else 0,
        "union_recall": len(union),
        "union_curve": curve,
        "marginal_gain_after_first": len(union) - (per_call[0] if per_call else 0),
        "mean_pairwise_jaccard": round(statistics.mean(pairs), 3) if pairs else None,
        "union_ids": sorted(union),
        "never_found": sorted({d["id"] for d in DEFECTS} - union),
        "unmatched_finding_count": sum(len(r["unmatched"]) for r in runs),
    }


# Metrics tracked across repeats. (key, human label, decimal places)
VARIANCE_KEYS = [
    ("mean_per_call", "mean per-call recall", 2),
    ("best_single", "best single call", 2),
    ("union_recall", "union across k", 2),
    ("marginal_gain_after_first", "gain from calls 2..k", 2),
    ("mean_pairwise_jaccard", "defect-set Jaccard", 3),
    ("mean_pairwise_jaccard_sections", "section Jaccard", 3),
    ("sections_union", "sections union", 2),
    ("first_call_sections", "sections on call 1", 2),
    ("unmatched_finding_count", "beyond-ground-truth findings", 1),
    ("cost_usd_total", "cost of all k calls ($)", 4),
    ("cost_usd_first_call", "cost of call 1 ($)", 4),
    ("cost_usd_wasted_after_first", "spent after call 1 ($)", 4),
]


#: Set by summarize_variance so print_variance can warn about non-measurement calls
#: without threading the analyses through every call site.
_LAST_ANALYSES: list[dict] = []


def summarize_variance(analyses: list[dict]) -> dict:
    """mean / sample sd / min / max for each tracked metric across repeats."""
    global _LAST_ANALYSES
    _LAST_ANALYSES = list(analyses)
    out = {}
    for key, label, _dp in VARIANCE_KEYS:
        vals = []
        for a in analyses:
            v = a.get("first_call_sections") if key == "first_call_sections" else a.get(key)
            if key == "first_call_sections":
                v = a["sections_per_call"][0] if a.get("sections_per_call") else None
            if v is not None:
                vals.append(float(v))
        if not vals:
            continue
        out[key] = {
            "label": label,
            "n": len(vals),
            "mean": statistics.mean(vals),
            # Sample sd. n=1 has no spread; n=5 sd is itself noisy -- the
            # min-max range is the more honest summary at this sample size.
            "sd": statistics.stdev(vals) if len(vals) > 1 else 0.0,
            "min": min(vals),
            "max": max(vals),
            "values": vals,
        }
    return out


def print_variance(var: dict, k: int) -> None:
    print("\n" + "=" * 78)
    print(f"VARIANCE ACROSS REPEATS  (parallel condition, k={k} calls per repeat)")
    print("=" * 78)
    bad = [a for a in _LAST_ANALYSES if a.get("failed_calls")]
    if bad:
        total = sum(a["failed_calls"] for a in bad)
        reasons = {}
        for a in bad:
            for kk, vv in (a.get("failed_call_reasons") or {}).items():
                reasons[kk] = reasons.get(kk, 0) + vv
        ks = [f"{a['k']}/{a.get('k_attempted', a['k'])}" for a in _LAST_ANALYSES]
        print(f"\n  !! {total} NON-MEASUREMENT CALL(S) {reasons} across "
              f"{len(bad)} repeat(s). They are EXCLUDED from the recall figures rather "
              f"than scored as zero, so those figures are computed over fewer calls "
              f"than requested (measuring/attempted per repeat: {', '.join(ks)}). "
              "The union is therefore a LOWER BOUND on what the full k would reach.")
    print(f"  {'metric':<30} {'mean':>9}  {'sd':>8}   {'range':>15}   values")
    for key, label, dp in VARIANCE_KEYS:
        s = var.get(key)
        if not s:
            continue
        rng = f"{s['min']:.{dp}f}–{s['max']:.{dp}f}"
        vals = " ".join(f"{v:.{dp}f}" for v in s["values"])
        print(f"  {label:<30} {s['mean']:>9.{dp}f}  {s['sd']:>8.{dp}f}   {rng:>15}   {vals}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="ollama", choices=["ollama", "anthropic", "openai"])
    ap.add_argument("--model", default="qwen3:8b")
    ap.add_argument("-k", type=int, default=8)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--doc", default="short",
                    choices=["short", "long", "xdoc", "xdoc9", "xdoc15"],
                    help="short = document.md (8 defects); long = document_long.md (20); "
                         "xdoc = corpus_xdoc/, 4 documents / 6 pairs / 24 cross-document "
                         "defects; xdoc9 = + corpus_xdoc_ext/, 9 documents / 36 pairs / "
                         "52 defects; xdoc15 = + corpus_xdoc_ext2/, 15 documents / "
                         "105 pairs / 87 defects")
    ap.add_argument("--repeats", type=int, default=1,
                    help="repeat the PARALLEL condition N times and report variance")
    ap.add_argument("--max-calls", type=int, default=400,
                    help="hard call-count bound; the backstop for models the spend "
                         "cap cannot price (see the guards comment above)")
    ap.add_argument("--max-output-tokens", type=int, default=None,
                    help="frontier output-token budget (thinking/reasoning + visible "
                         "output). Defaults to 8000, or 24000 for --doc xdoc, which "
                         "truncates at 8000.")
    ap.add_argument("--num-ctx", type=int, default=None,
                    help="Ollama context window. Defaults to Ollama's own setting, or "
                         "16384 for --doc xdoc, whose ~5k-token prompt would otherwise "
                         "be TRUNCATED SILENTLY.")
    ap.add_argument("--num-predict", type=int, default=None,
                    help="Ollama generation cap. Ollama's default is unbounded up to "
                         "num_ctx, which let qwen3:8b spend 14 minutes on one xdoc15 "
                         "call. Defaults to 4096 for the cross-document corpora.")
    args = ap.parse_args()

    global MAX_OUTPUT_TOKENS, NUM_CTX, NUM_PREDICT
    if args.max_output_tokens:
        MAX_OUTPUT_TOKENS = args.max_output_tokens
    elif args.doc == "xdoc":
        # Measured: Opus 5 truncated at 8000 on this corpus, returning no JSON at
        # all after 92 seconds. 24 defects of prose plus thinking needs more room.
        MAX_OUTPUT_TOKENS = 24000
    elif args.doc == "xdoc9":
        # 52 defects to describe rather than 24, over a corpus 2.3x the size.
        MAX_OUTPUT_TOKENS = 48000
    elif args.doc == "xdoc15":
        # 87 defects over ~53k chars. Measured on xdoc9: ~0.44 USD/call at 48000,
        # so this is the expensive setting -- see the corpus README on cost.
        MAX_OUTPUT_TOKENS = 64000
    if args.num_ctx:
        NUM_CTX = args.num_ctx
    elif args.doc == "xdoc":
        NUM_CTX = 16384
    elif args.doc == "xdoc9":
        # The nine-document set is ~2.3x the four-document one. 8192 was already
        # only just enough for 4 documents (~5k tokens); this needs the headroom or
        # Ollama truncates the tail SILENTLY and the locals never see the last
        # documents at all.
        NUM_CTX = 24576
    elif args.doc == "xdoc15":
        NUM_CTX = 32768
    if args.num_predict:
        NUM_PREDICT = args.num_predict
    elif args.doc in ("xdoc", "xdoc9", "xdoc15"):
        # Enough for a long list of findings, far short of what an unbounded run will
        # emit to fill the context. A truncated JSON body parses to zero findings and
        # is visible as a parse failure, which is the honest failure mode; an
        # unbounded one just burns the timeout and returns nothing at all.
        NUM_PREDICT = 4096
    if args.provider == "ollama" and (NUM_CTX or NUM_PREDICT):
        print(f"[ollama] num_ctx={NUM_CTX} num_predict={NUM_PREDICT}")

    init_guards(run_id=f"w3_{args.model}_{args.doc}_k{args.k}", max_calls=args.max_calls)

    # Swap in the requested document set and its ground truth. The short document
    # ceilings on frontier models (Opus 5: 8/8 on call 1), and so does the long one
    # (20/20 on call 1), which is why the cross-document corpus exists.
    global DEFECTS, _PROMPT, _SIG_RE
    if args.doc == "long":
        from defects_long import DEFECTS_LONG
        DEFECTS = DEFECTS_LONG
        doc = (HERE / "document_long.md").read_text(encoding="utf-8")
    elif args.doc in ("xdoc", "xdoc9", "xdoc15"):
        from defects_xdoc import DEFECTS_XDOC
        DEFECTS = list(DEFECTS_XDOC)
        _PROMPT = PROMPT_XDOC
        _SIG_RE = XDOC_SECTION_RE
        # ONLY the numbered corpus documents. `glob("*.md")` was the first version
        # and it silently swept in corpus_xdoc/README.md -- which contains the full
        # conflict map, i.e. the answer key. The first Opus smoke run scored a
        # suspiciously clean 24/24 because the answers were in its prompt. The tell
        # was the banner reporting "5 documents, 26,482 chars" for a 4-document,
        # 19,662-char corpus, which is why the banner now lists the filenames.
        # Each extension is a SEPARATE directory rather than more files in the first
        # one, so `--doc xdoc` keeps sending exactly the four documents its published
        # 24-defect figures were measured on, and `--doc xdoc9` its nine. Growing a
        # corpus in place would silently invalidate every figure measured on it.
        dirs = [HERE / "corpus_xdoc"]
        if args.doc in ("xdoc9", "xdoc15"):
            from defects_xdoc_ext import DEFECTS_XDOC_EXT
            DEFECTS = DEFECTS + list(DEFECTS_XDOC_EXT)
            dirs.append(HERE / "corpus_xdoc_ext")
        if args.doc == "xdoc15":
            from defects_xdoc_ext2 import DEFECTS_XDOC_EXT2
            DEFECTS = DEFECTS + list(DEFECTS_XDOC_EXT2)
            dirs.append(HERE / "corpus_xdoc_ext2")
        parts = [p for d in dirs for p in sorted(d.glob("[0-9][0-9]_*.md"))]
        if len(parts) < 2:
            raise SystemExit(
                f"{', '.join(d.name for d in dirs)} must contain at least two "
                f"NN_*.md documents; found {[p.name for p in parts]}"
            )
        ids = [d["id"] for d in DEFECTS]
        if len(set(ids)) != len(ids):
            raise SystemExit(f"duplicate defect ids across the ground truths: {ids}")
        # Concatenated in filename order (01_msa, 02_sow, 03_dpa, 04_sla) with a
        # hard separator, so the model sees four distinct documents rather than one
        # long one. Order is FIXED rather than shuffled: shuffling would vary the
        # prompt between calls, and W3 tests resampling at a *fixed* prompt.
        doc = "\n\n".join(
            f"===== BEGIN {p.name} =====\n{p.read_text(encoding='utf-8').strip()}\n"
            f"===== END {p.name} ====="
            for p in parts
        )
        n_pairs = len(parts) * (len(parts) - 1) // 2
        print(f"[corpus] {len(parts)} documents ({', '.join(p.name for p in parts)}), "
              f"{len(doc):,} chars, {n_pairs} document pairs, "
              f"{len(DEFECTS)} seeded cross-document defects")
    else:
        doc = (HERE / "document.md").read_text(encoding="utf-8")

    # --repeats: the W3 claim rests on the parallel condition, so that is what
    # gets repeated. Sequential's conclusion is qualitative (self-acknowledged
    # padding in late turns) and does not sharpen with more samples.
    if args.repeats > 1 and not args.smoke:
        # Both frontier vendors reject a non-default temperature (probed), so the
        # value passed is ignored on those paths; only Ollama honours it.
        temp = 0.0 if args.provider in ("anthropic", "openai") else 0.8
        out = HERE / f"variance_{args.model.replace(':', '_')}_{args.doc}_r{args.repeats}.json"

        def _persist(reps_so_far: list[dict], complete: bool) -> dict:
            """Write the payload after every repeat.

            WHY INCREMENTALLY. This used to write once, at the very end, and a
            single failed call therefore discarded every completed repeat's
            analysis with it. That happened twice on the cross-document corpus:
            one Ollama 600s timeout on repeat 2's first call threw away eight
            good `qwen3:8b` calls, and an earlier one threw away three repeats.
            The ledger still had the spend; the findings were simply gone.
            `repeats_completed` and `complete` record how much of the intended run
            the file actually represents, so a partial file is never mistaken for
            a full one.
            """
            v = summarize_variance([r["analysis"] for r in reps_so_far])
            payload = {
                "provider": args.provider,
                "model": args.model,
                "k": args.k,
                # `repeats` kept under its original name so anything reading the
                # existing variance_*.json files still works; the two new keys are
                # what you should actually check.
                "repeats": args.repeats,
                "repeats_requested": args.repeats,
                "repeats_completed": len(reps_so_far),
                "complete": complete,
                "condition": "parallel",
                "temperature_control_available": args.provider == "ollama",
                "num_ctx": NUM_CTX,
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "per_repeat": reps_so_far,
                "variance": v,
            }
            out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return v

        reps: list[dict] = []
        var: dict = {}
        try:
            for i in range(args.repeats):
                print(f"=== repeat {i + 1}/{args.repeats} ({args.model}, parallel k={args.k}) ===")
                runs = run_parallel(args.provider, args.model, doc, args.k, temp)
                reps.append({
                    "repeat": i + 1,
                    "runs": runs,
                    "analysis": analyse(runs, f"parallel_rep{i + 1}", args.model),
                })
                var = _persist(reps, complete=(i + 1 == args.repeats))
                print(f"    [saved {len(reps)}/{args.repeats} repeats to {out.name}]")
        except (BudgetExceeded, CallCapExceeded):
            raise  # a deliberate abort; the guard already explained itself
        except Exception as exc:  # noqa: BLE001 - keep the completed repeats
            if reps:
                var = _persist(reps, complete=False)
                print(f"\n!! run FAILED after {len(reps)}/{args.repeats} repeats "
                      f"({type(exc).__name__}: {str(exc)[:200]})")
                print(f"   the {len(reps)} completed repeat(s) ARE saved in {out.name} "
                      "with complete=false -- do not quote them as the full run")
            else:
                raise

        if reps:
            print(f"\nwrote {out}")
            print_variance(var, args.k)
        if _GUARD:
            print(f"\n[budget] {_GUARD.summary()}")
        return

    if args.smoke:
        raw, secs, _u = call_model(
            args.provider,
            args.model,
            [{"role": "user", "content": _PROMPT.format(document=doc)}],
            0.8,
        )
        findings = parse_findings(raw)
        failed = is_failed_call(raw)
        matched, unmatched = match_defects(findings)
        print(f"smoke: {secs:.0f}s, {len(findings)} findings, "
              f"{len(matched)}/{len(DEFECTS)} matched -> {sorted(matched)}")
        print(f"unmatched: {unmatched}")
        print(f"raw[:400]: {raw[:400]}")
        return

    results = {"provider": args.provider, "model": args.model, "k": args.k, "conditions": {}}

    # BOTH frontier vendors reject a non-default temperature with a 400 (Opus
    # 5/4.8/4.7 reject the parameter; gpt-5.5 accepts only its default of 1), so
    # the frontier paths get default sampling only and the temp-0.0 convergence
    # control cannot be run on either. Recorded in the results so the gap is
    # visible in the artifact rather than only in a comment.
    if args.provider in ("anthropic", "openai"):
        results["temperature_control_available"] = False
        print("[1/2] PARALLEL default sampling  (the actual W3 test)")
        print(f"      NOTE: no temp-0.0 control -- {args.provider} rejects a non-default "
              "temperature on this model.")
        p8 = run_parallel(args.provider, args.model, doc, args.k, 0.0)
        results["conditions"]["parallel_default"] = {"runs": p8, "analysis": analyse(p8, "parallel_default", args.model)}

        print("[2/2] SEQUENTIAL default sampling  (accumulating-context control)")
        sq = run_sequential(args.provider, args.model, doc, args.k, 0.0)
        results["conditions"]["sequential_default"] = {"runs": sq, "analysis": analyse(sq, "sequential_default", args.model)}
    else:
        results["temperature_control_available"] = True
        print("[1/3] PARALLEL temp=0.0  (convergence positive control)")
        p0 = run_parallel(args.provider, args.model, doc, args.k, 0.0)
        results["conditions"]["parallel_t0.0"] = {"runs": p0, "analysis": analyse(p0, "parallel_t0.0", args.model)}

        print("[2/3] PARALLEL temp=0.8  (the actual W3 test)")
        p8 = run_parallel(args.provider, args.model, doc, args.k, 0.8)
        results["conditions"]["parallel_t0.8"] = {"runs": p8, "analysis": analyse(p8, "parallel_t0.8", args.model)}

        print("[3/3] SEQUENTIAL temp=0.8  (accumulating-context control)")
        sq = run_sequential(args.provider, args.model, doc, args.k, 0.8)
        results["conditions"]["sequential_t0.8"] = {"runs": sq, "analysis": analyse(sq, "sequential_t0.8", args.model)}

    out = HERE / f"results_{args.model.replace(':', '_')}_{args.doc}.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")

    print("\n" + "=" * 72)
    for key, cond in results["conditions"].items():
        a = cond["analysis"]
        print(f"\n{key}")
        print(f"  per-call recall     {a['per_call_recall']}  mean {a['mean_per_call']}/{len(DEFECTS)}")
        print(f"  best single call    {a['best_single']}/{len(DEFECTS)}")
        print(f"  union across k={a['k']}   {a['union_recall']}/{len(DEFECTS)}")
        print(f"  union curve         {a['union_curve']}")
        print(f"  gain after 1st call +{a['marginal_gain_after_first']}")
        print(f"  mean pairwise J     {a['mean_pairwise_jaccard']}")
        print(f"  never found         {a['never_found']}")
        print(f"  unmatched findings  {a['unmatched_finding_count']}")
        print(f"  --- ground-truth-free (valid above the 8-defect ceiling) ---")
        print(f"  findings per call   {a['finding_counts']}")
        print(f"  sections per call   {a['sections_per_call']}")
        print(f"  sections union      {a['sections_union']}  curve {a['sections_union_curve']}")
        print(f"  mean pairwise J sec {a['mean_pairwise_jaccard_sections']}")
        print(f"  --- cost ---")
        print(f"  tokens in/out       {a['tokens_in']:,} / {a['tokens_out']:,}"
              + (f"  (cache r/w {a['cache_read_tokens']:,}/{a['cache_write_tokens']:,})"
                 if a['cache_read_tokens'] or a['cache_write_tokens'] else ""))
        print(f"  output per call     {a['tokens_per_call_out']}")
        print(f"  wall clock          {a['seconds_total']}s")
        if a["cost_usd_total"] is not None:
            print(f"  cost total          ${a['cost_usd_total']:.4f}")
            print(f"  cost of call 1      ${a['cost_usd_first_call']:.4f}")
            print(f"  spent after call 1  ${a['cost_usd_wasted_after_first']:.4f}"
                  f"  <- bought {a['sections_union'] - a['sections_per_call'][0]} extra section(s), "
                  f"{a['union_recall'] - a['per_call_recall'][0]} extra seeded defect(s)")


if __name__ == "__main__":
    main()
