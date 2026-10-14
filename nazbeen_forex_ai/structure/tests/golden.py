"""Golden candle fixtures for the Phase 11E primary trading model.

All fixtures are **synthetic test-only data** (mock; never real market data)
built on the fixed UTC grid from :mod:`nazbeen_forex_ai.structure.tests.candles`.

``golden_bullish_m15`` is the reference ICT/SMC sequence. Its 25 bars were laid
out so every detector rule fires exactly where the chronological model needs
it (each claim below was verified against the detector math, not guessed):

- bars 0-5  — quiet base then rally; swing low @3 = **1.1000** (SSL touch 1).
- bar 6     — swing high @6 = **1.1032** (BSL touch 1), bullish displacement.
- bar 9     — swing low @9 = **1.1001** (SSL touch 2 → SSL pool level 1.1000
              confirmed at bar 9, inside the 0.0005 tolerance).
- bar 12    — swing high @12 = **1.1033** (BSL touch 2 → BSL pool 1.1032
              confirmed at bar 12; also a higher high ⇒ bias point).
- bar 14    — close 1.0998 breaks below the confirmed swing low 1.1001 with
              the trend still neutral → bearish **BOS**, trend turns bearish
              (the precondition that makes the later break an MSS).
- bar 15    — **SSL sweep**: low 1.0994 < 1.1000 − 0.0005 and close 1.1007 >
              1.1000 (wick through + close back = sweep; never a break).
- bar 16    — bullish **displacement** (body 0.0028 ≥ 1.5 × ATR ≈ 0.00216) and
              close 1.1035 > swing high 1.1033 against a bearish trend →
              bullish **MSS** (index 16 for both events).
- bar 17    — c3 confirms the bullish **FVG** [1.1012, 1.1020]
              (15.high 1.1012 < 17.low 1.1020).
- bar 18    — **retest**: low 1.1014 trades back into the gap, close 1.1022
              stays above the far edge → lifecycle "retested", never
              invalidated (the tail never closes below 1.1012).
- bars 19-24 — gentle continuation; swing_bias over the full series is
              BULLISH (5 bullish points vs 1 bearish) and is **already
              BULLISH as of the sweep bar** (2 vs 0) so the bias gate passes
              chronologically — the bias precedes the sweep.

Chain: sweep(15) → displacement(16) → MSS(16) → FVG(17) → retest(18) → M1
pattern after 04:30 → complete inside the 96-bar window.

Companions (same grid conventions): M1 starts at 04:00 (index 240 on the
1-minute grid) with red/green zigzag bars — every green bar is a bullish
engulfing, and the swing structure is strictly rising → M1 bias BULLISH with
fresh patterns after the 04:30 retest. M5/H1 are rising zigzags (BULLISH).

``golden_bearish_*`` = exact price mirror (p' = 2.2000 − p, high/low swapped),
so every bullish finding holds with directions flipped.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from nazbeen_forex_ai.structure.tests.candles import bars

Row = Tuple[float, float, float, float]  # (open, high, low, close)

# --- reference bullish M15 sequence (see module docstring) ------------------

BULLISH_M15_ROWS: List[Row] = [
    (1.1006, 1.1008, 1.1005, 1.1005),  # 0  descent begins
    (1.1005, 1.1006, 1.1002, 1.1003),  # 1
    (1.1003, 1.1004, 1.1001, 1.1002),  # 2
    (1.1002, 1.1004, 1.1000, 1.1003),  # 3  SSL touch 1 (level 1.1000)
    (1.1003, 1.1006, 1.1002, 1.1005),  # 4
    (1.1005, 1.1012, 1.1004, 1.1011),  # 5
    (1.1011, 1.1032, 1.1010, 1.1030),  # 6  BSL touch 1 (1.1032), displacement
    (1.1030, 1.1032, 1.1024, 1.1026),  # 7
    (1.1026, 1.1028, 1.1014, 1.1016),  # 8
    (1.1016, 1.1018, 1.1001, 1.1004),  # 9  SSL touch 2 → pool confirmed
    (1.1004, 1.1010, 1.1003, 1.1008),  # 10
    (1.1008, 1.1022, 1.1007, 1.1020),  # 11
    (1.1020, 1.1033, 1.1019, 1.1030),  # 12 BSL touch 2 → pool confirmed
    (1.1030, 1.1032, 1.1012, 1.1018),  # 13 (low kept clear of bar 12's low so
    #                                    no incidental equal-low pool forms)
    (1.1018, 1.1020, 1.0996, 1.0998),  # 14 close < 1.1001 → bearish BOS
    (1.0998, 1.1012, 1.0994, 1.1007),  # 15 SSL sweep (wick + close back)
    (1.1007, 1.1036, 1.1005, 1.1035),  # 16 bullish displacement + MSS
    (1.1035, 1.1038, 1.1020, 1.1034),  # 17 c3 → FVG [1.1012, 1.1020]
    (1.1034, 1.1036, 1.1014, 1.1022),  # 18 retest of the FVG
    (1.1022, 1.1030, 1.1020, 1.1028),  # 19
    (1.1028, 1.1040, 1.1026, 1.1038),  # 20
    (1.1038, 1.1048, 1.1036, 1.1046),  # 21
    (1.1046, 1.1050, 1.1042, 1.1044),  # 22
    (1.1044, 1.1046, 1.1038, 1.1040),  # 23
    (1.1040, 1.1044, 1.1036, 1.1042),  # 24
]


def _mirror(rows: List[Row]) -> List[Row]:
    """Price mirror around 1.1000 (high/low swap): bullish ⇄ bearish."""
    return [(2.2 - o, 2.2 - lo, 2.2 - hi, 2.2 - c) for (o, hi, lo, c) in rows]


def _rising_rows(n: int, base: float, step: float) -> List[Row]:
    """Row form of ``candles.rising_bars`` (alternating trough/peak zigzag)."""
    rows: List[Row] = []
    for i in range(n):
        if i % 2 == 0:
            low = base + (i // 2) * step
            rows.append((low + 0.0001, low + 0.0002, low, low + 0.0001))
        else:
            high = base + 1.5 * step + (i // 2) * step
            rows.append((high - 0.0001, high, high - 0.0002, high - 0.0001))
    return rows


def _m1_rows(n_pairs: int = 60, base: float = 1.1000, step: float = 0.0002) -> List[Row]:
    """Red/green zigzag with strictly rising levels.

    Every green bar is a bullish engulfing of the red bar before it
    (open ≤ prev close, close ≥ prev open, body ≥ prev body), and the swing
    highs/lows both rise ⇒ ``swing_bias`` is BULLISH.
    """
    rows: List[Row] = []
    price = base
    for _ in range(n_pairs):
        lo = price
        rows.append((lo + 0.0004, lo + 0.0005, lo, lo + 0.0001))  # red
        rows.append((lo, lo + 0.0007, lo - 0.0001, lo + 0.0006))  # green engulfing
        price += step
    # Final bar closes the grid at 06:00 (red, harmless for the read above).
    rows.append((price + 0.0004, price + 0.0005, price, price + 0.0001))
    return rows


# --- golden fixtures ---------------------------------------------------------


def golden_bullish_m15() -> List[Dict]:
    """Reference bullish M15 series (25 bars, 00:00 → 06:00 UTC)."""
    return bars(BULLISH_M15_ROWS)


def golden_bearish_m15() -> List[Dict]:
    """Exact mirror of the bullish series → bearish setup of the same shape."""
    return bars(_mirror(BULLISH_M15_ROWS))


def golden_bullish_m1() -> List[Dict]:
    """M1 companion: 04:00 → 06:00 UTC, rising, fresh engulfings ≥ 04:30."""
    return bars(_m1_rows(), step_minutes=1, offset=240)


def golden_bearish_m1() -> List[Dict]:
    return bars(_mirror(_m1_rows()), step_minutes=1, offset=240)


def golden_bullish_m5() -> List[Dict]:
    """M5 companion: 00:00 → 06:00 UTC rising zigzag (BULLISH bias)."""
    return bars(_rising_rows(73, 1.1000, 0.0010), step_minutes=5)


def golden_bearish_m5() -> List[Dict]:
    return bars(_mirror(_rising_rows(73, 1.1000, 0.0010)), step_minutes=5)


def golden_bullish_h1() -> List[Dict]:
    """H1 companion: 00:00 → 06:00 UTC rising zigzag (BULLISH bias)."""
    return bars(_rising_rows(7, 1.1000, 0.0005), step_minutes=60)


def golden_bearish_h1() -> List[Dict]:
    return bars(_mirror(_rising_rows(7, 1.1000, 0.0005)), step_minutes=60)


def golden_ranging_m15() -> List[Dict]:
    """Sideways M15: NEUTRAL bias, no sweeps, no chains → WAIT."""
    return bars(_flat_rows(24))


def golden_ranging_m1() -> List[Dict]:
    return bars(_flat_rows(60), step_minutes=1, offset=240)


def golden_ranging_m5() -> List[Dict]:
    return bars(_flat_rows(73), step_minutes=5)


def golden_ranging_h1() -> List[Dict]:
    return bars(_flat_rows(7), step_minutes=60)


def _flat_rows(n: int, price: float = 1.1000, rng: float = 0.0004) -> List[Row]:
    """Row form of ``candles.flat_bars`` (same geometry)."""
    rows: List[Row] = []
    for i in range(n):
        wobble = (rng / 2) if i % 2 == 0 else -(rng / 2)
        o = price
        c = price + wobble
        h = max(o, c) + rng / 4
        low = min(o, c) - rng / 4
        rows.append((o, h, low, c))
    return rows


# --- invalid variants (all derived from the bullish reference) ---------------


def golden_invalid_no_sweep() -> List[Dict]:
    """Bar 15 closes *beyond* the SSL level → a break, never a sweep.

    Every other step (displacement, MSS, FVG, retest) still exists, but with
    no sweep the chain can never start: WAIT.
    """
    rows = list(BULLISH_M15_ROWS)
    rows[15] = (1.0998, 1.1012, 1.0994, 1.0993)  # close below the pool level
    return bars(rows)


def golden_invalid_chronology() -> List[Dict]:
    """The only sweep happens at bar 24 — *after* displacement/MSS/FVG/retest.

    Earlier signals exist but sit before the sweep, so they can never combine
    into a setup (chronology is mandatory): WAIT.
    """
    rows = list(BULLISH_M15_ROWS)
    rows[15] = (1.0998, 1.1012, 1.0994, 1.0993)  # kill the early sweep
    rows[24] = (1.1040, 1.1044, 1.1036, 1.1043)  # late bullish equal-low sweep
    return bars(rows)


def golden_invalid_fvg() -> List[Dict]:
    """A post-retest bar closes below every bullish FVG → invalidated.

    The retest happened, but its gap is dead: the FVG step is *invalid* → WAIT.
    """
    rows = list(BULLISH_M15_ROWS)
    rows.append((1.1042, 1.1046, 1.1000, 1.0990))  # close < 1.1012 → gap dead
    return bars(rows)


def golden_invalid_stale() -> List[Dict]:
    """Chain ends 106 M15 bars before the last bar (> 96) → stale → WAIT."""
    return golden_bullish_m15() + bars(_flat_rows(100, price=1.1040), offset=25)
