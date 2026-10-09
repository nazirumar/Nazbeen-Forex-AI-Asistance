"""Migrated audit regression tests — structure subsystem (Phase 11A).

Source: docs/audits/repro/test_audit_regressions.py (R index entries for
order blocks, FVG labels/timestamps, BOS, mtf bias). These failed against the
Phase 10 code and must pass against the Phase 11A fixes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from nazbeen_forex_ai.structure.analysis import mtf_bias
from nazbeen_forex_ai.structure.bos import detect_bos_choch_mss
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


def test_bug_orderblocks_module_imports() -> None:
    """CRIT-03: `from __future__ import __annotations__` is a SyntaxError.

    Actual before fix: SyntaxError: future feature __annotations__ is not defined.
    """
    import nazbeen_forex_ai.structure.orderblocks  # noqa: F401


def test_bug_fvg_gap_up_is_labelled_bullish() -> None:
    """CRIT-02: textbook bullish FVG (c0.high < c2.low) was labelled 'bearish'.

    Actual before fix: [('bearish', [1.1002, 1.1006])].
    """
    gap_up = [
        _c(0, 1.1001, 1.1002, 1.0999, 1.1001),
        _c(1, 1.1001, 1.1010, 1.1000, 1.1009),
        _c(2, 1.1008, 1.1012, 1.1006, 1.1011),
    ]
    events = detect_fvg(gap_up)
    assert len(events) == 1
    assert events[0].direction == "bullish", f"expected bullish, got {events[0].direction}"
    assert events[0].levels == [1.1002, 1.1006]


def test_bug_fvg_gap_down_is_labelled_bearish() -> None:
    """CRIT-02: textbook bearish FVG (c0.low > c2.high) was labelled 'bullish'.

    Actual before fix: [('bullish', [1.099, 1.099])] branch inverted.
    """
    gap_down = [
        _c(0, 1.1002, 1.1010, 1.1000, 1.1002),
        _c(1, 1.1001, 1.1002, 1.0996, 1.0997),
        _c(2, 1.0997, 1.0990, 1.0985, 1.0986),
    ]
    events = detect_fvg(gap_down)
    assert len(events) == 1
    assert events[0].direction == "bearish", f"expected bearish, got {events[0].direction}"


def test_bug_fvg_start_time_not_after_end_time() -> None:
    """M-09: one branch emitted start_time 2 bars AFTER end_time.

    Actual before fix: start_time = T2, end_time = T0 for the gap-down fixture.
    """
    gap_down = [
        _c(0, 1.1002, 1.1010, 1.1000, 1.1002),
        _c(1, 1.1001, 1.1002, 1.0996, 1.0997),
        _c(2, 1.0997, 1.0990, 1.0985, 1.0986),
    ]
    events = detect_fvg(gap_down)
    assert events, "gap-down fixture must produce an event"
    for e in events:
        assert e.start_time <= e.end_time, f"start {e.start_time} > end {e.end_time}"


def test_bug_bos_detects_close_above_swing_high() -> None:
    """CRIT-03: detect_bos_choch_mss was a stub that always returned [].

    Fixture: confirmed swing high 1.1050 followed by a close at 1.1060 (clear break).
    Actual before fix: [] — spec items BOS/CHOCH/MSS produced no output anywhere.
    """
    candles = [
        _c(0, 1.1010, 1.1020, 1.1005, 1.1015),
        _c(1, 1.1015, 1.1050, 1.1010, 1.1045),   # swing high 1.1050
        _c(2, 1.1045, 1.1048, 1.1030, 1.1035),
        _c(3, 1.1035, 1.1040, 1.1025, 1.1030),
        _c(4, 1.1030, 1.1062, 1.1028, 1.1060),   # close 1.1060 > swing high 1.1050
        _c(5, 1.1060, 1.1065, 1.1055, 1.1062),
        _c(6, 1.1062, 1.1070, 1.1058, 1.1066),
    ]
    events = detect_bos_choch_mss(candles)
    assert len(events) >= 1, "expected at least one BOS/CHOCH event, got []"


def test_bug_mtf_bias_bullish_on_rising_structure() -> None:
    """H-05: mtf_bias returned the TYPE of the last swing, not structure.

    Fixture: rising highs + rising lows (textbook uptrend).
    Actual before fix: 'BEARISH' because the last confirmed swing was a high.
    """
    candles = [
        _c(0, 1.1000, 1.1010, 1.0990, 1.1005),
        _c(1, 1.1005, 1.1020, 1.1000, 1.1015),
        _c(2, 1.1015, 1.1005, 1.0985, 1.0990),
        _c(3, 1.0990, 1.0995, 1.0975, 1.0980),
        _c(4, 1.0980, 1.1030, 1.0990, 1.1025),
        _c(5, 1.1025, 1.1060, 1.1020, 1.1055),
        _c(6, 1.1055, 1.1075, 1.1040, 1.1070),
        _c(7, 1.1070, 1.1055, 1.1030, 1.1035),
        _c(8, 1.1035, 1.1045, 1.1025, 1.1040),
        _c(9, 1.1040, 1.1085, 1.1060, 1.1080),
    ]
    bias = mtf_bias([], candles, [], [])
    assert bias["M15"] == "BULLISH", f"expected BULLISH on rising structure, got {bias['M15']}"
