"""Phase 11E detector tests — one assertion group per documented rule.

Each test encodes the exact mathematical definition from the detector's module
docstring (MASTER_SPEC §3.C): bullish/bearish variants, formation/confirmation
timestamps on the candle grid, invalid-condition handling, and no look-ahead.
"""

from __future__ import annotations

from nazbeen_forex_ai.structure.analysis import mtf_structure_alignment, swing_bias
from nazbeen_forex_ai.structure.displacement import detect_displacement
from nazbeen_forex_ai.structure.fvg import annotate_fvg_lifecycle, detect_fvg
from nazbeen_forex_ai.structure.liquidity import detect_liquidity, detect_sweeps
from nazbeen_forex_ai.structure.orderblocks import detect_orderblocks, validate_orderblocks
from nazbeen_forex_ai.structure.patterns import detect_engulfing, detect_rejection
from nazbeen_forex_ai.structure.zones import (
    detect_premium_discount,
    detect_sr_flips,
    detect_support_resistance,
)

from nazbeen_forex_ai.structure.tests.candles import (
    bars,
    falling_bars,
    flat_bars,
    quiet_around,
    rising_bars,
    t,
    z,
)

# ---------------------------------------------------------------------------
# Displacement
# ---------------------------------------------------------------------------


def _with_displacement(up: bool = True):
    rows = quiet_around(1.1000, 14)
    if up:
        rows.append((1.1000, 1.1010, 1.0999, 1.1010))  # body 0.0010 > 1.5*ATR
    else:
        rows.append((1.1000, 1.1001, 1.0990, 1.0990))
    return bars(rows)


def test_displacement_bullish_and_bearish() -> None:
    up = detect_displacement(_with_displacement(True))
    assert [e.direction for e in up] == ["bullish"]
    assert up[0].type == "DISPLACEMENT"
    d = up[0].details
    assert d["body_atr_ratio"] >= 1.5 and d["body_range_ratio"] >= 0.6
    down = detect_displacement(_with_displacement(False))
    assert [e.direction for e in down] == ["bearish"]


def test_displacement_never_backdates_and_handles_invalid() -> None:
    ev = detect_displacement(_with_displacement(True))[0]
    assert ev.index == 14
    assert ev.confirmed_at == t(14) and ev.formation_time == t(14)
    # Too-small body: not displacement.
    rows = quiet_around(1.1000, 10) + [(1.1000, 1.1004, 1.0996, 1.1005)]
    assert detect_displacement(bars(rows)) == []
    # Flat market (zero range/ATR) → no events, no crash.
    assert detect_displacement(bars([(1.1, 1.1, 1.1, 1.1)] * 5)) == []
    assert detect_displacement([]) == []


# ---------------------------------------------------------------------------
# Rejection / engulfing
# ---------------------------------------------------------------------------


def test_rejection_rules_both_directions() -> None:
    rows = [
        (1.1000, 1.1003, 1.0990, 1.1002),  # long lower wick → bullish hammer
        (1.1002, 1.1012, 1.0999, 1.1000),  # long upper wick → bearish star
        (1.1000, 1.1004, 1.0996, 1.1003),  # balanced candle → nothing
        (1.1, 1.1, 1.1, 1.1),  # zero range → invalid, skipped
    ]
    ev = detect_rejection(bars(rows))
    assert [(e.direction, e.index) for e in ev] == [("bullish", 0), ("bearish", 1)]
    assert ev[0].details["pattern"] == "hammer"
    assert ev[1].details["pattern"] == "shooting_star"
    assert ev[0].confirmed_at == ev[0].formation_time == t(0)


def test_engulfing_rules_both_directions() -> None:
    rows = [
        (1.1010, 1.1011, 1.0999, 1.1000),  # red
        (1.0998, 1.1013, 1.0997, 1.1012),  # green engulfs → bullish
        (1.1012, 1.1013, 1.0997, 1.0998),  # red engulfs green → bearish
        (1.0999, 1.1000, 1.0998, 1.09995),  # tiny body < ratio → nothing
    ]
    ev = detect_engulfing(bars(rows))
    assert [(e.direction, e.index) for e in ev] == [("bullish", 1), ("bearish", 2)]
    assert ev[0].details["prev_body"] > 0
    assert ev[0].confirmed_at == t(1)
    assert detect_engulfing([]) == []


