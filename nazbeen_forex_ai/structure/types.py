"""Core data structures and utilities for market structure detection.

All detectors are deterministic and avoid look-ahead bias.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

import pandas as pd


def to_utc_z(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)
    return ts.isoformat().replace("+00:00", "Z")


@dataclass
class Candle:
    time: datetime
    open: float
    high: float
    low: float
    close: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "time": to_utc_z(self.time),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
        }


@dataclass
class Swing:
    type: Literal["high", "low"]
    index: int
    time: datetime
    price: float
    confirmed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "index": self.index,
            "time": to_utc_z(self.time),
            "price": self.price,
            "confirmed": self.confirmed,
        }


@dataclass
class StructureEvent:
    type: str  # BOS/CHOCH/MSS/FVG/OB/Liquidity/...
    direction: Literal["bullish", "bearish", "neutral"] | None = None
    index: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    level: float | None = None
    levels: list[float] | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": self.type,
            "direction": self.direction,
            "index": self.index,
            "level": self.level,
            "levels": self.levels or [],
            "details": self.details or {},
        }
        if self.start_time:
            d["start_time"] = to_utc_z(self.start_time)
        if self.end_time:
            d["end_time"] = to_utc_z(self.end_time)
        return d


def candles_to_df(candles: list[Candle | dict]) -> pd.DataFrame:
    data = []
    for c in candles:
        if isinstance(c, Candle):
            data.append((c.time, c.open, c.high, c.low, c.close))
        else:
            t = c["time"]
            if isinstance(t, str):
                # handle Z
                try:
                    t = datetime.fromisoformat(t.replace("Z", "+00:00"))
                except Exception:
                    t = datetime.fromisoformat(t)
            data.append((t, float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"])))
    df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close"])
    return df