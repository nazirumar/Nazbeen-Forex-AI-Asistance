"""Market structure detection rules (Phase 11A workstream 11A.3).

Fixtures: valid bullish structure, valid bearish structure, counter-trend
CHOCH, displacement MSS, invalid (no) break, and order blocks. Also verifies
formation-time vs confirmation-time (no look-ahead).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from nazbeen_forex_ai.structure.bos import detect_bos_choch_mss
from nazbeen_forex_ai.structure.orderblocks import detect_orderblocks


def _c(i: int, o: float, h: float, l: float, cl: float) -> dict:
    return {
        "time": datetime(2026, 1, 1, 0, i, tzinfo=timezone.utc).isoformat(),
        "open": o,
        "high": h,
        "low": l,
        "close": cl,
        "volume": 10,
    }


def _bullish_break() -> list[dict]:
    """Swing high 1.1050 at bar 1, close 1.1060 at bar 4 → bullish break."""
    return [
        _c(0, 1.1010, 1.1020, 1.1005, 1.1015),
        _c(1, 1.1015, 1.1050, 1.1010, 1.1045),
        _c(2, 1.1045, 1.1048, 1.1030, 1.1035),
        _c(3, 1.1035, 1.1040, 1.1025, 1.1030),
        _c(4, 1.1030, 1.1062, 1.1028, 1.1060),
        _c(5, 1.1060, 1.1065, 1.1055, 1.1062),
        _c(6, 1.1062, 1.1070, 1.1058, 1.1066),
    ]


def _bearish_break() -> list[dict]:
    """Swing low 1.0970 at bar 1, close 1.0965 at bar 4 → bearish break."""
    return [
        _c(0, 1.1000, 1.1010, 1.0995, 1.1005),
        _c(1, 1.1005, 1.1010, 1.0970, 1.0975),
        _c(2, 1.0975, 1.0985, 1.0972, 1.0980),
        _c(3, 1.0980, 1.0995, 1.0978, 1.0990),
        _c(4, 1.0990, 1.0992, 1.0965, 1.0965),
        _c(5, 1.0965, 1.0970, 1.0960, 1.0968),
        _c(6, 1.0968, 1.0975, 1.0964, 1.0972),
    ]


def _invalid_break() -> list[dict]:
    """Swing high 1.1050 exists, but closes never exceed it → no events."""
    return [
        _c(0, 1.1010, 1.1020, 1.1005, 1.1015),
        _c(1, 1.1015, 1.1050, 1.1010, 1.1045),
        _c(2, 1.1045, 1.1048, 1.1030, 1.1035),
        _c(3, 1.1035, 1.1042, 1.1028, 1.1038),
        _c(4, 1.1038, 1.1044, 1.1030, 1.1035),
        _c(5, 1.1035, 1.1046, 1.1032, 1.1042),
        _c(6, 1.1042, 1.1047, 1.1038, 1.1044),
    ]


def _trend_then_choch() -> list[dict]:
    """BOS bullish at bar 4, then a counter-trend break at bar 9 → CHOCH."""
    return [
        _c(0, 1.1000, 1.1010, 1.0995, 1.1008),
        _c(1, 1.1008, 1.1040, 1.1005, 1.1035),   # swing high 1.1040
        _c(2, 1.1035, 1.1038, 1.1025, 1.1030),
        _c(3, 1.1030, 1.1036, 1.1020, 1.1032),
        _c(4, 1.1032, 1.1050, 1.1030, 1.1046),   # close > 1.1040 → BOS bullish
        _c(5, 1.1046, 1.1055, 1.1040, 1.1052),
        _c(6, 1.1052, 1.1060, 1.1048, 1.1056),   # swing high 1.1060
        _c(7, 1.1056, 1.1058, 1.1035, 1.1038),   # swing low 1.1035
        _c(8, 1.1038, 1.1042, 1.1036, 1.1040),
        _c(9, 1.1040, 1.1045, 1.1028, 1.1030),   # close < 1.1035 → counter break
    ]


def _choch_with_displacement() -> list[dict]:
    """BOS bullish at bar 3, then a large-body counter break at bar 7 → MSS."""
    return [
        _c(0, 1.1000, 1.1004, 1.0998, 1.1002),
        _c(1, 1.1002, 1.1012, 1.1000, 1.1010),   # swing high 1.1012
        _c(2, 1.1010, 1.1011, 1.1005, 1.1007),
        _c(3, 1.1007, 1.1018, 1.1006, 1.1016),   # close > 1.1012 → BOS bullish
        _c(4, 1.1016, 1.1020, 1.1012, 1.1018),   # swing high 1.1020
        _c(5, 1.1018, 1.1019, 1.1011, 1.1013),   # swing low 1.1011
        _c(6, 1.1013, 1.1016, 1.1012, 1.1015),
        _c(7, 1.1015, 1.1016, 1.1000, 1.1001),   # body 0.0014 ≫ ATR → displacement
    ]


def test_bos_bullish_break_detected() -> None:
    events = detect_bos_choch_mss(_bullish_break())
    assert len(events) == 1
    e = events[0]
    assert e.type == "BOS"
    assert e.direction == "bullish"
    assert e.level == pytest.approx(1.1050)
    assert e.index == 4  # break confirmed at bar 4, not backdated


def test_bos_bearish_break_detected() -> None:
    events = detect_bos_choch_mss(_bearish_break())
    assert len(events) == 1
    e = events[0]
    assert e.type == "BOS"
    assert e.direction == "bearish"
    assert e.level == pytest.approx(1.0970)
    assert e.index == 4


def test_choch_counter_trend_after_bullish_bos() -> None:
    events = detect_bos_choch_mss(_trend_then_choch())
    types = [e.type for e in events]
    assert types == ["BOS", "CHOCH"], f"expected [BOS, CHOCH], got {types}"
    bos, choch = events
    assert bos.direction == "bullish"
    assert choch.direction == "bearish"
    assert choch.details["trend_before"] == "bullish"
    assert choch.details["trend_after"] == "bearish"
    assert choch.details["displacement"] is False


def test_mss_is_choch_with_displacement() -> None:
    events = detect_bos_choch_mss(_choch_with_displacement())
    types = [e.type for e in events]
    assert types == ["BOS", "MSS"], f"expected [BOS, MSS], got {types}"
    mss = events[1]
    assert mss.direction == "bearish"
    assert mss.details["displacement"] is True
    assert mss.details["trend_before"] == "bullish"


def test_invalid_break_produces_no_events() -> None:
    assert detect_bos_choch_mss(_invalid_break()) == []


def test_wick_only_poke_is_not_a_break() -> None:
    """Breaks are close-confirmed: a wick above the level is not a BOS."""
    candles = _invalid_break()
    # Bar 4's wick pokes above the swing high (1.1050) but closes back below;
    # every later close also stays below the level.
    candles[4] = _c(4, 1.1038, 1.1058, 1.1030, 1.1035)
    assert max(c["high"] for c in candles) > 1.1050          # wick did poke above
    assert detect_bos_choch_mss(candles) == []               # but no close break


def test_no_lookahead_formation_vs_confirmation_time() -> None:
    events = detect_bos_choch_mss(_trend_then_choch())
    assert events
    for e in events:
        assert e.confirmed_at is not None
        assert e.formation_time is not None
        # Formation (the broken swing) precedes confirmation (the breaking bar).
        assert e.formation_time <= e.confirmed_at
        # Confirmation is the breaking bar itself, never a future time.
        assert e.confirmed_at == datetime(2026, 1, 1, 0, e.index, tzinfo=timezone.utc)


# --------------------------------------------------------------------------
# Order blocks
# --------------------------------------------------------------------------

def test_bullish_orderblock_before_displacement() -> None:
    candles = [
        _c(0, 1.10000, 1.10010, 1.09990, 1.09995),   # bearish candle
        _c(1, 1.09995, 1.10010, 1.09990, 1.10005),
        _c(2, 1.10005, 1.10010, 1.09995, 1.10000),   # bearish candle → OB zone
        _c(3, 1.10000, 1.10120, 1.09995, 1.10110),   # bullish displacement
    ]
    events = detect_orderblocks(candles)
    assert len(events) == 1
    e = events[0]
    assert e.type == "ORDERBLOCK"
    assert e.direction == "bullish"
    assert e.index == 2
    assert e.levels == pytest.approx([1.09995, 1.10010])  # OB candle [low, high]
    assert e.formation_time < e.confirmed_at              # confirmed at displacement bar


def test_bearish_orderblock_before_displacement() -> None:
    candles = [
        _c(0, 1.10000, 1.10010, 1.09990, 1.10005),   # bullish candle
        _c(1, 1.10005, 1.10010, 1.09995, 1.10000),
        _c(2, 1.10000, 1.10010, 1.09998, 1.10004),   # bullish candle → OB zone
        _c(3, 1.10004, 1.10010, 1.09890, 1.09900),   # bearish displacement
    ]
    events = detect_orderblocks(candles)
    assert len(events) == 1
    e = events[0]
    assert e.direction == "bearish"
    assert e.index == 2
    assert e.levels == pytest.approx([1.09998, 1.10010])


def test_no_orderblock_without_displacement() -> None:
    flat = [_c(i, 1.1000, 1.1001, 1.0999, 1.10005) for i in range(6)]
    assert detect_orderblocks(flat) == []
