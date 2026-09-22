"""Verified per-token prices, usage normalisation, and an enforced spend cap.

Why this module exists
---------------------
Before 2026-08-04 the only spend control in the repo lived inside
``experiments/w3_independence/run_w3.py``. The suite's own runners --
``ombs run``, ``ombs run-multiturn`` -- had none, and ``run-multiturn`` did not
even record token counts, so a frontier run could not be costed after the fact,
let alone stopped. The W2 Opus runs were therefore *bounded by call count*, not
*capped by a control*. This module makes the cap real on the paths that spend.

Two limits, stated plainly rather than buried
--------------------------------------------
1. **The ledger starts when it starts.** Cumulative spend is summed from
   ``outputs/spend_ledger.jsonl``, which only contains calls made after this
   module was introduced. Spend from earlier sessions (~$9-10 of Anthropic usage
   on 2026-08-03/04) is invisible to it. The cap therefore bounds *future*
   spend, not lifetime spend.
2. **It can overshoot by at most one call.** Output length is unknown until the
   response arrives, so a call is charged after it completes. A call that starts
   under the cap and ends over it is not refunded. The guard refuses to *start*
   any further call once the cap is crossed.
3. **Concurrent runs each see a stale baseline.** ``spent_before`` is read once at
   construction, so two runners started at the same time both compute their
   remaining budget from the ledger as it was before either began, and their
   combined spend can exceed the cap by up to the other's total. Appends
   themselves are single short writes and do not corrupt the file. Sequential
   runs are fully covered; if runs are to be parallelised, this needs a lock, and
   the honest word until then is that the cap covers *sequential* use.

Models absent from ``PRICING`` contribute 0 and are consequently **not covered**.
That is correct for Ollama models, which are free, and dangerous for any new
frontier model. Until 12 Sep 2026 nothing enforced this: the remit-review judge
``claude-sonnet-5`` ran 14 calls with no price entry, each booked at ``cost_usd:
null`` and invisible to the cap. ``refuse_unpriced`` now stops a billing
provider's run before its first call unless every model it will use is priced
(or ``--allow-unpriced`` is passed deliberately); ``reprice_ledger`` recomputes
the cost of historical null rows from their stored token counts once a price
exists, so the omission is corrected in the record rather than only disclosed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# --------------------------------------------------------------------------- #
# Prices: USD per 1M tokens.
#
# `cached_input` is the discounted rate for a prompt-cache hit. Anthropic also
# bills cache WRITES at 1.25x input; OpenAI does not bill cache writes at all
# (probed: `prompt_tokens_details.cache_write_tokens` comes back null/0).
#
# PROVENANCE -- these are the numbers, and where each came from:
#   claude-opus-5, claude-opus-4-8: $5.00 / $25.00, carried over from
#       experiments/w3_independence/run_w3.py, where they backed the measured
#       $0.3662 +/- 0.0055 per 8-call repeat figure.
#   gpt-5.5: $5.00 in / $0.50 cached / $30.00 out, VERIFIED 2026-08-04 against
#       OpenAI's published pricing page. This replaces a deliberately pessimistic
#       $15/$60 placeholder that a prior session used as an upper bound while the
#       real price was unknown.
#
# CONTEXT-LENGTH CAVEAT: gpt-5.5 has a second, higher price tier above a 272K
# prompt ($10 in / $45 out). Every prompt in this suite is orders of magnitude
# below that, and `call_cost` raises if one is not, so the cheap tier is never
# applied silently to a long-context call.
# --------------------------------------------------------------------------- #

PRICING: dict[str, dict[str, float]] = {
    "claude-opus-5": {"input": 5.00, "cached_input": 0.50, "output": 25.00},
    "claude-opus-4-8": {"input": 5.00, "cached_input": 0.50, "output": 25.00},
    "gpt-5.5": {"input": 5.00, "cached_input": 0.50, "output": 30.00},
    # claude-sonnet-5: $2.00 in / $10.00 out, Anthropic's list price as published 12 Sep 2026
    # (the introductory rate made permanent in August 2026); cached input at the standard 10%
    # cache-read rate. Added 12 Sep 2026 because this model judged the Wave 4-6 remit reviews
    # unpriced (14 ledger rows at cost null, since repriced with `ombs reprice-ledger`). The
    # PI confirms the figures against the vendor's page before the next judge call.
    "claude-sonnet-5": {"input": 2.00, "cached_input": 0.20, "output": 10.00},
    # gemini-3.1-pro-preview: $2.00 in / $12.00 out per 1M for prompts up to 200K, Google's list
    # price as published 12 Sep 2026. PREREG_THIRD_VENDOR_GEMINI.md fixes the model-id rule; the
    # OpenAI-compatible listing on 12 Sep 2026 (`ombs list-models --provider google`, 55 ids) showed
    # `models/gemini-3.1-pro-preview` and `models/gemini-3.1-pro-preview-customtools` as the only
    # 3.1 Pro-tier ids and no GA `gemini-3.1-pro`, so the plain preview id is the one under the
    # rule; configs pass the bare id without the `models/` prefix, as Google's compat docs do.
    # Cached input is entered AT the input rate until the discount is confirmed -- an over-count is
    # the safe error. Keyed by the exact id the configs use; the guard looks it up literally.
    "gemini-3.1-pro-preview": {"input": 2.00, "cached_input": 2.00, "output": 12.00},
}

# Providers that bill. A run on one of these must name only priced models, or the cap cannot
# see its spend. Ollama is free; the scripted test doubles use names outside this tuple.
BILLING_PROVIDERS: tuple[str, ...] = ("anthropic", "openai", "google", "gemini")

# Prompt size at which a model switches to a higher price tier. gpt-5.5 (272K) and
# gemini-3.1-pro-preview (200K) have one in this table; the check is applied generally
# so a future entry cannot quietly inherit the wrong assumption.
LONG_CONTEXT_THRESHOLD = {"gpt-5.5": 272_000, "gemini-3.1-pro-preview": 200_000}

EMPTY_USAGE = {
    "input_tokens": 0,
    "output_tokens": 0,
    "cached_input_tokens": 0,
    "cache_write_tokens": 0,
}


class BudgetExceeded(RuntimeError):
    """Raised to abort a run whose cumulative spend has crossed the cap."""


class UnpricedModel(RuntimeError):
    """A billing provider was asked to run a model with no entry in ``PRICING``."""


def refuse_unpriced(models, provider: str, *, allow_unpriced: bool = False) -> None:
    """Refuse a billing provider's run unless every model it will use is priced.

    Module-level rather than a ``BudgetGuard`` method on purpose: the runner tests replace the
    guard with a plain stub class, and a refusal that lived on the guard would vanish with it.
    ``allow_unpriced`` exists for a deliberate, call-count-bounded run and is a CLI flag, never a
    config field.
    """
    if allow_unpriced or (provider or "").lower() not in BILLING_PROVIDERS:
        return
    unpriced = [m for m in models if m not in PRICING]
    if unpriced:
        raise UnpricedModel(
            f"provider {provider!r} bills for {unpriced} but PRICING has no entry for "
            f"{'it' if len(unpriced) == 1 else 'them'}, so the spend cap could not see the run. "
            "Add the verified per-token price to src/ombs/utils/budget.py PRICING (keyed by the "
            "exact model id the config uses), or pass --allow-unpriced to bound the run by call "
            "count deliberately."
        )


def reprice_ledger(ledger_path, model: str, *, apply: bool = False,
                   repriced_on: str = "", note: str = "") -> dict:
    """Recompute ``cost_usd`` for a model's historical ``null`` rows from their stored usage.

    Returns ``{"rows": n, "total_usd": x, "by_run": {run_id: usd}}``. With ``apply`` the ledger
    is rewritten: only the matching rows change (``cost_usd`` set; ``repriced_on`` and
    ``reprice_note`` appended), every other line is written back byte-for-byte. Raises
    ``UnpricedModel`` if the model still has no price, since there is nothing to reprice with.
    """
    ledger_path = Path(ledger_path)
    if model not in PRICING:
        raise UnpricedModel(f"{model!r} has no PRICING entry; add it before repricing")
    lines = ledger_path.read_text(encoding="utf-8").splitlines(keepends=True)
    out: list[str] = []
    by_run: dict[str, float] = {}
    n = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out.append(line)
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError:
            out.append(line)
            continue
        if row.get("model") != model or row.get("cost_usd") is not None or not row.get("usage"):
            out.append(line)
            continue
        cost = call_cost(model, row["usage"])
        if cost is None:
            out.append(line)
            continue
        n += 1
        by_run[row.get("run_id", "")] = by_run.get(row.get("run_id", ""), 0.0) + cost
        if apply:
            row["cost_usd"] = cost
            row["repriced_on"] = repriced_on
            row["reprice_note"] = note
            out.append(json.dumps(row, ensure_ascii=False) + ("\n" if line.endswith("\n") else ""))
        else:
            out.append(line)
    if apply and n:
        ledger_path.write_text("".join(out), encoding="utf-8")
    return {"rows": n, "total_usd": round(sum(by_run.values()), 6), "by_run": {k: round(v, 6) for k, v in by_run.items()}}


def usage_from_metadata(meta: dict | None) -> dict:
    """Normalise a provider's ``provider_metadata`` into one usage shape.

    The three providers report tokens under three different sets of keys, and
    getting this wrong fails silently as a cost of zero -- so unknown shapes
    return zeros rather than guessing.

    - openai   : input_tokens (cache-hit tokens already excluded),
                 cached_input_tokens, output_tokens
    - anthropic: input_tokens, output_tokens,
                 cache_creation_input_tokens, cache_read_input_tokens
    - ollama   : prompt_eval_count, eval_count   (free; recorded for the record)
    """
    u = dict(EMPTY_USAGE)
    if not meta:
        return u

    if "prompt_eval_count" in meta or "eval_count" in meta:
        u["input_tokens"] = meta.get("prompt_eval_count") or 0
        u["output_tokens"] = meta.get("eval_count") or 0
        return u

    u["input_tokens"] = meta.get("input_tokens") or 0
    u["output_tokens"] = meta.get("output_tokens") or 0
    u["cached_input_tokens"] = (
        meta.get("cached_input_tokens")
        or meta.get("cache_read_input_tokens")
        or 0
    )
    u["cache_write_tokens"] = (
        meta.get("cache_write_tokens")
        or meta.get("cache_creation_input_tokens")
        or 0
    )
    return u


def call_cost(model: str, usage: dict) -> float | None:
    """USD for one call, or ``None`` for a model with no published price.

    ``None`` means "not covered by the budget guard" and is deliberately
    distinct from ``0.0``, which means "priced, and free".
    """
    p = PRICING.get(model)
    if not p:
        return None

    prompt_total = (usage.get("input_tokens") or 0) + (usage.get("cached_input_tokens") or 0)
    threshold = LONG_CONTEXT_THRESHOLD.get(model)
    if threshold and prompt_total > threshold:
        raise ValueError(
            f"{model}: prompt of {prompt_total:,} tokens exceeds the {threshold:,}-token "
            "tier boundary, so the price in PRICING is the wrong one. Add the "
            "long-context rate before running this."
        )

    return (
        (usage.get("input_tokens") or 0) * p["input"]
        + (usage.get("cached_input_tokens") or 0) * p.get("cached_input", p["input"] * 0.1)
        + (usage.get("cache_write_tokens") or 0) * p["input"] * 1.25
        + (usage.get("output_tokens") or 0) * p["output"]
    ) / 1_000_000


DEFAULT_LEDGER = Path("outputs") / "spend_ledger.jsonl"
# Cumulative cap across every run the ledger has seen. Deliberately below the
# $30 balance so a mistake leaves change rather than a dead key.
DEFAULT_CAP_USD = 25.00


class BudgetGuard:
    """Cumulative, cross-invocation spend cap with an append-only ledger.

    A per-run cap would not protect a $30 balance: twenty runs each safely under
    a per-run limit still drains it. The cap here is summed over the ledger, so
    it spans invocations.
    """

    def __init__(
        self,
        run_id: str,
        cap_usd: float | None = None,
        ledger_path: str | Path | None = None,
    ):
        self.run_id = run_id
        self.cap_usd = (
            cap_usd
            if cap_usd is not None
            else float(os.environ.get("OMBS_BUDGET_USD", DEFAULT_CAP_USD))
        )
        self.ledger_path = Path(ledger_path) if ledger_path else DEFAULT_LEDGER
        self.spent_this_run = 0.0
        self.calls_this_run = 0
        self.uncovered_calls = 0  # calls on models with no published price
        self.spent_before = self._read_ledger_total()

    def _read_ledger_total(self) -> float:
        if not self.ledger_path.exists():
            return 0.0
        total = 0.0
        for line in self.ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                total += float(json.loads(line).get("cost_usd") or 0.0)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue  # a corrupt line must not silently zero the ledger
        return total

    @property
    def spent_cumulative(self) -> float:
        return self.spent_before + self.spent_this_run

    def remaining(self) -> float:
        return max(self.cap_usd - self.spent_cumulative, 0.0)

    def _append(self, model: str, cost: float | None, usage: dict) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "run_id": self.run_id,
                        "model": model,
                        "cost_usd": cost,
                        "usage": usage,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    @staticmethod
    def is_priced(model: str) -> bool:
        """Can this model spend money at all?"""
        return model in PRICING

    def check_before_call(self, model: str | None = None) -> None:
        """Refuse to start another call once the cap is already crossed.

        **A model that cannot spend is never blocked.** An unpriced model (every
        Ollama model) contributes 0 to the cumulative total, so refusing to start its
        calls once the cap is reached stops free work for no benefit. That is not
        hypothetical: a local run on the 15-document corpus aborted with
        ``BudgetExceeded`` at $35.06 of frontier spend without being able to add a
        cent to it, and the failure looked for a while like a model or context problem
        rather than a bug here.

        Pass ``model`` to get that exemption. Called without one, the check is
        unconditional, which keeps the conservative behaviour for any caller that has
        not been updated.
        """
        if model is not None and not self.is_priced(model):
            return
        if self.spent_cumulative >= self.cap_usd:
            raise BudgetExceeded(
                f"cumulative spend ${self.spent_cumulative:.4f} has reached the cap "
                f"${self.cap_usd:.2f} (${self.spent_this_run:.4f} of it in run "
                f"{self.run_id!r}) -- refusing to start another call. Raise the cap with "
                "the OMBS_BUDGET_USD env var if this was intended."
            )

    def charge(self, model: str, meta: dict | None) -> tuple[dict, float | None]:
        """Record one call's usage and cost. Returns ``(usage, cost)``.

        Raises ``BudgetExceeded`` *after* recording, so the ledger is always a
        true account of what was actually spent even on the aborting call.
        """
        usage = usage_from_metadata(meta)
        cost = call_cost(model, usage)
        self.calls_this_run += 1
        if cost is None:
            self.uncovered_calls += 1
        else:
            self.spent_this_run += cost
        self._append(model, cost, usage)

        # Only a call that actually cost something can push us over. Without this,
        # charging a FREE call while already above the cap raises -- so a local run
        # started after the cap was reached would abort on its first call having
        # spent nothing.
        if cost is not None and self.spent_cumulative > self.cap_usd:
            raise BudgetExceeded(
                f"cumulative spend ${self.spent_cumulative:.4f} exceeded the cap "
                f"${self.cap_usd:.2f} -- aborting. Overshoot of at most one call is "
                "expected: output length is not known until the response arrives. "
                "Raise the cap with the OMBS_BUDGET_USD env var if this was intended."
            )
        return usage, cost

    def summary(self) -> str:
        parts = [
            f"spend this run ${self.spent_this_run:.4f} over {self.calls_this_run} calls",
            f"cumulative ${self.spent_cumulative:.4f} / cap ${self.cap_usd:.2f}",
        ]
        if self.uncovered_calls:
            parts.append(
                f"{self.uncovered_calls} call(s) on unpriced models -- NOT covered by the cap"
            )
        return "; ".join(parts)
