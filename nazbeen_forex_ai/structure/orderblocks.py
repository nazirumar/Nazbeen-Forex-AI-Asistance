"""Order blocks detection (basic)."""

from __future__ import __annotations__

from typing import Any

from nazbeen_forex_ai.structure.types import StructureEvent, candles_to_df


def detect_orderblocks(candles: list[Any], lookback: int = 20) -> list[StructureEvent]:
    df = candles_to_df(candles)
    events: list[StructureEvent] = []
    # Simple OB: last bearish candle before strong bullish move? placeholder deterministic
    for i in range(1, len(df) - 1):
        c = df.iloc[i]
        # mark as potential if it's a down candle followed contextually
        events.append(
            StructureEvent(
                type="ORDERBLOCK",
                direction="neutral",
                index=i,
                level=float(c["close"]),
                details={"source": "basic"},
            )
        )
    return events[:5]  # keep small for now