# ---------------------------------------------------------------------------
# Liquidity pools + sweeps
# ---------------------------------------------------------------------------


def _liquidity_fixture():
    """Two swing lows ~equal (SSL pool) + two swing highs ~equal (BSL)."""
    rows = [
        (1.1010, 1.1012, 1.1004, 1.1008),  # 0
        (1.1008, 1.1009, 1.1000, 1.1002),  # 1 low 1.1000
        (1.1002, 1.1010, 1.1001, 1.1009),  # 2
        (1.1009, 1.1022, 1.1008, 1.1020),  # 3 high 1.1022
        (1.1020, 1.1021, 1.1001, 1.1004),  # 4 low 1.1001 (≈1.1000 → SSL)
        (1.1004, 1.1014, 1.1003, 1.1012),  # 5
        (1.1012, 1.10225, 1.1010, 1.1021),  # 6 high 1.10225 (≈1.1022 → BSL)
        (1.1021, 1.1018, 1.1008, 1.1010),  # 7
        (1.1010, 1.1012, 1.1006, 1.1008),  # 8 quiet
    ]
    return bars(rows)


def test_liquidity_pools_and_equal_lows() -> None:
    liq = detect_liquidity(_liquidity_fixture(), tolerance=0.0005, swing_left=1, swing_right=1)
    kinds = {e.details["kind"] for e in liq}
    assert {"bsl", "ssl"} <= kinds
    # Legacy contract preserved:
    eq = [e for e in liq if e.details["kind"] == "equal_high"]
    assert eq and eq[0].level is not None
    ssl = next(e for e in liq if e.details["kind"] == "ssl")
    assert ssl.direction == "bullish"
    assert ssl.level == 1.1000  # first touch price (real candle low)
    assert ssl.formation_time == t(1) and ssl.confirmed_at == t(4)
    bsl = next(e for e in liq if e.details["kind"] == "bsl")
    assert bsl.direction == "bearish" and bsl.level == 1.1022
    assert bsl.confirmed_at == t(6)


def test_equal_low_is_detected_like_equal_high() -> None:
    # Two adjacent bars with equal lows only.
    rows = [
        (1.1000, 1.1008, 1.0990, 1.1006),
        (1.1006, 1.1010, 1.0990, 1.1008),  # same low 1.0990
        (1.1008, 1.1012, 1.1002, 1.1010),
    ]
    liq = detect_liquidity(bars(rows), tolerance=0.0001)
    lows = [e for e in liq if e.details["kind"] == "equal_low"]
    assert len(lows) == 1 and lows[0].direction == "bullish" and lows[0].level == 1.0990
    assert lows[0].confirmed_at == t(1)  # knowable at the second bar's close


def test_ssl_and_bsl_sweeps_with_close_back() -> None:
    fx = _liquidity_fixture()
    pool = detect_liquidity(fx, tolerance=0.0005, swing_left=1, swing_right=1)
    sweep_rows = fx + bars(
        [
            (1.1008, 1.1010, 1.0994, 1.1005),  # 9: wick below SSL, close back above
            (1.1005, 1.1030, 1.1004, 1.1028),  # 10
            (1.1028, 1.1040, 1.1027, 1.1020),  # 11: wick above BSL, close back below
        ],
        offset=len(fx),
    )
    sweeps = detect_sweeps(sweep_rows, liquidity=pool, tolerance=0.0005, max_bars=20)
    # Isolate the swing-pool sweeps under test (the fixture's incidental
    # equal-high pairs may fire their own sweeps — also correct per the rules).
    sweeps = [e for e in sweeps if e.details["pool_kind"] in ("ssl", "bsl")]
    assert [(e.direction, e.index) for e in sweeps] == [("bullish", 9), ("bearish", 11)]
    ssl_sweep = sweeps[0]
    assert ssl_sweep.type == "SWEEP" and ssl_sweep.details["kind"] == "ssl_sweep"
    assert ssl_sweep.details["swept_to"] == 1.0994
    assert ssl_sweep.confirmed_at == t(9) and ssl_sweep.formation_time == t(9)
    assert sweeps[1].details["kind"] == "bsl_sweep"


