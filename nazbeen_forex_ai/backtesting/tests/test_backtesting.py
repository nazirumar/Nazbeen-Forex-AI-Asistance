"""Backtesting tests."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from nazbeen_forex_ai.backtesting.engine import run_backtest
from nazbeen_forex_ai.backtesting.walkforward import walk_forward
from nazbeen_forex_ai.backtesting.probability import evaluate_probability
from nazbeen_forex_ai.structure.types import Candle


def make_candles(n: int = 300):
    c = []
    t = datetime(2026, 1, 1)
    p = 1.1000
    for i in range(n):
        o = p
        close = p + (0.0001 if i % 5 == 0 else -0.00005)
        h = max(o, close) + 0.00002
        l = min(o, close) - 0.00002
        c.append(Candle(time=t + timedelta(minutes=i), open=o, high=h, low=l, close=close).to_dict())
        p = close
    return c


def test_backtest_reproducible():
    c = make_candles(100)
    r1 = run_backtest(c)
    r2 = run_backtest(c)
    assert r1.total_trades == r2.total_trades


def test_walk_forward_runs():
    c = make_candles(400)
    wf = walk_forward(c, train_size=150, test_size=100, step=50)
    assert wf.windows is not None


def test_no_lookahead_crash():
    c = make_candles(50)
    r = run_backtest(c)
    assert r.total_trades >= 0


def test_probability_returns_null_insufficient():
    res = evaluate_probability([])
    assert res.probability is None
    res2 = evaluate_probability([{}] * 100)
    assert res2.probability is None
    assert res2.sample_size == 100


def test_metrics_consistent():
    c = make_candles(150)
    r = run_backtest(c)
    assert r.wins + r.losses == r.total_trades or r.total_trades == 0
