"""Walk-forward evaluation with chronological splits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from nazbeen_forex_ai.backtesting.engine import BacktestResult, run_backtest, summarize_trades


@dataclass
class WalkForwardResult:
    windows: List[Dict[str, Any]]
    overall: BacktestResult


def walk_forward(
    candles: List[Dict[str, Any]],
    train_size: int = 200,
    test_size: int = 100,
    step: int = 100,
    strategy: Callable[[List[Dict[str, Any]]], str] | None = None,
) -> WalkForwardResult:
    windows: List[Dict[str, Any]] = []
    all_trades: List[Any] = []
    if len(candles) < train_size + test_size:
        res = run_backtest(candles, strategy=strategy)
        windows.append({"train": candles, "test": candles, "result": res})
        return WalkForwardResult(windows=windows, overall=res)
    for i in range(0, len(candles) - train_size - test_size + 1, step):
        train = candles[i : i + train_size]
        test = candles[i + train_size : i + train_size + test_size]
        res_test = run_backtest(test, strategy=strategy)
        windows.append(
            {
                "train_range": [i, i + train_size],
                "test_range": [i + train_size, i + train_size + test_size],
                "result": res_test,
            }
        )
        all_trades.extend(res_test.trades)
    # `overall` is a true aggregation of every out-of-sample window's trades.
    overall = summarize_trades(all_trades)
    return WalkForwardResult(windows=windows, overall=overall)