def test_close_beyond_level_is_a_break_not_a_sweep() -> None:
    fx = _liquidity_fixture()
    pool = detect_liquidity(fx, tolerance=0.0005, swing_left=1, swing_right=1)
    rows = fx + bars(
        [
            (1.1008, 1.1010, 1.0994, 1.0993),  # wick below SSL but CLOSE stays below
            (1.0993, 1.0996, 1.0990, 1.0995),
        ],
        offset=len(fx),
    )
    sweeps = detect_sweeps(rows, liquidity=pool, tolerance=0.0005)
    # The SSL pool's level was traded through but the close stayed beyond it:
    # that is a break, never a sweep.
    assert [e for e in sweeps if e.details["pool_kind"] in ("ssl", "bsl")] == []


def test_sweep_never_scans_before_pool_confirmation() -> None:
    # Bar 1 dips below the future SSL level with a close back above it — a
    # perfect sweep pattern — but the SSL pool (touches at bars 4 and 7) only
    # becomes valid at bar 7's close. A pool is never valid before its
    # confirmation, so that earlier pattern must not be reported.
    rows = bars(
        [
            (1.1010, 1.1012, 1.1004, 1.1008),  # 0
            (1.1008, 1.1010, 1.0990, 1.1006),  # 1 deep qualifying dip (too early)
            (1.1006, 1.1010, 1.1002, 1.1008),  # 2
            (1.1008, 1.1016, 1.1007, 1.1014),  # 3
            (1.1014, 1.1015, 1.1000, 1.1003),  # 4 SSL touch 1 (level 1.1000)
            (1.1003, 1.1012, 1.1002, 1.1010),  # 5
            (1.1010, 1.1018, 1.1009, 1.1016),  # 6
            (1.1016, 1.1017, 1.1001, 1.1004),  # 7 SSL touch 2 → pool confirmed
            (1.1004, 1.1014, 1.1003, 1.1012),  # 8
        ]
    )
    pool = detect_liquidity(rows, tolerance=0.0008, swing_left=1, swing_right=1)
    ssl = next(e for e in pool if e.details["kind"] == "ssl")
    assert ssl.level == 1.1000
    assert ssl.details["confirmed_index"] == 7
    # Bar 1 satisfies the sweep math but precedes confirmation → no event.
    sweeps = detect_sweeps(rows, liquidity=pool, tolerance=0.0008, max_bars=20)
    assert sweeps == [], [(e.index, e.details) for e in sweeps]


# ---------------------------------------------------------------------------
# FVG lifecycle
# ---------------------------------------------------------------------------


def _fvg_bullish_tail(rows_tail):
    rows = [
        (1.1000, 1.1008, 1.0998, 1.1006),  # 0 (c1: high 1.1008)
        (1.1006, 1.1030, 1.1005, 1.1028),  # 1 (c2 impulse)
        (1.1028, 1.1032, 1.1015, 1.1030),  # 2 (c3: low 1.1015) → gap [1.1008, 1.1015]
    ]
    return bars(rows + rows_tail)


def test_fvg_lifecycle_states() -> None:
    # Still open: nothing after confirmation trades into the gap.
    tail = [(1.1030, 1.1034, 1.1016, 1.1032)]
    life = annotate_fvg_lifecycle(_fvg_bullish_tail(tail), detect_fvg(_fvg_bullish_tail(tail)))
    assert life[0].details["lifecycle"]["state"] == "open"
    assert life[0].details["confirmed_index"] == 2

    # Retested: wick into the gap, close stays above it.
    tail = [(1.1030, 1.1033, 1.1010, 1.1017)]
    life = annotate_fvg_lifecycle(_fvg_bullish_tail(tail), detect_fvg(_fvg_bullish_tail(tail)))
    lc = life[0].details["lifecycle"]
    assert lc["state"] == "retested" and lc["retest_index"] == 3
    assert lc["retest_time"] == z(t(3))

    # Mitigated: close inside the gap, never below its bottom.
    tail = [(1.1030, 1.1033, 1.1009, 1.1010)]
    life = annotate_fvg_lifecycle(_fvg_bullish_tail(tail), detect_fvg(_fvg_bullish_tail(tail)))
    assert life[0].details["lifecycle"]["state"] == "mitigated"

    # Invalidated: close fully below the gap's bottom.
    tail = [(1.1030, 1.1033, 1.1004, 1.1005)]
    life = annotate_fvg_lifecycle(_fvg_bullish_tail(tail), detect_fvg(_fvg_bullish_tail(tail)))
    lc = life[0].details["lifecycle"]
    assert lc["state"] == "invalidated" and lc["invalidated_index"] == 3


