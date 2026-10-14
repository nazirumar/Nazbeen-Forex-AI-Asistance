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
                        details={
                            "gap": gap,
                            "origin": t2.isoformat(),
                            # c3's index: the bar that confirmed the gap.
                            "confirmed_index": int(i + 2),
                        },
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
                        details={
                            "gap": gap,
                            "origin": t2.isoformat(),
                            "confirmed_index": int(i + 2),
                        },
                    )
                )
    return events


def annotate_fvg_lifecycle(
    candles_or_df, fvgs: list[StructureEvent]
) -> list[StructureEvent]:
    """Annotate each FVG with its retest / mitigation / invalidation status.

    Definitions (all evaluated on bars strictly *after* the gap's confirmation
    bar — no look-ahead; the first qualifying bar wins, so results are stable
    when the series is extended):

    For a **bullish** gap ``[b, t]`` = ``[levels[0], levels[1]]`` (price comes
    from above and retraces down), and symmetrically for a bearish gap (price
    comes from below and retraces up):

    - ``retest``: first later bar whose range overlaps the zone
      (bullish: ``low < t and high > b``; bearish: ``high > b and low < t``).
    - ``mitigation``: first later bar whose **close** enters the zone
      (bullish: ``close <= t``; bearish: ``close >= b``) — the imbalance was
      traded through by real closes, not just a wick.
    - ``invalidation``: first later bar whose close finishes **beyond the far
      edge** of the zone (bullish: ``close < b``; bearish: ``close > t``) —
      the gap failed entirely.

    ``lifecycle.state`` is monotone: ``open`` → ``retested`` → ``mitigated`` →
    ``invalidated`` (``invalidated`` may also occur directly, e.g. when price
    jumps the whole zone). Events whose confirmation bar is the last bar are
    reported as ``open`` — absence of a later bar is *unknown*, not "valid".
    """
    df = candles_to_df(candles_or_df) if isinstance(candles_or_df, list) else candles_or_df
    out: list[StructureEvent] = []
    for ev in fvgs:
        details = dict(ev.details or {})
        conf = details.get("confirmed_index")
        levels = ev.levels or []
        if conf is None or len(levels) < 2:
            details["lifecycle"] = {"state": "unknown", "reason": "missing confirmation index"}
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
            continue

        bottom, top = float(levels[0]), float(levels[1])
        bullish = ev.direction == "bullish"
        retest = mitigated = invalidated = None
        start = int(conf) + 1
        for j in range(start, len(df)):
            hi = float(df["high"].iloc[j])
            lo = float(df["low"].iloc[j])
            cl = float(df["close"].iloc[j])
            j_time = pd.Timestamp(df["time"].iloc[j]).to_pydatetime()
            overlap = (lo < top and hi > bottom) if bullish else (hi > bottom and lo < top)
            if retest is None and overlap:
                retest = (int(j), j_time)
            if mitigated is None and ((cl <= top) if bullish else (cl >= bottom)):
                mitigated = (int(j), j_time)
            if invalidated is None and ((cl < bottom) if bullish else (cl > top)):
                invalidated = (int(j), j_time)
                # The gap is dead: no later bar can "retest" a dead gap.
                break

        if invalidated:
            state = "invalidated"
        elif mitigated:
            state = "mitigated"
        elif retest:
            state = "retested"
        else:
            state = "open"
        lifecycle: dict[str, Any] = {"state": state}
        if retest:
            lifecycle["retest_index"], lifecycle["retest_time"] = retest[0], retest[1].isoformat().replace("+00:00", "Z")
        if mitigated:
            lifecycle["mitigated_index"] = mitigated[0]
            lifecycle["mitigated_time"] = mitigated[1].isoformat().replace("+00:00", "Z")
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