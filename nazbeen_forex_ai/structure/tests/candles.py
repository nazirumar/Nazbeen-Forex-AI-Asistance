"""Deterministic candle builders for Phase 11E detector and golden tests.

Every helper produces real ``dict`` candles (the same shape the providers
return) on a fixed UTC 15-minute grid so timestamps are always on the candle
grid and tests are reproducible — no randomness anywhere.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Sequence, Tuple

BASE = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
STEP = timedelta(minutes=15)

Row = Tuple[float, float, float, float]  # (open, high, low, close)


def t(i: int, step_minutes: int = 15) -> datetime:
    """UTC candle time for bar index ``i`` on a fixed grid."""
    return BASE + i * timedelta(minutes=step_minutes)


def z(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def bars(rows: Sequence[Row], step_minutes: int = 15, offset: int = 0) -> List[Dict]:
    """Build candle dicts from (open, high, low, close) rows.

    ``offset`` shifts the starting bar index so appended tails continue the
    same fixed time grid instead of restarting at bar 0.
    """
    out: List[Dict] = []
    for i, (o, h, low, c) in enumerate(rows):
        j = offset + i
        out.append(
            {
                "time": z(t(j, step_minutes)),
                "open": float(o),
                "high": float(h),
                "low": float(low),
                "close": float(c),
            }
        )
    return out


def rising_bars(n: int = 9, base: float = 1.1000, step: float = 0.0010) -> List[Dict]:
    """Alternating zigzag with rising troughs and peaks → bullish swing_bias.

    Even bars are trough bars (low at ``base + k*step``), odd bars are peak
    bars (high at trough + 1.5*step), so with ``left=right=1`` every peak/after
    the first trough is a confirmed swing and consecutive comparisons are all
    higher-high/higher-low.
    """
    rows: List[Row] = []
    for i in range(n):
        if i % 2 == 0:
            k = i // 2
            low = base + k * step
            rows.append((low + 0.0001, low + 0.0002, low, low + 0.0001))
        else:
            k = i // 2
            high = base + 1.5 * step + k * step
            rows.append((high - 0.0001, high, high - 0.0002, high - 0.0001))
    return bars(rows)


def falling_bars(n: int = 9, base: float = 1.1000, step: float = 0.0010) -> List[Dict]:
    """Mirror of :func:`rising_bars` → bearish swing_bias."""
    rows: List[Row] = []
    for i in range(n):
        if i % 2 == 0:
            k = i // 2
            high = base - k * step
            rows.append((high - 0.0001, high, high - 0.0002, high - 0.0001))
        else:
            k = i // 2
            low = base - 1.5 * step - k * step
            rows.append((low + 0.0001, low + 0.0002, low, low + 0.0001))
    return bars(rows)


def flat_bars(n: int = 12, price: float = 1.1000, rng: float = 0.0004) -> List[Dict]:
    """Sideways, low-variance bars → NEUTRAL bias, no structures."""
    rows: List[Row] = []
    for i in range(n):
        wobble = (rng / 2) if i % 2 == 0 else -(rng / 2)
        o = price
        c = price + wobble
        h = max(o, c) + rng / 4
        low = min(o, c) - rng / 4
        rows.append((o, h, low, c))
    return bars(rows)


def quiet_around(price: float, n: int, rng: float = 0.0006) -> List[Row]:
    """Small-range rows around ``price`` (used as ATR context)."""
    rows: List[Row] = []
    for i in range(n):
        o = price + (0.0001 if i % 2 else 0.0)
        c = price - (0.0001 if i % 2 else 0.0)
        rows.append((o, price + rng / 2, price - rng / 2, c))
    return rows
