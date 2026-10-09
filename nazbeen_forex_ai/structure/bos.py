"""BOS/CHOCH/MSS detection based on confirmed swing structure.

Deterministic definitions (no look-ahead):
- A swing at bar ``i`` is only usable once ``right`` bars have closed, i.e. from
  bar ``i + right`` onward. We never reference a swing before it is confirmed.
- **BOS** (break of structure): close breaks the most recent *confirmed* swing
  level in the direction of the prevailing trend (continuation), or establishes
  the first trend when the trend is still neutral.
- **CHOCH** (change of character): close breaks the most recent confirmed swing
  level *against* the prevailing trend.
- **MSS** (market structure shift): a counter-trend break (CHOCH) that is
  accompanied by displacement — a candle whose body is at least
  ``displacement_factor`` × the average range. MSS is therefore a *distinct,
  stricter* subset of CHOCH, not a duplicate.

Every event records both ``formation_time`` (the broken swing's bar) and
``confirmed_at`` (the breaking bar) so signals are never backdated.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from nazbeen_forex_ai.structure.swings import detect_swings
from nazbeen_forex_ai.structure.types import StructureEvent, candles_to_df


def _avg_range(df: pd.DataFrame, t: int, length: int) -> float:
    """Average high-low range over the ``length`` bars up to and including ``t``."""
    start = max(0, t - length + 1)
    window = df.iloc[start : t + 1]
    if len(window) == 0:
        return 0.0
    return float((window["high"] - window["low"]).mean())


def detect_bos_choch_mss(
    candles: list[Any],
    left: int = 1,
    right: int = 1,
    displacement_factor: float = 1.5,
    atr_length: int = 14,
) -> list[StructureEvent]:
    df = candles_to_df(candles)
    if len(df) < left + right + 1:
        return []

    swings = detect_swings(df, left=left, right=right)
    # Order swings by the bar at which they become confirmable.
    pending = sorted(swings, key=lambda s: s.index + right)

    events: list[StructureEvent] = []
    confirmed_highs: list[Any] = []
    confirmed_lows: list[Any] = []
    broken: set[int] = set()
    trend = "neutral"
    si = 0

    for t in range(len(df)):
        # Promote swings that are now confirmed (index + right <= t).
        while si < len(pending) and pending[si].index + right <= t:
            s = pending[si]
            (confirmed_highs if s.type == "high" else confirmed_lows).append(s)
            si += 1

        close = float(df["close"].iloc[t])
        open_ = float(df["open"].iloc[t])
        bar_time = pd.Timestamp(df["time"].iloc[t]).to_pydatetime()

        sh = next((s for s in reversed(confirmed_highs) if s.index not in broken), None)
        sl = next((s for s in reversed(confirmed_lows) if s.index not in broken), None)

        body = abs(close - open_)
        atr = _avg_range(df, t, atr_length)
        has_displacement = atr > 0 and body >= displacement_factor * atr

        if sh is not None and close > sh.price:
            broken.add(sh.index)
            counter = trend == "bearish"
            etype = ("MSS" if has_displacement else "CHOCH") if counter else "BOS"
            trend_before, trend = trend, "bullish"
            events.append(
                StructureEvent(
                    type=etype,
                    direction="bullish",
                    index=t,
                    start_time=sh.time,
                    end_time=bar_time,
                    formation_time=sh.time,
                    confirmed_at=bar_time,
                    level=float(sh.price),
                    details={
                        "close": close,
                        "trend_before": trend_before,
                        "trend_after": trend,
                        "displacement": bool(has_displacement),
                        "broken_swing_index": int(sh.index),
                    },
                )
            )
        elif sl is not None and close < sl.price:
            broken.add(sl.index)
            counter = trend == "bullish"
            etype = ("MSS" if has_displacement else "CHOCH") if counter else "BOS"
            trend_before, trend = trend, "bearish"
            events.append(
                StructureEvent(
                    type=etype,
                    direction="bearish",
                    index=t,
                    start_time=sl.time,
                    end_time=bar_time,
                    formation_time=sl.time,
                    confirmed_at=bar_time,
                    level=float(sl.price),
                    details={
                        "close": close,
                        "trend_before": trend_before,
                        "trend_after": trend,
                        "displacement": bool(has_displacement),
                        "broken_swing_index": int(sl.index),
                    },
                )
            )

    return events