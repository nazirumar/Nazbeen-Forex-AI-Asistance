"""Phase 11E: generic no-look-ahead and prefix-consistency suite.

Every event-emitting detector must satisfy, on *any* prefix of a deterministic
series:

1. **No look-ahead** — an event is never reported before its confirmation bar
   has closed (``confirmed_at`` ≤ the prefix's last bar; swings additionally
   prove ``index + right ≤ last``).
2. **Subset of the full read** — the events visible on a prefix are always a
   subset of the events on the full series (nothing is invented early).
3. **No repainting (monotone visibility)** — once an event is visible on some
   prefix it stays visible with an *identical* identity (type, direction,
   confirmation/formation time, level(s)) on every longer prefix: event keys
   only grow, never change or disappear.
4. **Monotone lifecycle** — FVG and order-block lifecycle states only advance
   (open → retested → mitigated/invalidated) and their retest/invalidation
   timestamps never change once reported.

Premium/discount is deliberately excluded from (2)/(3): it is a *rolling
window state* anchored to the last bar by design (each prefix legitimately
reports its own current state). It is instead checked to be exactly
self-anchored: one event, ``index == last``, ``confirmed_at == last bar``.

All series are synthetic test-only data (mock; never real market prices).
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Callable, Dict, List

from nazbeen_forex_ai.structure.analysis import swing_bias  # noqa: F401  (import check)
from nazbeen_forex_ai.structure.bos import detect_bos_choch_mss
from nazbeen_forex_ai.structure.displacement import detect_displacement
from nazbeen_forex_ai.structure.fvg import annotate_fvg_lifecycle, detect_fvg
from nazbeen_forex_ai.structure.liquidity import detect_liquidity, detect_sweeps
from nazbeen_forex_ai.structure.orderblocks import detect_orderblocks, validate_orderblocks
from nazbeen_forex_ai.structure.patterns import detect_engulfing, detect_rejection
from nazbeen_forex_ai.structure.swings import detect_swings
from nazbeen_forex_ai.structure.tests.candles import bars
from nazbeen_forex_ai.structure.types import StructureEvent
from nazbeen_forex_ai.structure.zones import (
    detect_premium_discount,
    detect_sr_flips,
    detect_support_resistance,
)

TOL = 0.0005
_RIGHT = 2  # swing_right used by the liquidity/S-R detectors here
_LIFECYCLE_RANK = {"unknown": -1, "open": 0, "retested": 1, "mitigated": 2, "invalidated": 3}


def _series() -> List[Dict]:
    """Golden bullish M15 plus a designed tail (see row comments).

    Tail adds: a hammer + a shooting star (rejections), a mid-series
    retest→mitigation→invalidation of the golden FVG (full lifecycle), a
    second SSL sweep on a red pin bar, a bullish displacement + order block,
    a fresh FVG that is later retested, and a bullish engulfing.
    """
    from nazbeen_forex_ai.structure.tests.golden import BULLISH_M15_ROWS

    tail = [
        (1.1042, 1.1046, 1.1038, 1.1044),  # 25
        (1.1044, 1.1045, 1.1034, 1.1043),  # 26 hammer → bullish rejection
        (1.1043, 1.1056, 1.1042, 1.1044),  # 27 shooting star → bearish rejection
        (1.1044, 1.1045, 1.1030, 1.1032),  # 28
        (1.1032, 1.1034, 1.1022, 1.1024),  # 29
        (1.1024, 1.1028, 1.1016, 1.1018),  # 30 close ≤ 1.1020 → FVG17 mitigated
        (1.1018, 1.1020, 1.1006, 1.1010),  # 31
        (1.1010, 1.1012, 1.0998, 1.1002),  # 32 close < 1.1012 → FVG17 invalidated
        (1.1002, 1.1004, 1.0992, 1.0996),  # 33 break-like, never a sweep (close back)
        (1.1005, 1.1006, 1.0990, 1.1002),  # 34 red pin → SSL sweep + OB candle
        (1.1002, 1.1030, 1.1000, 1.1028),  # 35 bullish displacement + engulfing
        (1.1028, 1.1036, 1.1026, 1.1034),  # 36 c3 → new bullish FVG
        (1.1034, 1.1036, 1.1022, 1.1028),  # 37 retest of the new FVG
        (1.1028, 1.1034, 1.1024, 1.1032),  # 38
        (1.1032, 1.1040, 1.1030, 1.1038),  # 39
    ]
    return bars(list(BULLISH_M15_ROWS) + tail)


def _iso(dt) -> str:
    return dt.isoformat().replace("+00:00", "Z") if dt else ""


def _key(ev: StructureEvent):
    """Stable identity: everything except mutable details/lifecycle."""
    return (
        ev.type,
        ev.direction,
        _iso(ev.confirmed_at),
        _iso(ev.formation_time),
        round(float(ev.level), 10) if ev.level is not None else None,
        tuple(round(float(x), 10) for x in (ev.levels or ())),
    )


def _run_swings(candles: List[Dict]) -> List[StructureEvent]:
    """Swings wrapped as events; knowable at ``index + right`` (not before)."""
    out: List[StructureEvent] = []
    for s in detect_swings(candles, left=_RIGHT, right=_RIGHT):
        knowable = candles[min(s.index + _RIGHT, len(candles) - 1)]["time"]
        out.append(
            StructureEvent(
                type=f"swing_{s.type}",
                direction=None,
                index=s.index,
                formation_time=s.time,
                confirmed_at=datetime.fromisoformat(knowable.replace("Z", "+00:00")),
                level=float(s.price),
            )
        )
    return out


def _run_sweeps(candles: List[Dict]) -> List[StructureEvent]:
    pools = detect_liquidity(candles, tolerance=TOL, swing_left=_RIGHT, swing_right=_RIGHT)
    return detect_sweeps(candles, liquidity=pools, tolerance=TOL)


def _run_fvg_lifecycle(candles: List[Dict]) -> List[StructureEvent]:
    return annotate_fvg_lifecycle(candles, detect_fvg(candles, threshold_pips=0.1))


def _run_ob_lifecycle(candles: List[Dict]) -> List[StructureEvent]:
    return validate_orderblocks(candles, detect_orderblocks(candles))


Detector = tuple  # (name, run(candles) -> list[StructureEvent], last_bar_anchored)

DETECTORS: List[Detector] = [
    ("swings", _run_swings, False),
    (
        "liquidity",
        lambda c: detect_liquidity(c, tolerance=TOL, swing_left=_RIGHT, swing_right=_RIGHT),
        False,
    ),
    ("sweeps", _run_sweeps, False),
    ("displacement", detect_displacement, False),
    ("bos_choch_mss", detect_bos_choch_mss, False),
    ("fvg", detect_fvg, False),
    ("fvg_lifecycle", _run_fvg_lifecycle, False),
    ("orderblocks", detect_orderblocks, False),
    ("ob_lifecycle", _run_ob_lifecycle, False),
    ("rejection", detect_rejection, False),
    ("engulfing", detect_engulfing, False),
    ("sr_levels", lambda c: detect_support_resistance(c, tolerance=TOL), False),
    ("sr_flips", lambda c: detect_sr_flips(c, tolerance=TOL), False),
    ("premium_discount", detect_premium_discount, True),  # rolling state by design
]


# --- property 1/2/3: no look-ahead, subset, monotone visibility ---------------


def test_every_detector_fires_on_the_series_non_vacuous():
    series = _series()
    for name, run, _anchored in DETECTORS:
        events = run(series)
        assert events, f"detector {name} produced no events — suite would be vacuous"


def test_prefix_properties_no_lookahead_no_subset_no_repaint():
    series = _series()
    for name, run, anchored in DETECTORS:
        full_keys = Counter(_key(e) for e in run(series))
        seen: Counter = Counter()
        for k in range(2, len(series)):
            prefix = series[: k + 1]
            last = datetime.fromisoformat(prefix[-1]["time"].replace("Z", "+00:00"))
            events = run(prefix)
            for e in events:
                # (1) never before the confirmation bar has closed
                assert e.confirmed_at is not None, name
                assert e.confirmed_at <= last, f"{name} reports before its bar"
                if e.formation_time is not None:
                    assert e.formation_time <= e.confirmed_at, name
            if anchored:
                # rolling window state: exactly the last bar, self-anchored
                assert len(events) <= 1, name
                for e in events:
                    assert e.index == k, name
                    assert e.confirmed_at == last, name
                continue
            keys = Counter(_key(e) for e in events)
            # (2) never invents events the full series does not have
            assert keys - full_keys == Counter(), f"{name} invents events at k={k}"
            # (3) events never change identity or disappear as bars arrive (only grow)
            assert seen - keys == Counter(), f"{name} repaints or disappears at k={k}"
            seen |= keys
        if not anchored:
            assert seen == full_keys, f"{name} final prefix must equal the full read"


def test_swings_only_reported_once_confirmed():
    series = _series()
    for k in range(2, len(series)):
        prefix = series[: k + 1]
        for e in _run_swings(prefix):
            assert e.index + _RIGHT <= k, f"swing at {e.index} confirmed too early"


# --- property 4: monotone lifecycle -------------------------------------------


def test_fvg_lifecycle_is_monotone_and_timestamps_sticky():
    _assert_lifecycle_monotone(_run_fvg_lifecycle, ("retest_time", "mitigated_time", "invalidated_time"))


def test_ob_lifecycle_is_monotone_and_timestamps_sticky():
    _assert_lifecycle_monotone(_run_ob_lifecycle, ("retest_time", "invalidated_time"))


def _assert_lifecycle_monotone(run: Callable, sticky_fields) -> None:
    series = _series()
    prev_state: Dict = {}
    prev_fields: Dict = {}
    for k in range(2, len(series)):
        for e in run(series[: k + 1]):
            key = _key(e)
            state = (e.details or {}).get("lifecycle", {}).get("state")
            assert state in _LIFECYCLE_RANK, f"unknown lifecycle state {state!r}"
            if key in prev_state:
                assert _LIFECYCLE_RANK[state] >= _LIFECYCLE_RANK[prev_state[key]], (
                    f"lifecycle regressed {prev_state[key]} -> {state} at k={k}"
                )
                for f in sticky_fields:
                    old = prev_fields.get(key, {}).get(f)
                    new = (e.details or {}).get("lifecycle", {}).get(f)
                    if old is not None:
                        assert new == old, f"lifecycle {f} changed at k={k}"
            prev_state[key] = state
            prev_fields[key] = dict((e.details or {}).get("lifecycle", {}))


def test_fvg_lifecycle_advances_through_the_whole_series():
    """The golden FVG must be observed open → retested → mitigated → invalidated."""
    series = _series()
    seen_states = set()
    for k in range(2, len(series)):
        for e in _run_fvg_lifecycle(series[: k + 1]):
            if e.direction == "bullish" and (e.levels or [None])[0] == 1.1012:
                seen_states.add((e.details or {}).get("lifecycle", {}).get("state"))
    assert {"retested", "mitigated", "invalidated"} <= seen_states


def test_detector_output_is_deterministic():
    series = _series()
    for name, run, _anchored in DETECTORS:
        first = run(series)
        second = run(series)
        assert [_key(e) for e in first] == [_key(e) for e in second], name
        assert [_iso(e.confirmed_at) for e in first] == [_iso(e.confirmed_at) for e in second]


def test_event_times_stay_on_the_candle_grid():
    """Every confirmation/formation time is a real candle time (no fabrication)."""
    series = _series()
    grid = {c["time"] for c in series}
    for name, run, _anchored in DETECTORS:
        for e in run(series):
            for ts in (e.confirmed_at, e.formation_time):
                if ts is None:
                    continue
                assert _iso(ts) in grid, f"{name} timestamp {_iso(ts)} is not a candle time"


def test_prefix_runs_cover_the_whole_series():
    """Sanity: the harness exercises a meaningful number of prefixes."""
    series = _series()
    assert len(series) == 40
    assert len(series[0]["time"]) == len(series[-1]["time"])  # uniform ISO shape
    assert timedelta(minutes=15) * (len(series) - 1) == (
        datetime.fromisoformat(series[-1]["time"].replace("Z", "+00:00"))
        - datetime.fromisoformat(series[0]["time"].replace("Z", "+00:00"))
    )
