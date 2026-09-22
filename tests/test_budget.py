"""Tests for the enforced spend cap.

A budget guard that is never exercised is a comment, not a control -- the whole
reason this module exists is that the previous "cap" covered one experiment
script and not the suite runners. These tests pin the abort, the cross-invocation
accumulation, and the two places a silent zero could hide (an unknown usage shape
and an unpriced model).
"""

from __future__ import annotations

import json

import pytest

from ombs.utils.budget import (
    BudgetExceeded,
    BudgetGuard,
    UnpricedModel,
    call_cost,
    refuse_unpriced,
    reprice_ledger,
    usage_from_metadata,
)

OPENAI_META = {
    "input_tokens": 1000,
    "cached_input_tokens": 500,
    "output_tokens": 200,
    "finish_reason": "stop",
}
ANTHROPIC_META = {"input_tokens": 1000, "output_tokens": 200, "stop_reason": "end_turn"}
OLLAMA_META = {"prompt_eval_count": 1000, "eval_count": 200, "done_reason": "stop"}


def test_usage_normalisation_across_the_three_providers():
    assert usage_from_metadata(OPENAI_META)["cached_input_tokens"] == 500
    assert usage_from_metadata(ANTHROPIC_META)["input_tokens"] == 1000
    o = usage_from_metadata(OLLAMA_META)
    assert (o["input_tokens"], o["output_tokens"]) == (1000, 200)


def test_anthropic_cache_key_aliases_are_picked_up():
    u = usage_from_metadata(
        {
            "input_tokens": 10,
            "output_tokens": 5,
            "cache_read_input_tokens": 7,
            "cache_creation_input_tokens": 3,
        }
    )
    assert u["cached_input_tokens"] == 7
    assert u["cache_write_tokens"] == 3


def test_unknown_metadata_shape_yields_zeros_not_a_guess():
    assert usage_from_metadata({"weird": 1})["input_tokens"] == 0
    assert usage_from_metadata(None)["output_tokens"] == 0


def test_gpt55_cost_matches_the_verified_rate_card():
    # $5.00/1M in, $0.50/1M cached, $30.00/1M out.
    cost = call_cost("gpt-5.5", usage_from_metadata(OPENAI_META))
    expected = (1000 * 5.00 + 500 * 0.50 + 200 * 30.00) / 1_000_000
    assert cost == pytest.approx(expected)


def test_unpriced_model_returns_none_not_zero():
    # None means "not covered by the cap"; 0.0 would mean "priced and free".
    assert call_cost("qwen3:8b", usage_from_metadata(OLLAMA_META)) is None


def test_long_context_prompt_refuses_to_use_the_cheap_tier():
    with pytest.raises(ValueError, match="tier boundary"):
        call_cost("gpt-5.5", {"input_tokens": 300_000, "output_tokens": 10})