def test_fvg_lifecycle_bearish_mirror() -> None:
    rows = [
        (1.1030, 1.1032, 1.1022, 1.1024),  # 0 (c1 low 1.1022)
        (1.1024, 1.1025, 1.1000, 1.1002),  # 1 (impulse down)
        (1.0998, 1.1015, 1.0996, 1.1000),  # 2 (c3 high 1.1015) → gap [1.1015, 1.1022]
        (1.1000, 1.1021, 1.0998, 1.1018),  # 3 retrace into gap, close inside
    ]
    fvgs = detect_fvg(bars(rows))
    assert fvgs and fvgs[0].direction == "bearish"
    life = annotate_fvg_lifecycle(bars(rows), fvgs)
    lc = life[0].details["lifecycle"]
    assert lc["state"] == "mitigated" and lc["retest_index"] == 3


# ---------------------------------------------------------------------------
# Order block validation
# ---------------------------------------------------------------------------


def _ob_tail(tail):
    # bar0: small bearish candle (the OB zone [1.0998, 1.1001]);
    # bar1: bullish displacement (body 0.0015 >= 1.5 * ATR 0.00095) → OB confirmed.
    rows = [
        (1.1000, 1.1001, 1.0998, 1.0999),
        (1.0999, 1.1015, 1.0999, 1.1014),
    ]
    return bars(rows) + bars(tail, offset=len(rows))


def test_orderblock_lifecycle() -> None:
    # Open: no later bar trades back into the zone.
    tail = [(1.1014, 1.1017, 1.1011, 1.1015)]
    obs = validate_orderblocks(_ob_tail(tail), detect_orderblocks(_ob_tail(tail)))
    assert obs and obs[0].details["lifecycle"]["state"] == "open"

    # Retested: price returns into the OB zone.
    tail = [(1.1014, 1.1017, 1.0997, 1.1013)]
    obs = validate_orderblocks(_ob_tail(tail), detect_orderblocks(_ob_tail(tail)))
    lc = obs[0].details["lifecycle"]
    assert lc["state"] == "retested" and lc["touches"] == 1 and lc["retest_index"] == 2

    # Invalidated: close below the OB low (1.0998).
    tail = [(1.1014, 1.1017, 1.0995, 1.0996)]
    obs = validate_orderblocks(_ob_tail(tail), detect_orderblocks(_ob_tail(tail)))
    assert obs[0].details["lifecycle"]["state"] == "invalidated"


# ---------------------------------------------------------------------------
# Premium/discount, S/R, flips
# ---------------------------------------------------------------------------


def test_premium_discount_zone() -> None:
    rows = quiet_around(1.1050, 9, rng=0.0100)  # range [1.1000, 1.1100]
    rows.append((1.1070, 1.1075, 1.1065, 1.1072))  # close above midpoint 1.1050
    ev = detect_premium_discount(bars(rows))
    assert len(ev) == 1 and ev[0].details["zone"] == "premium"
    assert ev[0].direction == "bearish"
    assert ev[0].level == 1.1050 and ev[0].details["midpoint"] == 1.1050
    assert ev[0].confirmed_at == t(9)

    rows2 = rows[:-1] + [(1.1030, 1.1035, 1.1025, 1.1028)]  # below midpoint
    ev = detect_premium_discount(bars(rows2))
    assert ev[0].details["zone"] == "discount" and ev[0].direction == "bullish"

    # Degenerate (no range) → invalid condition, never a fabricated midpoint.
    assert detect_premium_discount(bars([(1.1, 1.1, 1.1, 1.1)] * 5)) == []
    assert detect_premium_discount([]) == []


