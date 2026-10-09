"""Event-driven backtester with strict chronological evaluation.

Correctness notes (audit CRIT-01):
- Trade outcomes are **simulated**, never hardcoded. Every trade resolves by
  hitting SL, hitting TP, or being closed at the end of the data.
- Entries happen at the **open of the bar after** the signal bar (the signal uses
  only ``candles[:i]``, so there is no look-ahead). Exits are simulated bar by bar.
- When both SL and TP fall inside one candle, the **stop-loss is assumed first**
  (conservative).
- Spread, slippage and commission are applied to every trade; PnL is
  position-aware (scales with ``contract_size * lots``).
- Metrics (win rate, expectancy, profit factor, drawdown) are computed from the
  real trade list — no fabricated figures.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal

from nazbeen_forex_ai.structure.types import Candle, candles_to_df
from nazbeen_forex_ai.structure.analysis import evaluate_scenario

PIPS = 0.0001


@dataclass
class Trade:
    entry_time: Any
    exit_time: Any = None
    side: Literal["LONG", "SHORT"] | None = None
    entry: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    lots: float = 0.0
    exit_price: float | None = None
    result: Literal["WIN", "LOSS", "BREAK_EVEN"] | None = None
    pnl: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0
    spread_cost: float = 0.0


@dataclass
class BacktestResult:
    trades: List[Trade] = field(default_factory=list)
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    break_evens: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    max_drawdown: float = 0.0
    net_profit: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0


def _default_strategy(window: List[Dict[str, Any]]) -> str:
    """BUY/SELL/WAIT from the deterministic scenario engine (uses only `window`)."""
    try:
        return str(evaluate_scenario(window, [], []).get("decision", "WAIT"))
    except Exception:
        return "WAIT"


def summarize_trades(trades: List[Trade]) -> BacktestResult:
    """Recompute all performance metrics from a concrete trade list."""
    result = BacktestResult(trades=trades)
    result.total_trades = len(trades)
    result.wins = sum(1 for t in trades if t.result == "WIN")
    result.losses = sum(1 for t in trades if t.result == "LOSS")
    result.break_evens = sum(1 for t in trades if t.result == "BREAK_EVEN")

    pnls = [t.pnl for t in trades]
    result.net_profit = float(sum(pnls))
    result.gross_profit = float(sum(p for p in pnls if p > 0))
    result.gross_loss = float(-sum(p for p in pnls if p < 0))

    if result.total_trades:
        result.win_rate = 100.0 * result.wins / result.total_trades
        result.expectancy = result.net_profit / result.total_trades
    if result.gross_loss > 0:
        result.profit_factor = result.gross_profit / result.gross_loss
    elif result.gross_profit > 0:
        result.profit_factor = math.inf

    # Max drawdown from the cumulative equity curve (peak-to-trough).
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    result.max_drawdown = float(max_dd)
    return result


def run_backtest(
    candles: List[Dict[str, Any]],
    commission_pips: float = 0.0,
    slippage_pips: float = 0.0,
    spread_pips: float = 0.0,
    strategy: Callable[[List[Dict[str, Any]]], str] | None = None,
    sl_pips: float = 10.0,
    tp_pips: float = 20.0,
    pip_size: float = PIPS,
    contract_size: float = 100000.0,
    lots: float = 1.0,
    min_bars: int = 30,
) -> BacktestResult:
    if not candles:
        return BacktestResult()
    df = candles_to_df(candles)
    n = len(df)
    if n <= min_bars + 1:
        return BacktestResult()

    strat = strategy or _default_strategy
    spread_price = spread_pips * pip_size
    slip_price = slippage_pips * pip_size
    commission_price = commission_pips * pip_size
    unit = contract_size * lots  # PnL per 1.0 price move, position-aware

    times = [df["time"].iloc[i] for i in range(n)]
    opens = df["open"].astype(float).tolist()
    highs = df["high"].astype(float).tolist()
    lows = df["low"].astype(float).tolist()
    closes = df["close"].astype(float).tolist()

    trades: List[Trade] = []
    i = min_bars
    while i < n - 1:
        window = candles[:i]  # strictly before bar i — no look-ahead
        decision = strat(window)
        if decision not in ("BUY", "SELL"):
            i += 1
            continue

        side = "LONG" if decision == "BUY" else "SHORT"
        raw_entry = opens[i]
        if side == "LONG":
            sl = raw_entry - sl_pips * pip_size
            tp = raw_entry + tp_pips * pip_size
            eff_entry = raw_entry + spread_price + slip_price
        else:
            sl = raw_entry + sl_pips * pip_size
            tp = raw_entry - tp_pips * pip_size
            eff_entry = raw_entry - spread_price - slip_price

        exit_price: float | None = None
        exit_time = times[n - 1]
        result: str | None = None
        exit_i = n - 1

        for j in range(i + 1, n):
            high, low = highs[j], lows[j]
            if side == "LONG":
                sl_hit = low <= sl
                tp_hit = high >= tp
                if sl_hit or tp_hit:
                    # Conservative: when both are inside one candle, assume SL.
                    exit_price = sl if sl_hit else tp
                    result = "LOSS" if sl_hit else "WIN"
                    exit_time = times[j]
                    exit_i = j
                    break
            else:
                sl_hit = high >= sl
                tp_hit = low <= tp
                if sl_hit or tp_hit:
                    exit_price = sl if sl_hit else tp
                    result = "LOSS" if sl_hit else "WIN"
                    exit_time = times[j]
                    exit_i = j
                    break

        if exit_price is None:
            # Ran out of data: close at the final close.
            exit_price = closes[n - 1]
            exit_time = times[n - 1]
            exit_i = n - 1
            if exit_price > raw_entry:
                result = "WIN" if side == "LONG" else "LOSS"
            elif exit_price < raw_entry:
                result = "LOSS" if side == "LONG" else "WIN"
            else:
                result = "BREAK_EVEN"

        if side == "LONG":
            eff_exit = exit_price - slip_price
            gross = (eff_exit - eff_entry) * unit
        else:
            eff_exit = exit_price + slip_price
            gross = (eff_entry - eff_exit) * unit

        commission_cost = commission_price * unit
        pnl = gross - commission_cost

        trades.append(
            Trade(
                entry_time=times[i],
                exit_time=exit_time,
                side=side,
                entry=raw_entry,
                sl=sl,
                tp=tp,
                lots=lots,
                exit_price=exit_price,
                result=result,  # type: ignore[arg-type]
                pnl=pnl,
                commission=commission_price,
                slippage=2.0 * slip_price,
                spread_cost=spread_price,
            )
        )
        i = max(exit_i, i + 1)

    return summarize_trades(trades)
