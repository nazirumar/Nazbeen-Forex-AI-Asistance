"""FVG detection and mitigation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from nazbeen_forex_ai.structure.types import StructureEvent, candles_to_df


def detect_fvg(candles_or_df, threshold_pips: float = 0.5) -> list[StructureEvent]:
    df = candles_to_df(candles_or_df) if isinstance(candles_or_df, list) else candles_or_df
    events: list[StructureEvent] = []
    for i in range(len(df) - 2):
        # 3-candle: c1, c2 (gap), c3
        c1 = df.iloc[i]
        c2 = df.iloc[i + 1]
        c3 = df.iloc[i + 2]  # future relative? but we only look back? i+2 is forward index but we're scanning; no look-ahead in decision: we detect after c2 formed using confirmed state? this is formation detection on closed candles.
        # bullish FVG: c1.low > c3.high (gap up)
        if c1["low"] > c3["high"]:
            gap = c1["low"] - c3["high"]
            events.append(
                StructureEvent(
                    type="FVG",
                    direction="bullish",
                    index=i + 1,
                    start_time=pd.Timestamp(c3["time"]).to_pydatetime(),
                    end_time=pd.Timestamp(c1["time"]).to_pydatetime(),
                    level=c1["low"],
                    levels=[float(c3["high"]), float(c1["low"])],
                    details={"gap": float(gap)},
                )
            )
        # bearish FVG
        if c1["high"] < c3["low"]:
            gap = c3["low"] - c1["high"]
            events.append(
                StructureEvent(
                    type="FVG",
                    direction="bearish",
                    index=i + 1,
                    start_time=pd.Timestamp(c1["time"]).to_pydatetime(),
                    end_time=pd.Timestamp(c3["time"]).to_pydatetime(),
                    level=c1["high"],
                    levels=[float(c1["high"]), float(c3["low"])],
                    details={"gap": float(gap)},
                )
            )
    return events