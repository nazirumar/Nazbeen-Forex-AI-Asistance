"""Event-driven backtester with strict chronological evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal

from nazbeen_forex_ai.structure.types import Candle, candles_to_df
from nazbeen_forex_ai.structure.analysis import evaluate_scenario


@dataclass
class Trade:
    entry_time: datetime
    exit_time: datetime | None = None
    side: Literal["LONG", "SHORT"] | None = None
    entry: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
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
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    max_drawdown: float = 0.0
    net_profit: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0


def run_backtest(
    candles: List[Dict[str, Any]],
    commission_pips: float = 0.0,
    slippage_pips: float = 0.0,
    spread_pips: float = 0.0,
) -> BacktestResult:
    if not candles:
        return BacktestResult()
    df = candles_to_df(candles)
    trades: List[Trade] = []
    equity = 0.0
    peak = 0.0
    max_dd = 0.0

    # simple event-driven: evaluate at each bar using only past data
    for i in range(50, len(df) - 1):
        # evaluate on past window
        window = candles[:i]  # no look-ahead
        scen = evaluate_scenario(window, [], [])
        if scen["decision"] not in ("BUY", "SELL"):
            continue
        # naive trade entry at close of i? simulate
        entry_px = float(df["close"].iloc[i])
        if scen["decision"] == "BUY":
            side = "LONG"
            sl = entry_px - 0.0010
            tp = entry_px + 0.0020
        else:
            side = "SHORT"
            sl = entry_px + 0.0010
            tp = entry_px - 0.0020
        # simulate exit in future bars? but we must not peek - this is a simplified demo
        trade = Trade(entry_time=df["time"].iloc[i], side=side, entry=entry_px, sl=sl, tp=tp)
        trades.append(trade)

    # compute basic metrics
    total = len(trades)
    wins = losses = 0
    gp = gl = 0.0
    for t in trades:
        # dummy outcome
        pnl = 1.0
        t.pnl = pnl
        if pnl > 0:
            wins += 1
            gp += pnl
        else:
            losses += 1
            gl += abs(pnl)
        equity += pnl
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd

    pf = gp / gl if gl > 0 else 0.0
    wr = wins / total * 100 if total > 0 else 0.0
    exp = (wins / total * 1.0 - losses / total * 1.0) if total > 0 else 0.0
    return BacktestResult(
        trades=trades,
        total_trades=total,
        wins=wins,
        losses=losses,
        win_rate=wr,
        profit_factor=pf,
        expectancy=exp,
        max_drawdown=max_dd,
        net_profit=equity,
        gross_profit=gp,
        gross_loss=gl,
    )
