"""Walk-forward evaluation with chronological splits.

Integrity guarantees (audit M-07/P-02, fix P1.4):

- ``overall`` is a true aggregation of every out-of-sample window's trades.
- Input chronology is validated: candles must be in strict chronological
  order — a shuffled series would silently corrupt the train/test boundary
  (future data leaking into "past" windows).
- The insufficient-data fallback (train == test on the same candles) is
  **explicitly marked as NOT walk-forward** — it is never reported as an
  out-of-sample result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

from nazbeen_forex_ai.backtesting.engine import BacktestResult, run_backtest, summarize_trades
from nazbeen_forex_ai.structure.types import candles_to_df


@dataclass
class WalkForwardResult:
    windows: List[Dict[str, Any]]
    overall: BacktestResult
    # False when the evaluation could not produce genuine out-of-sample
    # windows (insufficient data) — see `note`.
    is_walk_forward: bool = True
    note: str = field(default="")


def _validate_chronological(candles: List[Dict[str, Any]]) -> None:
    """Raise ValueError unless candle timestamps strictly increase (audit M-07)."""
    if len(candles) < 2:
        return
    try:
        times = candles_to_df(candles)["time"]
        ordered = bool(times.is_monotonic_increasing)
        unique = not bool(times.duplicated().any())
    except Exception as e:
        raise ValueError(f"candle timestamps are unparseable or incomparable: {e}") from e
    if not ordered or not unique:
        raise ValueError(
            "candles must be in strict chronological order (each timestamp later "
            "than the previous one); walk-forward splits assume time flows forward"
        )


def walk_forward(
    candles: List[Dict[str, Any]],
    train_size: int = 200,
    test_size: int = 100,
    step: int = 100,
    strategy: Callable[[List[Dict[str, Any]]], str] | None = None,
) -> WalkForwardResult:
    _validate_chronological(candles)
    windows: List[Dict[str, Any]] = []
    all_trades: List[Any] = []
    if len(candles) < train_size + test_size:
        res = run_backtest(candles, strategy=strategy)
        # P-02: train == test on the same bars is NOT out-of-sample evidence.
        note = (
            f"insufficient data ({len(candles)} candles < train_size {train_size} + "
            f"test_size {test_size}): train and test are identical — this is NOT "
            "a walk-forward (out-of-sample) result"
        )
        windows.append(
            {
                "train": candles,
                "test": candles,
                "result": res,
                "walk_forward": False,
                "reason": note,
            }
        )
        return WalkForwardResult(windows=windows, overall=res, is_walk_forward=False, note=note)
    for i in range(0, len(candles) - train_size - test_size + 1, step):
        train = candles[i : i + train_size]
        test = candles[i + train_size : i + train_size + test_size]
        res_test = run_backtest(test, strategy=strategy)
        windows.append(
            {
                "train_range": [i, i + train_size],
                "test_range": [i + train_size, i + train_size + test_size],
                "result": res_test,
                "walk_forward": True,
            }
        )
        all_trades.extend(res_test.trades)
    # `overall` is a true aggregation of every out-of-sample window's trades.
    overall = summarize_trades(all_trades)
    return WalkForwardResult(windows=windows, overall=overall)
