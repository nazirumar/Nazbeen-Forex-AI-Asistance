"""Risk engine tests."""

from __future__ import annotations

import pytest

from nazbeen_forex_ai.risk.calculations import (
    calculate_rr,
    get_symbol_spec,
    position_size,
    round_to_tick,
)
from nazbeen_forex_ai.risk.scenarios import evaluate_trade_plan, ScenarioConfig


def test_rr_calculation_long():
    rr = calculate_rr(1.1000, 1.0990, 1.1020)
    assert rr == pytest.approx(2.0)


def test_rr_calculation_short():
    rr = calculate_rr(1.1020, 1.1030, 1.1000)
    assert rr == pytest.approx(2.0)


def test_position_size_clamped():
    spec = get_symbol_spec("EURUSD")
    lot = position_size(10000, 1.0, 1.1000, 1.0990, spec)
    assert lot >= 0.0


def test_bullish_valid_plan():
    res = evaluate_trade_plan(
        bias="BULLISH",
        entry=1.1000,
        sl=1.0990,
        tp=1.1020,
        spread_pips=0.5,
        symbol="EURUSD",
        account_balance=10000.0,
        config=ScenarioConfig(risk_percent=1.0, min_rr=1.0, max_spread_pips=2.0),
    )
    assert res.decision == "BUY"
    assert res.rr >= 1.0
    assert res.entry_levels[0] > res.sl


def test_bearish_valid_plan():
    res = evaluate_trade_plan(
        bias="BEARISH",
        entry=1.1020,
        sl=1.1030,
        tp=1.1000,
        spread_pips=0.5,
        symbol="EURUSD",
        account_balance=10000.0,
        config=ScenarioConfig(risk_percent=1.0, min_rr=1.0, max_spread_pips=2.0),
    )
    assert res.decision == "SELL"
    assert res.entry_levels[0] < res.sl


def test_invalid_rr_returns_wait():
    res = evaluate_trade_plan(
        bias="BULLISH",
        entry=1.1000,
        sl=1.0990,
        tp=1.1005,
        spread_pips=0.5,
        symbol="EURUSD",
        config=ScenarioConfig(risk_percent=1.0, min_rr=2.0, max_spread_pips=2.0),
    )
    assert res.decision == "WAIT"


def test_high_spread_returns_wait():
    res = evaluate_trade_plan(
        bias="BULLISH",
        entry=1.1000,
        sl=1.0990,
        tp=1.1020,
        spread_pips=3.0,
        symbol="EURUSD",
        config=ScenarioConfig(risk_percent=1.0, min_rr=1.0, max_spread_pips=2.0),
    )
    assert res.decision == "WAIT"


def test_inconsistent_levels_returns_wait():
    res = evaluate_trade_plan(
        bias="BULLISH",
        entry=1.1000,
        sl=1.1010,  # SL above entry
        tp=1.1020,
    )
    assert res.decision == "WAIT"


def test_round_to_tick():
    spec = get_symbol_spec("EURUSD")
    assert round_to_tick(1.10005, spec.tick_size) == pytest.approx(1.10005)
