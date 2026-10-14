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


def validate_orderblocks(
    candles: list[Any], order_blocks: list[StructureEvent]
) -> list[StructureEvent]:
    """Order-block validation: retest (mitigation) and invalidation lifecycle.

    Deterministic rules evaluated only on bars **after** the OB's confirming
    displacement bar (no look-ahead; first qualifying bar wins, so the output
    is stable when the series grows):

    For an OB zone ``[z_low, z_high] = [levels[0], levels[1]]``:

    - **retest** (the classic "return to the order block"): first later bar
      whose range overlaps the zone (``low < z_high and high > z_low``).
      ``touches`` counts all such bars after confirmation.
    - **invalidation**: first later bar whose **close** finishes beyond the
      zone against the OB's direction (bullish OB: ``close < z_low``;
      bearish OB: ``close > z_high``) — that OB is dead and must never
      support a setup.

    ``details["lifecycle"].state`` is monotone: ``open`` → ``retested`` →
    ``invalidated``. An OB with no later bars is ``open`` (unknown, not
    "valid forever"). Re-validating twice returns the same values.
    """
    df = candles_to_df(candles)
    out: list[StructureEvent] = []
    for ev in order_blocks:
        details = dict(ev.details or {})
        conf = details.get("displacement_index")
        levels = ev.levels or []
        lifecycle: dict[str, Any]
        if conf is None or len(levels) < 2:
            lifecycle = {"state": "unknown", "reason": "missing displacement index"}
        else:
            z_low, z_high = float(levels[0]), float(levels[1])
            bullish = ev.direction == "bullish"
            retest: tuple[int, Any] | None = None
            invalidated: tuple[int, Any] | None = None
            touches = 0
            for j in range(int(conf) + 1, len(df)):
                hi = float(df["high"].iloc[j])
                lo = float(df["low"].iloc[j])
                cl = float(df["close"].iloc[j])
                if lo < z_high and hi > z_low:
                    touches += 1
                    if retest is None:
                        retest = (
                            int(j),
                            pd.Timestamp(df["time"].iloc[j]).to_pydatetime(),
                        )
                if ((cl < z_low) if bullish else (cl > z_high)) and invalidated is None:
                    invalidated = (
                        int(j),
                        pd.Timestamp(df["time"].iloc[j]).to_pydatetime(),
                    )
                    break
            if invalidated:
                state = "invalidated"
            elif retest:
                state = "retested"
            else:
                state = "open"
            lifecycle = {"state": state, "touches": touches}
            if retest:
                lifecycle["retest_index"] = retest[0]
                lifecycle["retest_time"] = retest[1].isoformat().replace("+00:00", "Z")
            if invalidated:
                lifecycle["invalidated_index"] = invalidated[0]
                lifecycle["invalidated_time"] = invalidated[1].isoformat().replace("+00:00", "Z")
        details["lifecycle"] = lifecycle
        out.append(
            StructureEvent(
                type=ev.type,
                direction=ev.direction,
                index=ev.index,
                start_time=ev.start_time,
                end_time=ev.end_time,
                formation_time=ev.formation_time,
                confirmed_at=ev.confirmed_at,
                level=ev.level,
                levels=ev.levels,
                details=details,
            )
        )
    return out