def test_charge_accumulates_and_writes_the_ledger(tmp_path):
    led = tmp_path / "ledger.jsonl"
    g = BudgetGuard(run_id="r1", cap_usd=1.00, ledger_path=led)
    usage, cost = g.charge("gpt-5.5", OPENAI_META)
    assert cost is not None and cost > 0
    assert usage["input_tokens"] == 1000
    rows = [json.loads(x) for x in led.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(rows) == 1 and rows[0]["run_id"] == "r1"


# $30.00/1M output, and a prompt small enough to stay on the cheap tier -- the
# expensive-tier check is exercised separately above.
THREE_DOLLARS = {"input_tokens": 0, "output_tokens": 100_000}


def test_cap_spans_invocations(tmp_path):
    # The point of the ledger: many runs each individually cheap must still add up.
    led = tmp_path / "ledger.jsonl"
    g1 = BudgetGuard(run_id="r1", cap_usd=8.00, ledger_path=led)
    g1.charge("gpt-5.5", THREE_DOLLARS)
    g2 = BudgetGuard(run_id="r2", cap_usd=8.00, ledger_path=led)
    assert g2.spent_before == pytest.approx(3.00)
    g2.charge("gpt-5.5", THREE_DOLLARS)
    assert g2.spent_cumulative == pytest.approx(6.00)
    assert g2.remaining() == pytest.approx(2.00)


def test_charge_raises_once_the_cap_is_crossed(tmp_path):
    led = tmp_path / "ledger.jsonl"
    g = BudgetGuard(run_id="r1", cap_usd=1.00, ledger_path=led)
    with pytest.raises(BudgetExceeded):
        g.charge("gpt-5.5", THREE_DOLLARS)
    # The aborting call is still on the ledger -- the record must reflect money
    # actually spent, not money we wish we had not spent.
    rows = [x for x in led.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(rows) == 1


def test_refuses_to_start_a_call_when_already_over(tmp_path):
    led = tmp_path / "ledger.jsonl"
    led.write_text(json.dumps({"run_id": "old", "model": "gpt-5.5", "cost_usd": 9.0}) + "\n",
                   encoding="utf-8")
    g = BudgetGuard(run_id="r2", cap_usd=5.00, ledger_path=led)
    with pytest.raises(BudgetExceeded, match="refusing to start"):
        g.check_before_call()


def test_a_corrupt_ledger_line_does_not_zero_the_total(tmp_path):
    led = tmp_path / "ledger.jsonl"
    led.write_text(
        json.dumps({"cost_usd": 2.0}) + "\nnot json at all\n" + json.dumps({"cost_usd": 1.0}) + "\n",
        encoding="utf-8",
    )
    g = BudgetGuard(run_id="r", cap_usd=10.0, ledger_path=led)
    assert g.spent_before == pytest.approx(3.0)


def test_unpriced_calls_are_counted_and_surfaced(tmp_path):
    g = BudgetGuard(run_id="r", cap_usd=1.0, ledger_path=tmp_path / "l.jsonl")
    g.charge("qwen3:8b", OLLAMA_META)
    assert g.uncovered_calls == 1
    assert "NOT covered" in g.summary()


# --------------------------------------------------------------------------- #
# A model that cannot spend must never be blocked by a spend cap.
#
# This is a regression test for a real abort: a free local run on the
# 15-document corpus died with BudgetExceeded at $35 of *frontier* spend without
# being able to add a cent to it, and the failure initially looked like a model or
# context problem rather than a bug in the guard.
# --------------------------------------------------------------------------- #


def _over_cap_guard(tmp_path) -> BudgetGuard:
    led = tmp_path / "ledger.jsonl"
    led.write_text(json.dumps({"model": "gpt-5.5", "cost_usd": 35.0}) + "\n", encoding="utf-8")
    return BudgetGuard(run_id="local", cap_usd=25.00, ledger_path=led)


def test_free_model_is_not_blocked_when_the_cap_is_already_exceeded(tmp_path):
    g = _over_cap_guard(tmp_path)
    assert g.spent_cumulative > g.cap_usd
    g.check_before_call("qwen3:8b")  # must not raise


def test_priced_model_is_still_blocked_when_the_cap_is_exceeded(tmp_path):
    g = _over_cap_guard(tmp_path)
    with pytest.raises(BudgetExceeded, match="refusing to start"):
        g.check_before_call("gpt-5.5")


def test_charging_a_free_call_over_the_cap_does_not_raise(tmp_path):
    g = _over_cap_guard(tmp_path)
    usage, cost = g.charge("qwen3:8b", OLLAMA_META)  # must not raise
    assert cost is None
    assert usage["input_tokens"] == 1000


def test_omitting_the_model_keeps_the_unconditional_check(tmp_path):
    # Any caller not yet passing a model gets the old, conservative behaviour.
    g = _over_cap_guard(tmp_path)
    with pytest.raises(BudgetExceeded):
        g.check_before_call()


def test_is_priced_matches_the_rate_card(tmp_path):
    g = _over_cap_guard(tmp_path)
    assert g.is_priced("gpt-5.5") is True
    assert g.is_priced("claude-opus-5") is True
    assert g.is_priced("qwen2.5:3b") is False


# -- 12 Sep 2026: a billing provider may not run an unpriced model ------------------------- #


def test_claude_sonnet_5_cost_matches_the_list_price():
    # $2.00/1M in, $0.20/1M cached, $10.00/1M out (Anthropic list price, 12 Sep 2026).
    cost = call_cost("claude-sonnet-5", {"input_tokens": 1000, "cached_input_tokens": 500, "output_tokens": 200})
    assert cost == pytest.approx((1000 * 2.00 + 500 * 0.20 + 200 * 10.00) / 1_000_000)


def test_refuse_unpriced_stops_a_billing_provider_and_lets_free_and_test_doubles_through():
    with pytest.raises(UnpricedModel, match="not-priced"):
        refuse_unpriced(["gpt-5.5", "not-priced"], "openai")
    with pytest.raises(UnpricedModel):
        refuse_unpriced(["claude-sonnet-5-preview"], "anthropic")
    refuse_unpriced(["gpt-5.5", "claude-sonnet-5"], "openai")  # all priced: fine
    refuse_unpriced(["qwen3:8b"], "ollama")  # free
    refuse_unpriced(["scripted-model"], "p1")  # test double, not a billing provider
    refuse_unpriced(["nope"], "openai", allow_unpriced=True)  # the deliberate override


def _ledger_with_null_rows(tmp_path):
    rows = [
        {"run_id": "r1", "model": "gpt-5.5", "cost_usd": 0.01, "usage": {"input_tokens": 1, "output_tokens": 1}},
        {"run_id": "remit", "model": "claude-sonnet-5", "cost_usd": None,
         "usage": {"input_tokens": 1000, "output_tokens": 100, "cached_input_tokens": 0, "cache_write_tokens": 0}},
        {"run_id": "remit", "model": "claude-sonnet-5", "cost_usd": None,
         "usage": {"input_tokens": 2000, "output_tokens": 200, "cached_input_tokens": 0, "cache_write_tokens": 0}},
        {"run_id": "local", "model": "qwen3:8b", "cost_usd": None, "usage": {"input_tokens": 5, "output_tokens": 5}},
    ]
    path = tmp_path / "ledger.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows) + "not json\n", encoding="utf-8")
    return path, rows


def test_reprice_ledger_dry_run_changes_nothing_and_reports_the_total(tmp_path):
    path, _ = _ledger_with_null_rows(tmp_path)
    before = path.read_bytes()
    r = reprice_ledger(path, "claude-sonnet-5", repriced_on="2026-09-12")
    assert r["rows"] == 2
    assert r["total_usd"] == pytest.approx((3000 * 2.00 + 300 * 10.00) / 1_000_000)
    assert path.read_bytes() == before


def test_reprice_ledger_apply_rewrites_only_the_matching_rows(tmp_path):
    path, rows = _ledger_with_null_rows(tmp_path)
    r = reprice_ledger(path, "claude-sonnet-5", apply=True, repriced_on="2026-09-12", note="test")
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == json.dumps(rows[0]) and lines[3] == json.dumps(rows[3]) and lines[4] == "not json"
    fixed = [json.loads(lines[1]), json.loads(lines[2])]
    assert all(x["cost_usd"] is not None and x["repriced_on"] == "2026-09-12" and x["reprice_note"] == "test" for x in fixed)
    assert sum(x["cost_usd"] for x in fixed) == pytest.approx(r["total_usd"])
    # the guard's cumulative total now includes the corrected rows
    g = BudgetGuard(run_id="t", cap_usd=100, ledger_path=path)
    assert g.spent_before == pytest.approx(0.01 + r["total_usd"])
    # idempotent: nothing left to reprice
    assert reprice_ledger(path, "claude-sonnet-5", repriced_on="x")["rows"] == 0


def test_reprice_ledger_refuses_a_model_that_is_still_unpriced(tmp_path):
    path, _ = _ledger_with_null_rows(tmp_path)
    with pytest.raises(UnpricedModel):
        reprice_ledger(path, "qwen3:8b")


def test_gemini_cost_matches_the_list_price_and_refuses_the_cheap_tier_above_200k():
    # $2.00/1M in, cached at the input rate until confirmed, $12.00/1M out; tier boundary 200K.
    cost = call_cost("gemini-3.1-pro-preview", {"input_tokens": 1000, "cached_input_tokens": 500, "output_tokens": 200})
    assert cost == pytest.approx((1000 * 2.00 + 500 * 2.00 + 200 * 12.00) / 1_000_000)
    with pytest.raises(ValueError, match="tier boundary"):
        call_cost("gemini-3.1-pro-preview", {"input_tokens": 250_000, "cached_input_tokens": 0, "output_tokens": 1})
    refuse_unpriced(["gemini-3.1-pro-preview"], "google")  # priced: allowed
    with pytest.raises(UnpricedModel):
        refuse_unpriced(["gemini-3.1-pro"], "google")  # not the listed id: refused
