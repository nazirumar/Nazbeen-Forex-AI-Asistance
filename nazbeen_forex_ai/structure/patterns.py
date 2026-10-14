"""Rejection candles and engulfing patterns.

Deterministic definitions (no look-ahead; knowable at the bar's own close;
``formation_time == confirmed_at == time[t]``):

For bar ``t``: ``range = high - low``, ``body = |close - open|``,
``upper = high - max(open, close)``, ``lower = min(open, close) - low``.

- **Bullish rejection** (hammer/dragonfly-like): the lower wick dominates —
  ``lower >= wick_ratio * body`` **and** ``lower > upper`` **and** the close
  sits in the upper half (``close >= low + 0.5 * range``).
- **Bearish rejection** (shooting-star/inverted hammer-like): ``upper >=
  wick_ratio * body`` **and** ``upper > lower`` **and** the close sits in the
  lower half (``close <= low + 0.5 * range``).
  Invalid: ``range == 0`` (doji of zero range never qualifies).

- **Bullish engulfing** at ``t`` (needs bar ``t-1``): previous bar red
  (``close < open``), current bar green (``close > open``), current body
  engulfs the previous body and closes beyond the previous open
  (``close_t >= open_{t-1}``, ``open_t <= close_{t-1}``) with
  ``body_t >= min_body_ratio * body_{t-1}`` (and ``body_{t-1} > 0``).
- **Bearish engulfing**: previous green, current red, mirrored conditions.

Both detectors are pure functions of the candles: identical input always
produces identical, reproducible output (MASTER_SPEC §3.C).
"""

from __future__ import annotations

from typing import Any, List

import pandas as pd

from nazbeen_forex_ai.structure.types import StructureEvent, candles_to_df


def detect_rejection(candles: list[Any], wick_ratio: float = 2.0) -> list[StructureEvent]:
    """Rejection candles; see module docstring for the exact rules."""
    df = candles_to_df(candles)
    events: List[StructureEvent] = []
    for t in range(len(df)):
        o = float(df["open"].iloc[t])
        c = float(df["close"].iloc[t])
        hi = float(df["high"].iloc[t])
        lo = float(df["low"].iloc[t])
        rng = hi - lo
        if rng <= 0:
            continue
        body = abs(c - o)
        upper = hi - max(o, c)
        lower = min(o, c) - lo
        direction = None
        pattern = None
        if lower >= float(wick_ratio) * body and lower > upper and c >= lo + 0.5 * rng:
            direction, pattern = "bullish", "hammer"
        elif upper >= float(wick_ratio) * body and upper > lower and c <= lo + 0.5 * rng:
            direction, pattern = "bearish", "shooting_star"
        if direction is None:
            continue
        ts = pd.Timestamp(df["time"].iloc[t]).to_pydatetime()
        events.append(
            StructureEvent(
                type="REJECTION",
                direction=direction,
                index=int(t),
                level=c,
                formation_time=ts,
                confirmed_at=ts,
                details={
                    "pattern": pattern,
                    "body": body,
                    "range": rng,
                    "upper_wick": upper,
                    "lower_wick": lower,
                    "wick_ratio": float(wick_ratio),
                    "dominant_wick": lower if direction == "bullish" else upper,
                },
            )
        )
    return events


def detect_engulfing(candles: list[Any], min_body_ratio: float = 1.0) -> list[StructureEvent]:
    """Engulfing patterns; see module docstring for the exact rules."""
    df = candles_to_df(candles)
    events: List[StructureEvent] = []
    for t in range(1, len(df)):
        po = float(df["open"].iloc[t - 1])
        pc = float(df["close"].iloc[t - 1])
        co = float(df["open"].iloc[t])
        cc = float(df["close"].iloc[t])
        prev_body = abs(pc - po)
        body = abs(cc - co)
        if prev_body <= 0 or body < float(min_body_ratio) * prev_body:
            continue
        prev_red, prev_green = pc < po, pc > po
        cur_green, cur_red = cc > co, cc < co
        direction = None
        if prev_red and cur_green and cc >= po and co <= pc:
            direction = "bullish"
        elif prev_green and cur_red and cc <= po and co >= pc:
            direction = "bearish"
        if direction is None:
            continue
        ts = pd.Timestamp(df["time"].iloc[t]).to_pydatetime()
        events.append(
            StructureEvent(
                type="ENGULFING",
                direction=direction,
                index=int(t),
                level=cc,
                formation_time=ts,
                confirmed_at=ts,
                details={
                    "pattern": f"{direction}_engulfing",
                    "body": body,
                    "prev_body": prev_body,
                    "body_ratio": body / prev_body,
                    "min_body_ratio": float(min_body_ratio),
                },
            )
        )
    return events
