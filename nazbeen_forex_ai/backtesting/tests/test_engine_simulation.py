"""Backtesting engine simulation tests (Phase 11A workstream 11A.1).

Covers chronological entries/exits, real SL/TP simulation, the conservative
both-touched rule, spread/slippage/commission costs, position-aware PnL and
honest performance metrics.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from nazbeen_forex_ai.backtesting.engine import run_backtest, summarize_trades


def _c(i: int, o: float, h: float, l: float, cl: float) -> dict:
    return {
        "time": datetime(2026, 1, 1, 0, i, tzinfo=timezone.utc).isoformat(),
        "open": o,
        "high": h,
        "low": l,
        "close": cl,
        "volume": 10,
    }


def _buy_at_30(window: list[dict]) -> str:
    return "BUY" if len(window) == 30 else "WAIT"


def _flat_then(n_flat: int, then: list[dict]) -> list[dict]:
    """n_flat flat bars (indices 0..n_flat-1) followed by `then` bars."""
    flat = [_c(i, 1.1000, 1.1001, 1.0999, 1.1000) for i in range(n_flat)]
    extra = [_c(n_flat + k, o, h, l, cl) for k, (o, h, l, cl) in enumerate(then)]
    return flat + extra


def _winner_fixture() -> list[dict]:
    """Entry at bar 30 open, then a rally to TP 1.1020 at bar 34."""
    rally = []
    for j in range(10):
        o = 1.1000 + 0.0005 * j
        c = o + 0.0005
        rally.append((o, c + 0.0001, o - 0.0001, c))
    return _flat_then(31, rally)


def _loser_fixture() -> list[dict]:
    """Entry at bar 30 open, then a drop to SL 1.0990 at bar 31."""
    return _flat_then(31, [(1.1000, 1.1005, 1.0989, 1.0995)])


def _both_touched_fixture() -> list[dict]:
    """Bar 31 spans both SL (low 1.0985 ≤ 1.0990) and TP (high 1.1025 ≥ 1.1020)."""
    return _flat_then(31, [(1.1000, 1.1025, 1.0985, 1.1000)])


def test_winner_trade_hits_take_profit() -> None:
    r = run_backtest(_winner_fixture(), strategy=_buy_at_30, min_bars=30)
    assert r.total_trades == 1
    t = r.trades[0]
    assert t.side == "LONG"
    assert t.result == "WIN"
    assert t.exit_price == pytest.approx(1.1020)
    assert t.pnl == pytest.approx(200.0)  # 0.0020 × 100000 × 1 lot
    assert r.wins == 1 and r.losses == 0
    assert r.win_rate == pytest.approx(100.0)
    assert r.gross_profit == pytest.approx(200.0)
    assert r.gross_loss == pytest.approx(0.0)


def test_loser_trade_hits_stop_loss() -> None:
    r = run_backtest(_loser_fixture(), strategy=_buy_at_30, min_bars=30)
    assert r.total_trades == 1
    t = r.trades[0]
    assert t.result == "LOSS"
    assert t.exit_price == pytest.approx(1.0990)
    assert t.pnl == pytest.approx(-100.0)  # 0.0010 adverse × 100000
    assert r.losses == 1
    assert r.gross_loss == pytest.approx(100.0)
    assert r.net_profit == pytest.approx(-100.0)
    assert r.max_drawdown == pytest.approx(100.0)


def test_both_sl_and_tp_in_one_candle_assumes_sl_first() -> None:
    """Conservative rule: ambiguity inside one candle resolves to the stop."""
    r = run_backtest(_both_touched_fixture(), strategy=_buy_at_30, min_bars=30)
    assert r.total_trades == 1
    t = r.trades[0]
    assert t.result == "LOSS"
    assert t.exit_price == pytest.approx(1.0990)  # SL, not TP
    assert t.pnl < 0


def test_costs_reduce_pnl_deterministically() -> None:
    """spread(2) + slippage(1×2) + commission(5) = 9 pips = $90 on 1 lot."""
    free = run_backtest(_winner_fixture(), strategy=_buy_at_30, min_bars=30)
    paid = run_backtest(
        _winner_fixture(),
        strategy=_buy_at_30,
        min_bars=30,
        commission_pips=5.0,
        slippage_pips=1.0,
        spread_pips=2.0,
    )
    assert free.total_trades == paid.total_trades == 1
    assert free.trades[0].pnl == pytest.approx(200.0)
    assert paid.trades[0].pnl == pytest.approx(110.0)
    assert free.trades[0].pnl - paid.trades[0].pnl == pytest.approx(90.0)
    t = paid.trades[0]
    assert t.spread_cost == pytest.approx(0.0002)
    assert t.slippage == pytest.approx(0.0002)  # round trip: 1 pip in + 1 pip out
    assert t.commission == pytest.approx(0.0005)


def test_pnl_is_position_aware() -> None:
    """Doubling lot size doubles PnL (position-aware, not fixed constants)."""
    one = run_backtest(_winner_fixture(), strategy=_buy_at_30, min_bars=30, lots=1.0)
    two = run_backtest(_winner_fixture(), strategy=_buy_at_30, min_bars=30, lots=2.0)
    assert two.trades[0].pnl == pytest.approx(2.0 * one.trades[0].pnl)
    assert two.trades[0].lots == 2.0


def _mixed_fixture() -> list[dict]:
    """Bar 30 entry → TP win; bar 50 entry → SL loss."""
    bars: list[tuple] = []
    # decline from 1.1050 back to 1.1000 over bars 41..49
    for k in range(9):
        o = 1.1050 - 0.0005 * (k + 1)
        c = 1.1050 - 0.0005 * (k + 2)
        bars.append((o, o + 0.0001, c - 0.0001, c))
    extra = [
        (1.1000, 1.1001, 1.0999, 1.1000),  # 50: entry bar
        (1.1000, 1.1001, 1.0989, 1.0995),  # 51: SL hit
    ]
    winner = _winner_fixture()  # flat 0..30, rally 31..40
    return winner + [_c(40 + 1 + k, o, h, l, c) for k, (o, h, l, c) in enumerate(bars)] + [
        _c(50, *extra[0]),
        _c(51, *extra[1]),
    ]


def _buy_at_30_and_50(window: list[dict]) -> str:
    return "BUY" if len(window) in (30, 50) else "WAIT"


def test_metrics_win_rate_expectancy_profit_factor_drawdown() -> None:
    r = run_backtest(_mixed_fixture(), strategy=_buy_at_30_and_50, min_bars=30)
    assert r.total_trades == 2
    assert r.wins == 1 and r.losses == 1
    assert r.win_rate == pytest.approx(50.0)
    assert r.net_profit == pytest.approx(100.0)      # +200 − 100
    assert r.gross_profit == pytest.approx(200.0)
    assert r.gross_loss == pytest.approx(100.0)
    assert r.profit_factor == pytest.approx(2.0)
    assert r.expectancy == pytest.approx(50.0)       # 100 / 2 trades
    assert r.max_drawdown == pytest.approx(100.0)    # peak 200 → 100


def test_entries_and_exits_are_chronological_and_non_overlapping() -> None:
    r = run_backtest(_mixed_fixture(), strategy=_buy_at_30_and_50, min_bars=30)
    assert r.total_trades == 2
    prev_exit = None
    for t in r.trades:
        assert t.entry_time < t.exit_time, "exit must precede entry (order violated)"
        if prev_exit is not None:
            assert t.entry_time >= prev_exit, "trades must not overlap"
        prev_exit = t.exit_time


def test_open_position_closed_at_end_of_data() -> None:
    """A trade still open on the final bar is closed at the last close."""
    # Gentle drift that never reaches TP (+20 pips) and never drops to SL (−10).
    bars = [(1.1000 + 0.0001 * j, 1.1000 + 0.0001 * j + 0.0001,
             1.1000 + 0.0001 * j - 0.0001, 1.1000 + 0.0001 * (j + 1)) for j in range(10)]
    candles = _flat_then(31, bars)
    r = run_backtest(candles, strategy=_buy_at_30, min_bars=30)
    assert r.total_trades == 1
    t = r.trades[0]
    assert t.exit_time.isoformat() == candles[-1]["time"]
    assert t.result in ("WIN", "LOSS", "BREAK_EVEN")
    # +3 pips of drift: still a win but below TP, proving a data-end close.
    assert t.exit_price < 1.1020
    assert t.result == "WIN" and t.pnl > 0


def test_summarize_trades_recomputes_from_trades() -> None:
    r = run_backtest(_mixed_fixture(), strategy=_buy_at_30_and_50, min_bars=30)
    agg = summarize_trades(list(r.trades))
    assert agg.total_trades == r.total_trades
    assert agg.net_profit == pytest.approx(r.net_profit)
    assert agg.max_drawdown == pytest.approx(r.max_drawdown)
    assert agg.profit_factor == pytest.approx(r.profit_factor)


def test_no_dummy_constant_outcomes() -> None:
    """No trade carries the old hardcoded pnl=1.0 (CRIT-01)."""
    r = run_backtest(_mixed_fixture(), strategy=_buy_at_30_and_50, min_bars=30)
    assert r.trades
    assert all(t.pnl != 1.0 for t in r.trades)
    assert r.net_profit != float(r.total_trades)  # not "every trade won +1"
