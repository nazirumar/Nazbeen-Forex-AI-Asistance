"""Liquidity zones (equal highs/lows, sweeps)."""

from __future__ import annotations

from typing import Any

from nazbeen_forex_ai.structure.types import StructureEvent, candles_to_df


def detect_liquidity(candles: list[Any], tolerance: float = 0.0001) -> list[StructureEvent]:
    df = candles_to_df(candles)
    events: list[StructureEvent] = []
    # equal highs
    for i in range(len(df) - 1):
        if abs(df["high"].iloc[i] - df["high"].iloc[i + 1]) <= tolerance:
            events.append(
                StructureEvent(
                    type="LIQUIDITY",
                    direction="bearish",
                    index=i,
                    level=float(df["high"].iloc[i]),
                    details={"kind": "equal_high"},
                )
            )
    return events