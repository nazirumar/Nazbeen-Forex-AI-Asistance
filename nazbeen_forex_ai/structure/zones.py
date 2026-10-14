"""Premium/discount zones, support/resistance levels and S/R flips.

Deterministic definitions (no look-ahead; every timestamp is a real candle
time; first qualifying bar wins so results are stable when the series grows):

- **Premium/discount**: dealing range = ``[lowest low, highest high]`` over the
  last ``lookback`` bars; ``midpoint = (high + low) / 2``. The last close above
  the midpoint is *premium* (bearish-labelled zone), below is *discount*
  (bullish-labelled), exactly at is *equilibrium*. Only the current state is
  reported (a rolling window cannot be prefix-tested for repaint — it is
  reported with its ``bars_used`` so the UI knows exactly which window was
  used). Invalid when ``high <= low`` (no range) → ``[]``.

- **Support/resistance**: chronological clusters of confirmed swing lows
  (support) and swing highs (resistance) whose prices lie within ``tolerance``
  of the cluster's first touch. A cluster becomes a level at its
  ``min_touches``-th touch: ``level`` = mean of the first ``min_touches`` touch
  prices (fixed once confirmed — later touches never move it), ``formation`` =
  first touch, ``confirmed_at`` = the confirming touch. Homogeneous clusters
  only: a cluster mixing highs and lows is dropped (invalid condition).

- **S/R flip**: a confirmed level that is **broken by a close** beyond it
  (resistance: ``close > level + tolerance``; support: ``close < level -
  tolerance``) and then **held on a retest** — resistance→support: a later bar
  trades back down to the level (``low < level + tolerance``) and **closes
  above it** (``close > level``); support→resistance is the mirror. The first
  break+hold pair within ``max_bars`` of each other emits one flip; a break
  with no hold produces no event (an invalidated level, not a flip).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

import pandas as pd

from nazbeen_forex_ai.structure.swings import detect_swings
from nazbeen_forex_ai.structure.types import StructureEvent, candles_to_df

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _t(df: pd.DataFrame, i: int) -> datetime:
    return pd.Timestamp(df["time"].iloc[i]).to_pydatetime()


def _key(ev: StructureEvent) -> datetime:
    ts = ev.confirmed_at or ev.formation_time
    if ts is None:
        return _EPOCH
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def detect_premium_discount(candles: list[Any], lookback: int = 100) -> list[StructureEvent]:
    """Current premium/discount state; see module docstring for the rules."""
    df = candles_to_df(candles)
    if len(df) == 0:
        return []
    window = df.iloc[-max(1, int(lookback)):]
    hi = float(window["high"].max())
    lo = float(window["low"].min())
    if hi <= lo:
        # Flat/degenerate range: reporting a midpoint would be fabrication.
        return []
    midpoint = (hi + lo) / 2.0
    price = float(df["close"].iloc[-1])
    if price > midpoint:
        zone, direction = "premium", "bearish"
    elif price < midpoint:
        zone, direction = "discount", "bullish"
    else:
        zone, direction = "equilibrium", "neutral"
    last_t = _t(df, len(df) - 1)
    return [
        StructureEvent(
            type="PREMIUM_DISCOUNT",
            direction=direction,
            index=int(len(df) - 1),
            level=midpoint,
            formation_time=last_t,
            confirmed_at=last_t,
            details={
                "zone": zone,
                "price": price,
                "range_high": hi,
                "range_low": lo,
                "midpoint": midpoint,
                # Normalised position of the close inside the range: -1 = low,
                # +1 = high, 0 = equilibrium.
                "position": (price - midpoint) / ((hi - lo) / 2.0),
                "bars_used": int(len(window)),
                "lookback": int(lookback),
            },
        )
    ]


def _cluster_levels(
    touches: List[Any],
    kind: str,
    direction: str,
    tolerance: float,
    min_touches: int,
) -> List[StructureEvent]:
    """Group chronological swing touches into S/R levels (first-price anchored)."""
    out: List[StructureEvent] = []
    cluster: List[Any] = []

    def flush() -> None:
        if len(cluster) < min_touches:
            return
        head = cluster[0]
        confirm = cluster[min_touches - 1]
        # Level is fixed by the *first* min_touches touches: later touches may
        # raise `touches` but never move the level (no repaint by extension).
        level = sum(float(s.price) for s in cluster[:min_touches]) / min_touches
        out.append(
            StructureEvent(
                type="SR",
                direction=direction,
                index=int(confirm.index),
                level=level,
                formation_time=head.time,
                confirmed_at=confirm.time,
                details={
                    "kind": kind,
                    "touches": len(cluster),
                    "touch_prices": [float(s.price) for s in cluster],
                    "touch_indices": [int(s.index) for s in cluster],
                    "confirmed_index": int(confirm.index),
                    "tolerance": tolerance,
                },
            )
        )

    for s in touches:
        if not cluster:
            cluster = [s]
        elif abs(float(s.price) - float(cluster[0].price)) <= tolerance:
            cluster.append(s)
        else:
            flush()  # close the finished cluster *before* starting a new one
            cluster = [s]
    flush()
    return out


def detect_support_resistance(
    candles: list[Any],
    tolerance: float = 0.0005,
    min_touches: int = 2,
    swing_left: int = 3,
    swing_right: int = 3,
    lookback: Optional[int] = None,
) -> list[StructureEvent]:
    """Support/resistance from clustered swing touches; see module docstring."""
    df = candles_to_df(candles)
    if lookback is not None:
        df = df.iloc[-max(1, int(lookback)):]
    need = swing_left + swing_right + 1
    if len(df) < need:
        return []
    touches_n = max(2, int(min_touches))
    swings = detect_swings(df, left=swing_left, right=swing_right)
    highs = [s for s in swings if s.type == "high"]
    lows = [s for s in swings if s.type == "low"]
    # Resistance sits above (bearish-labelled), support below (bullish).
    levels = _cluster_levels(highs, "resistance", "bearish", tolerance, touches_n)
    levels += _cluster_levels(lows, "support", "bullish", tolerance, touches_n)
    levels.sort(key=_key)
    return levels


def detect_sr_flips(
    candles: list[Any],
    tolerance: float = 0.0005,
    min_touches: int = 2,
    swing_left: int = 3,
    swing_right: int = 3,
    max_bars: int = 100,
) -> list[StructureEvent]:
    """Support/resistance flips; see module docstring for the rules."""
    df = candles_to_df(candles)
    levels = detect_support_resistance(
        candles, tolerance=tolerance, min_touches=min_touches,
        swing_left=swing_left, swing_right=swing_right,
    )
    out: List[StructureEvent] = []
    for lvl in levels:
        kind = (lvl.details or {}).get("kind")
        level = lvl.level
        conf = (lvl.details or {}).get("confirmed_index")
        if level is None or conf is None:
            continue
        resistance = kind == "resistance"
        break_at: Optional[int] = None
        for j in range(int(conf) + 1, min(len(df), int(conf) + 1 + int(max_bars))):
            cl = float(df["close"].iloc[j])
            if (cl > level + tolerance) if resistance else (cl < level - tolerance):
                break_at = j
                break
        if break_at is None:
            continue
        for k in range(break_at + 1, min(len(df), break_at + 1 + int(max_bars))):
            hi = float(df["high"].iloc[k])
            lo = float(df["low"].iloc[k])
            cl = float(df["close"].iloc[k])
            held = (lo < level + tolerance and cl > level) if resistance else (
                hi > level - tolerance and cl < level
            )
            if not held:
                continue
            out.append(
                StructureEvent(
                    type="SR_FLIP",
                    direction="bullish" if resistance else "bearish",
                    index=int(k),
                    level=float(level),
                    formation_time=_t(df, break_at),
                    confirmed_at=_t(df, k),
                    details={
                        "kind": "resistance_to_support" if resistance else "support_to_resistance",
                        "prior_kind": kind,
                        "level": float(level),
                        "broke_index": int(break_at),
                        "broke_at": _t(df, break_at).isoformat().replace("+00:00", "Z"),
                        "confirmed_index": int(k),
                    },
                )
            )
            break
    out.sort(key=_key)
    return out
