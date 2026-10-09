"""Swing detection (HH/HL/LH/LL). Confirmation uses lookback/lookahead to avoid look-ahead bias."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from nazbeen_forex_ai.structure.types import Swing, candles_to_df


def detect_swings(
    candles_or_df,
    left: int = 3,
    right: int = 3,
    min_strength: int = 1,
) -> list[Swing]:
    if isinstance(candles_or_df, list):
        df = candles_to_df(candles_or_df)
    else:
        df = candles_or_df
    swings: list[Swing] = []
    if len(df) < left + right + 1:
        return swings
    for i in range(left, len(df) - right):
        # swing high
        high = df["high"].iloc[i]
        is_sh = True
        for j in range(i - left, i):
            if df["high"].iloc[j] >= high:
                is_sh = False
                break
        for j in range(i + 1, i + right + 1):
            if df["high"].iloc[j] > high:
                is_sh = False
                break
        if is_sh:
            swings.append(
                Swing(
                    type="high",
                    index=i,
                    time=pd.Timestamp(df["time"].iloc[i]).to_pydatetime(),
                    price=float(high),
                    confirmed=True,
                )
            )
        # swing low
        low = df["low"].iloc[i]
        is_sl = True
        for j in range(i - left, i):
            if df["low"].iloc[j] <= low:
                is_sl = False
                break
        for j in range(i + 1, i + right + 1):
            if df["low"].iloc[j] < low:
                is_sl = False
                break
        if is_sl:
            swings.append(
                Swing(
                    type="low",
                    index=i,
                    time=pd.Timestamp(df["time"].iloc[i]).to_pydatetime(),
                    price=float(low),
                    confirmed=True,
                )
            )
    # sort by index
    swings.sort(key=lambda x: x.index)
    return swings


def classify_structure(swings: list[Swing]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    # track last high/low
    last_high: Swing | None = None
    last_low: Swing | None = None
    for s in swings:
        if s.type == "high":
            if last_high is None:
                sh = "HH_or_first"
            else:
                if s.price > last_high.price:
                    sh = "HH"
                elif s.price < last_high.price:
                    sh = "LH"
                else:
                    sh = "EH"
            result.append({"swing": s.to_dict(), "label": sh})
            last_high = s
        else:  # low
            if last_low is None:
                sl = "LL_or_first"
            else:
                if s.price < last_low.price:
                    sl = "LL"
                elif s.price > last_low.price:
                    sl = "HL"
                else:
                    sl = "EL"
            result.append({"swing": s.to_dict(), "label": sl})
            last_low = s
    return result