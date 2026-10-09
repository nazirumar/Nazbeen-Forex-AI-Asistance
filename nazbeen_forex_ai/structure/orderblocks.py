"""Order blocks detection (deterministic, no look-ahead).

Definitions:
- **Bullish OB**: the last bearish candle immediately before a bullish
  displacement candle. Its [low, high] is the demand zone.
- **Bearish OB**: the last bullish candle immediately before a bearish
  displacement candle. Its [low, high] is the supply zone.

An OB is only knowable once the displacement candle closes, so ``confirmed_at``
is the displacement bar; ``formation_time`` is the OB candle itself.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from nazbeen_forex_ai.structure.types import StructureEvent, candles_to_df


def detect_orderblocks(
    candles: list[Any],
    lookback: int = 20,
    displacement_factor: float = 1.5,
    atr_length: int = 14,
) -> list[StructureEvent]:
    df = candles_to_df(candles)
    events: list[StructureEvent] = []
    if len(df) < 3:
        return events

    # Precompute average range (ATR proxy) for displacement sizing.
    ranges = (df["high"] - df["low"]).astype(float)
    atr = ranges.rolling(atr_length, min_periods=1).mean()

    for t in range(1, len(df)):
        o = float(df["open"].iloc[t])
        c = float(df["close"].iloc[t])
        body = abs(c - o)
        a = float(atr.iloc[t])
        if a <= 0 or body < displacement_factor * a:
            continue

        displacement_up = c > o
        displacement_down = c < o
        if not (displacement_up or displacement_down):
            continue

        # Walk back to the nearest opposite-colour candle within lookback.
        ob_idx = None
        for j in range(t - 1, max(-1, t - 1 - lookback), -1):
            jo = float(df["open"].iloc[j])
            jc = float(df["close"].iloc[j])
            if displacement_up and jc < jo:  # bearish candle before up-move
                ob_idx = j
                break
            if displacement_down and jc > jo:  # bullish candle before down-move
                ob_idx = j
                break
        if ob_idx is None:
            continue

        ob_o = float(df["open"].iloc[ob_idx])
        ob_c = float(df["close"].iloc[ob_idx])
        ob_high = float(df["high"].iloc[ob_idx])
        ob_low = float(df["low"].iloc[ob_idx])
        direction = "bullish" if displacement_up else "bearish"
        ob_time = pd.Timestamp(df["time"].iloc[ob_idx]).to_pydatetime()
        dis_time = pd.Timestamp(df["time"].iloc[t]).to_pydatetime()

        events.append(
            StructureEvent(
                type="ORDERBLOCK",
                direction=direction,
                index=ob_idx,
                start_time=ob_time,
                end_time=dis_time,
                formation_time=ob_time,
                confirmed_at=dis_time,
                level=ob_c,
                levels=[ob_low, ob_high],
                details={
                    "ob_open": ob_o,
                    "ob_close": ob_c,
                    "displacement_index": int(t),
                    "displacement_body": body,
                },
            )
        )
    return events