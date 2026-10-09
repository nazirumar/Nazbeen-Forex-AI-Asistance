"""Filters: spread, volatility, session."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


def check_spread(spread_pips: float | None, max_spread_pips: float) -> bool:
    if spread_pips is None:
        return True  # unknown; don't reject blindly
    return spread_pips <= max_spread_pips


def is_market_hours(dt: datetime | None = None, session: str = "all") -> bool:
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    # very simple: allow all by default
    return True


def check_volatility(atr_pips: float | None, min_atr: float, max_atr: float) -> bool:
    if atr_pips is None:
        return True
    if atr_pips < min_atr:
        return False
    if atr_pips > max_atr:
        return False
    return True
