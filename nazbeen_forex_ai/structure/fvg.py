"""FVG detection and mitigation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from nazbeen_forex_ai.structure.types import StructureEvent, candles_to_df


def detect_fvg(candles_or_df, threshold_pips: float = 0.5) -> list[StructureEvent]:
    """Detect fair-value gaps on a 3-candle basis (no look-ahead).

    Definitions (c1, c2, c3 are chronological):
      - Bullish FVG (gap UP):   c1.high < c3.low  → zone [c1.high, c3.low]
      - Bearish FVG (gap DOWN): c1.low  > c3.high → zone [c3.high, c1.low]

    A gap is only knowable once c3 has closed, so formation_time == confirmed_at
    == c3.time; the pattern never backdates to c1 (audit CRIT-02 / M-05).
    """
    df = candles_to_df(candles_or_df) if isinstance(candles_or_df, list) else candles_or_df
    events: list[StructureEvent] = []
    pip = 0.0001
    min_gap = max(0.0, float(threshold_pips)) * pip
    for i in range(len(df) - 2):
        # 3-candle: c1, c2 (impulse), c3 (confirms the imbalance)
        c1 = df.iloc[i]
        c2 = df.iloc[i + 1]
        c3 = df.iloc[i + 2]
        t1 = pd.Timestamp(c1["time"]).to_pydatetime()
        t2 = pd.Timestamp(c2["time"]).to_pydatetime()
        t3 = pd.Timestamp(c3["time"]).to_pydatetime()

        # bullish FVG: gap up (c1.high below c3.low)
        if c1["high"] < c3["low"]:
            gap = float(c3["low"]) - float(c1["high"])
            if gap >= min_gap:
                events.append(
                    StructureEvent(
                        type="FVG",
                        direction="bullish",
                        index=i + 1,
                        start_time=t1,
                        end_time=t3,
                        formation_time=t3,
                        confirmed_at=t3,
                        level=float(c1["high"]),
                        levels=[float(c1["high"]), float(c3["low"])],
                        details={"gap": gap, "origin": t2.isoformat()},
                    )
                )
        # bearish FVG: gap down (c1.low above c3.high)
        if c1["low"] > c3["high"]:
            gap = float(c1["low"]) - float(c3["high"])
            if gap >= min_gap:
                events.append(
                    StructureEvent(
                        type="FVG",
                        direction="bearish",
                        index=i + 1,
                        start_time=t1,
                        end_time=t3,
                        formation_time=t3,
                        confirmed_at=t3,
                        level=float(c1["low"]),
                        levels=[float(c3["high"]), float(c1["low"])],
                        details={"gap": gap, "origin": t2.isoformat()},
                    )
                )
    return events