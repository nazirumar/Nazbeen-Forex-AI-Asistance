"""Migrated audit regression tests — backtesting (Phase 11A).

Source: docs/audits/repro/test_audit_regressions.py (dummy pnl, ignored cost
parameters, walk-forward `overall` not an aggregation).

Migration note: the cost/outcome tests inject a deterministic signal strategy.
They target the ENGINE's cost and outcome logic (CRIT-01), which is now
strategy-injectable; the oscillating fixture alone forms no valid FVG setups
under the corrected structure detectors, so relying on scenario signals there
would test the strategy instead of the engine.
"""

from __future__ import annotations

from datetime import datetime, timezone

from nazbeen_forex_ai.backtesting.engine import run_backtest
from nazbeen_forex_ai.backtesting.walkforward import walk_forward


def _c(i: int, o: float, h: float, l: float, cl: float) -> dict:
    return {
        "time": datetime(2026, 1, 1, 0, i % 60, tzinfo=timezone.utc).isoformat(),
        "open": o,
        "high": h,
        "low": l,
        "close": cl,
        "volume": 10,
    }


def _oscillating_candles(n: int = 240) -> list[dict]:
    out = []
    for i in range(n):
        base = 1.1000 + 0.01 * ((i % 20) / 20.0) * (1 if (i // 20) % 2 == 0 else -1)
        out.append(_c(i, base, base + 0.0015, base - 0.0015, base + 0.0005))
    return out


def _deterministic_strategy(window: list[dict]) -> str:
    """Reliable BUY/SELL signals every 12 bars for engine-mechanics testing."""
    if len(window) % 12 != 0:
        return "WAIT"
    return "BUY" if (len(window) // 12) % 2 == 0 else "SELL"


def test_bug_backtest_applies_cost_parameters() -> None:
    """H-07: commission/slippage/spread params were accepted but never applied.

    Actual before fix: Trade.commission/.slippage/.spread_cost stayed 0.0 for
    every trade (engine.py never referenced the parameters after the signature).
    """
    result = run_backtest(
        _oscillating_candles(),
        commission_pips=5.0,
        slippage_pips=1.0,
        spread_pips=2.0,
        strategy=_deterministic_strategy,
    )
    assert result.total_trades > 0, "engine generated no trades (itself a finding)"
    assert any(
        t.commission > 0 or t.slippage > 0 or t.spread_cost > 0 for t in result.trades
    ), "cost parameters were ignored: every trade has zero cost"


def test_bug_backtest_outcomes_are_not_dummy() -> None:
    """CRIT-01: pnl was hardcoded to 1.0 ('dummy outcome').

    Actual before fix: every trade won => win_rate == 100%, gross_loss == 0,
    drawdown == 0 — fabricated performance figures (MASTER_SPEC §7).
    """
    result = run_backtest(_oscillating_candles(), strategy=_deterministic_strategy)
    assert result.total_trades > 0, "engine generated no trades (itself a finding)"
    assert result.gross_loss > 0 or result.win_rate < 100.0, (
        f"impossible performance: win_rate={result.win_rate}%, "
        f"gross_loss={result.gross_loss} (pnl hardcoded to 1.0)"
    )
    # Real outcomes carry real money values, not the dummy constant 1.0.
    assert all(t.pnl != 1.0 for t in result.trades) or result.net_profit != result.total_trades


def test_bug_walkforward_overall_is_aggregate_of_windows() -> None:
    """M-07: `overall` re-ran the engine on the last test window instead of
    aggregating window results (all_trades was dead code).

    Actual before fix: overall.total_trades == trades(candles[-test_size:])
    != sum(window trades).
    """
    candles = _oscillating_candles(500)
    wf = walk_forward(
        candles, train_size=200, test_size=100, step=100, strategy=_deterministic_strategy
    )
    window_total = sum(w["result"].total_trades for w in wf.windows)
    assert window_total > 0, "walk-forward windows produced no trades (uninformative)"
    assert wf.overall.total_trades == window_total, (
        f"overall={wf.overall.total_trades} != sum(windows)={window_total} — "
        "'overall' is not an aggregation"
    )
    # Aggregation also means combined metrics derive from all window trades.
    all_pnls = [t.pnl for w in wf.windows for t in w["result"].trades]
    assert wf.overall.net_profit == sum(all_pnls)
