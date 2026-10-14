"""Liquidity: equal highs/lows, BSL/SSL pools and liquidity sweeps.

Deterministic definitions (no look-ahead; every timestamp is a real candle time):

- **Equal highs** (legacy): adjacent bars ``i``/``i+1`` with
  ``|high_i - high_{i+1}| <= tolerance`` → level ``high_i``, knowable once bar
  ``i+1`` closes (``formation_time`` = bar i, ``confirmed_at`` = bar i+1).
- **Equal lows**: symmetric rule on ``low``.
- **BSL pool** (buy-side liquidity above old highs): a chronological cluster of
  at least ``min_touches`` confirmed **swing highs** whose prices are within
  ``tolerance`` of the cluster's first price. ``level`` is the first swing's
  price (a real candle high); ``formation_time`` = first touch,
  ``confirmed_at`` = the ``min_touches``-th touch (the bar at which the pool
  became valid). **SSL pool**: symmetric rule on swing lows.
- **Sweep**: after a pool is confirmed, the first bar within ``max_bars`` that
  trades *through* the pool level and **closes back on the original side**
  (classic stop hunt):
    - SSL sweep (bullish): ``low < level - tolerance`` and ``close > level``.
    - BSL sweep (bearish): ``high > level + tolerance`` and ``close < level``.
  A close that stays beyond the level is a *break*, not a sweep — no event is
  emitted (invalid condition handled by omission, never by guessing).

The clustering rule is prefix-stable: extending the candle series can only add
new pools after the already-confirmed ones, and a pool's ``level``/``confirmed``
are fixed once it is emitted — so detector output never repaints (audit M-10 /
brief 11E §2).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List

import pandas as pd

from nazbeen_forex_ai.structure.swings import detect_swings
from nazbeen_forex_ai.structure.types import StructureEvent, candles_to_df

# Sort anchor for events whose timestamps are somehow missing (never in
# practice); tz-aware so it can be compared with candle times (UTC everywhere).
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _time_at(df: pd.DataFrame, i: int) -> datetime:
    return pd.Timestamp(df["time"].iloc[i]).to_pydatetime()


def _sort_key(event: StructureEvent) -> datetime:
    ts = event.confirmed_at or event.formation_time
    if ts is None:
        return _EPOCH
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def _flush_pool(
    cluster: List[Any], kind: str, direction: str, min_touches: int
) -> StructureEvent | None:
    if len(cluster) < min_touches:
        return None
    anchor = cluster[0]
    confirm = cluster[min_touches - 1]
    return StructureEvent(
        type="LIQUIDITY",
        direction=direction,
        index=anchor.index,
        level=float(anchor.price),
        levels=[float(s.price) for s in cluster],
        formation_time=anchor.time,
        confirmed_at=confirm.time,
        details={
            "kind": kind,
            "touches": len(cluster),
            "swing_indices": [int(s.index) for s in cluster],
            "confirmed_index": int(confirm.index),
        },
    )


def _cluster_swings(swings: List[Any], kind: str, direction: str, tolerance: float, min_touches: int) -> List[StructureEvent]:
    out: List[StructureEvent] = []
    cluster: List[Any] = []
    for s in swings:
        if not cluster:
            cluster = [s]
            continue
        if abs(float(s.price) - float(cluster[0].price)) <= tolerance:
            cluster.append(s)
        else:
            ev = _flush_pool(cluster, kind, direction, min_touches)
            if ev is not None:
                out.append(ev)
            cluster = [s]
    ev = _flush_pool(cluster, kind, direction, min_touches)
    if ev is not None:
        out.append(ev)
    return out


def _detect_liquidity_df(
    df: pd.DataFrame,
    tolerance: float,
    swing_left: int,
    swing_right: int,
    min_touches: int,
) -> List[StructureEvent]:
    events: List[StructureEvent] = []
    if len(df) < 2:
        return events

    # --- adjacent equal highs / equal lows (level pairs) --------------------
    for i in range(len(df) - 1):
        h_a = float(df["high"].iloc[i])
        h_b = float(df["high"].iloc[i + 1])
        if abs(h_a - h_b) <= tolerance:
            events.append(
                StructureEvent(
                    type="LIQUIDITY",
                    direction="bearish",
                    index=i,
                    level=h_a,
                    formation_time=_time_at(df, i),
                    confirmed_at=_time_at(df, i + 1),
                    details={
                        "kind": "equal_high",
                        "bars": [int(i), int(i + 1)],
                        "confirmed_index": int(i + 1),
                    },
                )
            )
        l_a = float(df["low"].iloc[i])
        l_b = float(df["low"].iloc[i + 1])
        if abs(l_a - l_b) <= tolerance:
            events.append(
                StructureEvent(
                    type="LIQUIDITY",
                    direction="bullish",
                    index=i,
                    level=l_a,
                    formation_time=_time_at(df, i),
                    confirmed_at=_time_at(df, i + 1),
                    details={
                        "kind": "equal_low",
                        "bars": [int(i), int(i + 1)],
                        "confirmed_index": int(i + 1),
                    },
                )
            )

    # --- BSL/SSL pools from confirmed swings --------------------------------
    touches = max(1, int(min_touches))
    swings = detect_swings(df, left=swing_left, right=swing_right)
    highs = [s for s in swings if s.type == "high"]
    lows = [s for s in swings if s.type == "low"]
    # BSL rests above old highs (bearish-labelled, same convention as the
    # legacy equal_high events); SSL rests below old lows.
    events.extend(_cluster_swings(highs, "bsl", "bearish", tolerance, touches))
    events.extend(_cluster_swings(lows, "ssl", "bullish", tolerance, touches))

    events.sort(key=_sort_key)
    return events


def detect_liquidity(
    candles: list[Any],
    tolerance: float = 0.0001,
    swing_left: int = 3,
    swing_right: int = 3,
    min_touches: int = 2,
) -> list[StructureEvent]:
    """Equal highs/lows + BSL/SSL pools (see module docstring for the rules)."""
    return _detect_liquidity_df(
        candles_to_df(candles), tolerance, swing_left, swing_right, min_touches
    )


def detect_sweeps(
    candles: list[Any],
    liquidity: list[StructureEvent] | None = None,
    tolerance: float = 0.0001,
    max_bars: int = 50,
) -> list[StructureEvent]:
    """Liquidity sweeps of previously confirmed pools (see module docstring).

    ``liquidity`` may pass in an already-computed pool list (the API does) to
    avoid recomputing it; it is assumed to come from :func:`detect_liquidity`
    on the *same* candles.
    """
    df = candles_to_df(candles)
    if len(df) == 0:
        return []
    pools = liquidity if liquidity is not None else _detect_liquidity_df(df, tolerance, 3, 3, 2)

    out: List[StructureEvent] = []
    for pool in pools:
        kind = (pool.details or {}).get("kind")
        if kind not in ("bsl", "ssl", "equal_high", "equal_low"):
            continue
        level = pool.level
        if level is None:
            continue
        start = int((pool.details or {}).get("confirmed_index", pool.index or 0)) + 1
        stop = min(len(df), start + max(1, int(max_bars)))
        for t in range(start, stop):
            hi = float(df["high"].iloc[t])
            lo = float(df["low"].iloc[t])
            cl = float(df["close"].iloc[t])
            bullish = kind in ("ssl", "equal_low")
            if bullish and lo < level - tolerance and cl > level:
                direction = "bullish"
                label = "ssl_sweep"
                swept_to = lo
                break
            if (not bullish) and hi > level + tolerance and cl < level:
                direction = "bearish"
                label = "bsl_sweep"
                swept_to = hi
                break
        else:
            continue
        out.append(
            StructureEvent(
                type="SWEEP",
                direction=direction,
                index=t,
                level=float(level),
                formation_time=_time_at(df, t),
                confirmed_at=_time_at(df, t),
                details={
                    "kind": label,
                    "pool_kind": kind,
                    "level": float(level),
                    "pool_time": pool.formation_time.isoformat() if pool.formation_time else None,
                    "swept_to": swept_to,
                    "close": cl,
                    "confirmed_index": int(t),
                },
            )
        )
    out.sort(key=_sort_key)
    return out
