"""Data freshness and market-session helpers (audit H-09, fix P1.8).

Pure, timezone-aware (UTC) functions — no provider or network access, so they
are unit-testable without an MT5 terminal. Used by the analysis service to
label stale data honestly and by the status endpoint to report the session
state. Nothing here fabricates freshness: an unknown last-bar time yields
``stale=None``-style transparency via ``last_bar_age_sec=None``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

# Nominal bar length per supported timeframe, in seconds.
TIMEFRAME_SECONDS: Dict[str, int] = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "H1": 3600,
    # Mock-provider "S" variants share the minute-based spacing.
    "M1S": 60,
    "M5S": 300,
    "M15S": 900,
}

# Forex market-closure window (UTC): Friday 21:00 → Sunday 21:00. This is a
# documented heuristic for the major sessions, not a broker calendar — it is
# surfaced as a *state label*, never used to fabricate prices.
FOREX_CLOSE_WEEKDAY = 4  # Friday
FOREX_CLOSE_HOUR_UTC = 21
FOREX_OPEN_WEEKDAY = 6  # Sunday
FOREX_OPEN_HOUR_UTC = 21


def _as_utc(dt: Union[datetime, str, None]) -> Optional[datetime]:
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def bar_age_seconds(
    last_bar_time: Union[datetime, str, None], now: Union[datetime, str, None] = None
) -> Optional[float]:
    """Age of the newest bar in seconds, or None when it cannot be determined."""
    bar = _as_utc(last_bar_time)
    current = _as_utc(now) or datetime.now(timezone.utc)
    if bar is None:
        return None
    return max(0.0, (current - bar).total_seconds())


def assess_staleness(
    last_bar_time: Union[datetime, str, None],
    timeframe: str,
    now: Union[datetime, str, None] = None,
    threshold_sec: int = 900,
) -> Dict[str, Any]:
    """Decide whether candle data is stale (audit H-09).

    A dataset is stale when the newest bar is older than the larger of the
    configured threshold and 1.5× the nominal bar length (grace for a
    still-forming bar). With no last-bar time the age is unknown: staleness is
    reported as ``False`` with ``last_bar_age_sec=None`` (absence of data is
    never dressed up as freshness — callers gate on data presence separately).
    """
    age = bar_age_seconds(last_bar_time, now)
    tf_sec = TIMEFRAME_SECONDS.get((timeframe or "").upper())
    effective = max(int(threshold_sec), int(1.5 * tf_sec) if tf_sec else int(threshold_sec))
    if age is None:
        return {"stale": False, "last_bar_age_sec": None, "threshold_sec": effective}
    return {"stale": age > effective, "last_bar_age_sec": age, "threshold_sec": effective}


def is_market_closed(now: Union[datetime, str, None] = None) -> bool:
    """Heuristic weekend-closure check for major FX sessions (UTC).

    Closed: Friday from 21:00 UTC through Sunday until 21:00 UTC.
    """
    current = _as_utc(now) or datetime.now(timezone.utc)
    wd, hour = current.weekday(), current.hour
    if wd == 5:  # Saturday
        return True
    if wd == FOREX_CLOSE_WEEKDAY and hour >= FOREX_CLOSE_HOUR_UTC:  # Friday evening
        return True
    if wd == FOREX_OPEN_WEEKDAY and hour < FOREX_OPEN_HOUR_UTC:  # Sunday day
        return True
    return False


def market_state(now: Union[datetime, str, None] = None) -> str:
    """Session state label: "open" or "closed" (heuristic, documented above)."""
    return "closed" if is_market_closed(now) else "open"
