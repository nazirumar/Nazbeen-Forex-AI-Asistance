"""Multi-timeframe conflict detection tests (Phase 11C, audit H-05).

`mtf_bias` must compute real HH/HL/LH/LL biases across H1/M15/M5/M1 and emit a
real conflicts list — never the old hardcoded ``[]`` stub.
"""

from __future__ import annotations

from nazbeen_forex_ai.structure.analysis import evaluate_scenario, mtf_bias


def _c(i: int, o: float, h: float, l: float, cl: float) -> dict:
    return {
        "time": f"2026-01-01T00:{i:02d}:00+00:00",
        "open": o,
        "high": h,
        "low": l,
        "close": cl,
        "volume": 10,
    }


# Textbook rising structure (same shape as the H-05 repro): BULLISH.
_RISING = [
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


def _mirror(candles: list[dict]) -> list[dict]:
    """Price-axis mirror: every bullish structure becomes a bearish one."""
    out = []
    for c in candles:
        out.append(
            {
                **c,
                "open": round(2.2070 - c["open"], 6),
                "close": round(2.2070 - c["close"], 6),
                "high": round(2.2070 - c["low"], 6),
                "low": round(2.2070 - c["high"], 6),
            }
        )
    return out


_FALLING = _mirror(_RISING)


def test_fixture_sanity_single_timeframe_biases() -> None:
    assert mtf_bias([], _RISING, [], [])["M15"] == "BULLISH"
    assert mtf_bias([], _FALLING, [], [])["M15"] == "BEARISH"


def test_conflict_reported_between_opposite_timeframes() -> None:
    bias = mtf_bias([], _RISING, _FALLING, [])
    assert bias["M15"] == "BULLISH"
    assert bias["M5"] == "BEARISH"
    assert "M15 BULLISH vs M5 BEARISH" in bias["conflicts"]


def test_no_conflicts_when_only_one_timeframe_decisive() -> None:
    bias = mtf_bias([], _RISING, [], [])
    assert bias["conflicts"] == []


def test_neutral_timeframes_never_conflict() -> None:
    bias = mtf_bias([], [], [], [])
    assert bias == {
        "H1": "NEUTRAL",
        "M15": "NEUTRAL",
        "M5": "NEUTRAL",
        "M1": "NEUTRAL",
        "conflicts": [],
    }


def test_conflicts_cover_every_disagreeing_pair() -> None:
    bias = mtf_bias(_RISING, _RISING, _FALLING, _RISING)
    assert len(bias["conflicts"]) == 3, bias["conflicts"]
    assert "H1 BULLISH vs M5 BEARISH" in bias["conflicts"]
    assert "M15 BULLISH vs M5 BEARISH" in bias["conflicts"]
    assert "M5 BEARISH vs M1 BULLISH" in bias["conflicts"]


def test_evaluate_scenario_propagates_real_conflicts() -> None:
    scen = evaluate_scenario(_RISING, _FALLING, [])
    assert scen["mtf_conflicts"], "scenario must surface real MTF conflicts"
    assert any("M5 BEARISH" in c for c in scen["mtf_conflicts"])


def test_evaluate_scenario_empty_inputs_have_no_conflicts() -> None:
    scen = evaluate_scenario([], [], [])
    assert scen["mtf_conflicts"] == []
    assert scen["decision"] == "WAIT"
