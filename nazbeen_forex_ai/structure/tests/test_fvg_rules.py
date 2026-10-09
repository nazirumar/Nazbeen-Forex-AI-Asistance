"""FVG detection rules (Phase 11A workstream 11A.2).

Covers gap-up, gap-down, no-gap, invalid (sub-threshold) gap and overlapping
candle-range cases, plus formation/confirmation timestamp sanity.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from nazbeen_forex_ai.structure.fvg import detect_fvg


def _c(i: int, o: float, h: float, l: float, cl: float) -> dict:
    return {
        "time": datetime(2026, 1, 1, 0, i, tzinfo=timezone.utc).isoformat(),
        "open": o,
        "high": h,
        "low": l,
        "close": cl,
        "volume": 10,
    }


def _gap_up() -> list[dict]:
    return [
        _c(0, 1.1001, 1.1002, 1.0999, 1.1001),
        _c(1, 1.1001, 1.1010, 1.1000, 1.1009),
        _c(2, 1.1008, 1.1012, 1.1006, 1.1011),
    ]


def _gap_down() -> list[dict]:
    return [
        _c(0, 1.1002, 1.1010, 1.1000, 1.1002),
        _c(1, 1.1001, 1.1002, 1.0996, 1.0997),
        _c(2, 1.0997, 1.0990, 1.0985, 1.0986),
    ]


def test_fvg_gap_up_detected_bullish() -> None:
    events = detect_fvg(_gap_up())
    assert len(events) == 1
    e = events[0]
    assert e.type == "FVG"
    assert e.direction == "bullish"
    assert e.levels == [1.1002, 1.1006]  # [c0.high, c2.low]
    assert e.details["gap"] == pytest.approx(0.0004)


def test_fvg_gap_down_detected_bearish() -> None:
    events = detect_fvg(_gap_down())
    assert len(events) == 1
    e = events[0]
    assert e.type == "FVG"
    assert e.direction == "bearish"
    assert e.levels == [1.099, 1.1]  # [c2.high, c0.low]


def test_fvg_no_gap_yields_nothing() -> None:
    flat = [
        _c(0, 1.1000, 1.1005, 1.0995, 1.1000),
        _c(1, 1.1000, 1.1006, 1.0994, 1.1003),
        _c(2, 1.1003, 1.1007, 1.0996, 1.1001),
    ]
    assert detect_fvg(flat) == []


def test_fvg_invalid_gap_below_threshold_rejected() -> None:
    """A sub-threshold sliver (default threshold_pips=0.5) must not be a gap."""
    tiny = [
        _c(0, 1.09995, 1.10000, 1.09990, 1.09995),
        _c(1, 1.09995, 1.10010, 1.09994, 1.10005),
        _c(2, 1.10003, 1.10010, 1.10002, 1.10008),
    ]
    # c0.high = 1.10000 < c2.low = 1.10003 → gap of 0.00003 < 0.00005 min.
    assert detect_fvg(tiny) == []
    # ...but the same sliver passes when the threshold is lowered explicitly.
    assert len(detect_fvg(tiny, threshold_pips=0.1)) == 1


def test_fvg_overlapping_candle_ranges_still_detected() -> None:
    """c0's full range extends below c2's range, but the gap zone still exists.

    Overlap between the candles' ranges must not suppress a valid gap, and the
    bearish condition must not fire on a bullish setup.
    """
    overlap = [
        _c(0, 1.0995, 1.1002, 1.0990, 1.0996),   # low 1.0990 far below c2
        _c(1, 1.0996, 1.1005, 1.0995, 1.1004),
        _c(2, 1.1004, 1.1010, 1.1006, 1.1009),   # c2.low 1.1006 > c0.high 1.1002
    ]
    events = detect_fvg(overlap)
    assert len(events) == 1
    assert events[0].direction == "bullish"
    assert events[0].levels == [1.1002, 1.1006]


def test_fvg_mutually_overlapping_no_gap() -> None:
    """When c0.high >= c2.low and c0.low <= c2.high there is no imbalance at all."""
    merged = [
        _c(0, 1.1000, 1.1008, 1.0998, 1.1002),
        _c(1, 1.1002, 1.1010, 1.0999, 1.1006),
        _c(2, 1.1006, 1.1012, 1.1004, 1.1010),
    ]
    assert detect_fvg(merged) == []


def test_fvg_timestamps_and_confirmation_not_backdated() -> None:
    for fixture in (_gap_up(), _gap_down()):
        e = detect_fvg(fixture)[0]
        assert e.start_time <= e.end_time
        # Pattern is only knowable once c3 (index 2) has closed.
        assert e.formation_time == e.end_time
        assert e.confirmed_at == e.end_time
        assert e.confirmed_at > e.start_time  # never backdated to c1