def test_support_resistance_levels_fixed_at_confirmation() -> None:
    rows = [
        (1.1030, 1.1032, 1.1020, 1.1022),  # 0
        (1.1022, 1.1050, 1.1021, 1.1048),  # 1 peak 1.1050
        (1.1048, 1.1049, 1.1030, 1.1032),  # 2
        (1.1032, 1.1052, 1.1031, 1.1050),  # 3 peak 1.1052 (≈ first → cluster)
        (1.1046, 1.1049, 1.1032, 1.1034),  # 4
        (1.1034, 1.1051, 1.1033, 1.1049),  # 5 peak 1.1051 (3rd touch)
        (1.1049, 1.1050, 1.1031, 1.1033),  # 6
    ]
    levels = detect_support_resistance(
        bars(rows), tolerance=0.0005, min_touches=2, swing_left=1, swing_right=1
    )
    res = [e for e in levels if e.details["kind"] == "resistance"]
    assert res, levels
    lvl = res[0]
    assert lvl.details["touches"] == 3
    # Level fixed by the FIRST min_touches touches — later touches don't move it.
    assert abs(lvl.level - (1.1050 + 1.1052) / 2) < 1e-9
    assert lvl.formation_time == t(1) and lvl.confirmed_at == t(3)
    assert lvl.direction == "bearish"


def test_sr_flip_resistance_to_support_requires_hold() -> None:
    rows = [
        (1.1020, 1.1022, 1.1010, 1.1012),  # 0
        (1.1012, 1.1050, 1.1011, 1.1048),  # 1 peak 1.1050
        (1.1048, 1.1049, 1.1020, 1.1022),  # 2
        (1.1022, 1.1051, 1.1021, 1.1049),  # 3 peak 1.1051 → resistance confirmed
        (1.1049, 1.1050, 1.1048, 1.1050),  # 4
        (1.1050, 1.1062, 1.1049, 1.1060),  # 5 CLOSE above level → break
        (1.1060, 1.1061, 1.10505, 1.1059),  # 6 retest: low back at level, close above
    ]
    flips = detect_sr_flips(
        bars(rows), tolerance=0.0005, min_touches=2, swing_left=1, swing_right=1
    )
    assert len(flips) == 1
    f = flips[0]
    assert f.type == "SR_FLIP" and f.direction == "bullish"
    assert f.details["kind"] == "resistance_to_support"
    assert f.formation_time == t(5) and f.confirmed_at == t(6)


def test_break_without_hold_is_not_a_flip() -> None:
    rows = [
        (1.1020, 1.1022, 1.1010, 1.1012),
        (1.1012, 1.1050, 1.1011, 1.1048),
        (1.1048, 1.1049, 1.1020, 1.1022),
        (1.1022, 1.1051, 1.1021, 1.1049),
        (1.1049, 1.1050, 1.1048, 1.1050),
        (1.1050, 1.1062, 1.1049, 1.1060),  # break
        (1.1060, 1.1075, 1.1058, 1.1070),  # runs away — never retests the level
        (1.1070, 1.1072, 1.1060, 1.1065),
    ]
    assert (
        detect_sr_flips(bars(rows), tolerance=0.0005, min_touches=2, swing_left=1, swing_right=1)
        == []
    )


# ---------------------------------------------------------------------------
# Multi-timeframe alignment
# ---------------------------------------------------------------------------


def test_mtf_structure_alignment_states() -> None:
    bull = rising_bars(11)
    bear = falling_bars(11)
    assert swing_bias(bull) == "BULLISH"
    assert swing_bias(bear) == "BEARISH"
    assert swing_bias(flat_bars(12)) == "NEUTRAL"

    aligned = mtf_structure_alignment({"H1": bull, "M15": bull, "M5": bull, "M1": bull})
    assert aligned["aligned"] is True and aligned["dominant"] == "BULLISH"
    assert aligned["conflicts"] == [] and aligned["unavailable"] == []

    conflicted = mtf_structure_alignment({"H1": bull, "M15": bull, "M5": bear, "M1": []})
    assert conflicted["aligned"] is False and conflicted["dominant"] is None
    assert "H1 BULLISH vs M5 BEARISH" in conflicted["conflicts"]
    assert conflicted["unavailable"] == ["M1"]
    assert conflicted["structure"]["M1"] is None, "unavailable is None, never NEUTRAL"

    no_evidence = mtf_structure_alignment({})
    assert no_evidence["aligned"] is None and no_evidence["dominant"] is None
