"""Walk-forward integrity tests (Phase 11C — audits M-07/P-02/P-03, fix P1.4).

Contract:
- Insufficient-data fallback (train == test) is explicitly marked as NOT
  walk-forward and never presented as out-of-sample.
- Input chronology is validated: shuffled or duplicated timestamps raise.
- The engine consumes each signal once (no overlapping trades).
- An uncalibrated probability model reports NO confidence interval (M-08).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from nazbeen_forex_ai.backtesting.engine import run_backtest
from nazbeen_forex_ai.backtesting.probability import evaluate_probability
from nazbeen_forex_ai.backtesting.walkforward import walk_forward


def _c(i: int, o: float, h: float, l: float, cl: float) -> dict:
    return {
        "time": (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=i)).isoformat(),
        "open": o,
        "high": h,
        "low": l,
        "close": cl,
        "volume": 10,
    }


def _oscillating(n: int) -> list[dict]:
    out = []
    for i in range(n):
        base = 1.1000 + 0.01 * ((i % 20) / 20.0) * (1 if (i // 20) % 2 == 0 else -1)
        out.append(_c(i, base, base + 0.0015, base - 0.0015, base + 0.0005))
    return out


def _deterministic_strategy(window: list[dict]) -> str:
    if len(window) % 12 != 0:
        return "WAIT"
    return "BUY" if (len(window) // 12) % 2 == 0 else "SELL"


# ---------------------------------------------------------------------------
# P-02: the fallback is never reported as walk-forward
# ---------------------------------------------------------------------------

def test_insufficient_data_fallback_is_marked_not_walk_forward() -> None:
    candles = _oscillating(50)
    wf = walk_forward(candles, train_size=200, test_size=100, step=100)

    assert wf.is_walk_forward is False
    assert "NOT a walk-forward" in wf.note
    window = wf.windows[0]
    assert window["walk_forward"] is False
    assert "NOT a walk-forward" in window["reason"]
    # train and test are literally the same bars — leakage, labeled as such.
    assert window["train"] is window["test"]


def test_normal_windows_are_marked_walk_forward() -> None:
    wf = walk_forward(_oscillating(400), train_size=150, test_size=100, step=50)
    assert wf.is_walk_forward is True
    assert wf.note == ""
    assert wf.windows and all(w["walk_forward"] is True for w in wf.windows)


def test_empty_input_is_marked_not_walk_forward() -> None:
    wf = walk_forward([], train_size=200, test_size=100)
    assert wf.is_walk_forward is False
    assert wf.overall.total_trades == 0


# ---------------------------------------------------------------------------
# Chronology validation (M-07 remainder)
# ---------------------------------------------------------------------------

def test_walk_forward_rejects_shuffled_input() -> None:
    candles = _oscillating(300)
    shuffled = [candles[i] for i in range(299, -1, -1)]
    with pytest.raises(ValueError, match="chronological"):
        walk_forward(shuffled, train_size=100, test_size=50, step=50)


def test_walk_forward_rejects_duplicate_timestamps() -> None:
    candles = _oscillating(300)
    candles[150] = dict(candles[149])
    with pytest.raises(ValueError, match="chronological"):
        walk_forward(candles, train_size=100, test_size=50, step=50)


def test_walk_forward_accepts_sorted_input() -> None:
    wf = walk_forward(_oscillating(300), train_size=100, test_size=50, step=50)
    assert wf.windows


# ---------------------------------------------------------------------------
# P-03: each signal is consumed once (no overlapping trades)
# ---------------------------------------------------------------------------

def test_engine_never_overlapping_trades() -> None:
    result = run_backtest(_oscillating(400), strategy=_deterministic_strategy)
    assert result.total_trades > 1, "fixture must produce multiple trades to be informative"
    for earlier, later in zip(result.trades, result.trades[1:]):
        assert earlier.exit_time is not None
        assert later.entry_time > earlier.exit_time, (
            "overlapping trades: a new entry began before the previous exit — "
            "stale signals are being reused (audit P-03)"
        )


def test_each_bar_used_at_most_once_for_entries() -> None:
    result = run_backtest(_oscillating(400), strategy=_deterministic_strategy)
    entries = [t.entry_time for t in result.trades]
    assert entries == sorted(entries), "entries must be chronological"
    assert len(entries) == len(set(entries)), "duplicate entry bars: signal reused"


# ---------------------------------------------------------------------------
# M-08: no fabricated confidence intervals
# ---------------------------------------------------------------------------

def test_probability_never_reports_ci_without_calibration() -> None:
    insufficient = evaluate_probability([])
    assert insufficient.probability is None
    assert insufficient.calibrated is False
    assert insufficient.confidence_interval == [], (
        "an uncalibrated model must report NO confidence interval"
    )

    stub = evaluate_probability([{}] * 100)
    assert stub.probability is None
    assert stub.calibrated is False
    assert stub.confidence_interval == [], (
        "the old [0.3, 0.7] stub interval was a fabricated figure"
    )
