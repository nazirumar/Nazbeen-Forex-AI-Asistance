"""Displacement candles (impulsive, high-conviction bars).

Deterministic definition (no look-ahead, knowable at the bar's own close):

For bar ``t`` with ``range = high - low``, ``body = |close - open|`` and
``ATR_t = mean(range over the atr_length bars up to and including t)``:

- **Bullish displacement**: ``close > open``, ``body >= factor * ATR_t`` and
  ``body >= body_ratio * range`` (the body dominates the wicks).
- **Bearish displacement**: ``close < open`` with the same two conditions.

Invalid conditions: ``range == 0`` (flat bar), ``ATR_t == 0`` (all-flat window)
or ``close == open`` — never reported as displacement.

``formation_time == confirmed_at == time[t]``: the pattern needs only its own
bar to be known, so it is never backdated (audit M-05/M-10).
"""

from __future__ import annotations

from typing import Any, List

import pandas as pd

from nazbeen_forex_ai.structure.types import StructureEvent, candles_to_df


def detect_displacement(
    candles: list[Any],
    factor: float = 1.5,
    atr_length: int = 14,
    body_ratio: float = 0.6,
) -> list[StructureEvent]:
    """Detect displacement candles; see module docstring for the rules."""
    df = candles_to_df(candles)
    events: List[StructureEvent] = []
    if len(df) == 0:
        return events

    ranges = (df["high"] - df["low"]).astype(float)
    atr = ranges.rolling(int(atr_length), min_periods=1).mean()

    for t in range(len(df)):
        o = float(df["open"].iloc[t])
        c = float(df["close"].iloc[t])
        rng = float(ranges.iloc[t])
        body = abs(c - o)
        a = float(atr.iloc[t])
        if rng <= 0 or a <= 0 or c == o:
            continue
        if body < float(factor) * a:
            continue
        if body < float(body_ratio) * rng:
            continue
        direction = "bullish" if c > o else "bearish"
        events.append(
            StructureEvent(
                type="DISPLACEMENT",
                direction=direction,
                index=int(t),
                level=c,
                formation_time=pd.Timestamp(df["time"].iloc[t]).to_pydatetime(),
                confirmed_at=pd.Timestamp(df["time"].iloc[t]).to_pydatetime(),
                details={
                    "body": body,
                    "range": rng,
                    "body_atr_ratio": body / a,
                    "body_range_ratio": body / rng,
                    "atr_length": int(atr_length),
                    "factor": float(factor),
                },
            )
        )
    return events
