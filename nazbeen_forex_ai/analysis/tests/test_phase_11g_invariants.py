"""Phase 11G WS5: regression verification of MASTER_SPEC §3 (MTF ICT/SMC) and
§4 (end-to-end AI screenshot analysis).

These tests pin the cross-cutting invariants the phase must not regress:

§3  Multi-timeframe structure is read from confirmed swings only (never looking
    ahead of the last bar); real cross-timeframe conflicts are surfaced and an
    unfetchable timeframe is reported as unavailable, never as NEUTRAL.
§4  Screenshot/AI readings never override the deterministic engine, and a
    decision is only issued on synchronized (fresh, real) market data —
    disagreement or unsynchronized data means WAIT with an explanation.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from nazbeen_forex_ai.analysis.services import (
    ScreenshotAnalysisService,
    apply_deterministic_authority,
)
from nazbeen_forex_ai.structure.analysis import mtf_bias, mtf_structure_alignment
from nazbeen_forex_ai.structure.types import Candle


def _c(i: int, o: float, h: float, l: float, c: float) -> Candle:  # noqa: E741
    from datetime import datetime, timedelta, timezone

    t = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=15 * i)
    return Candle(time=t, open=o, high=h, low=l, close=c)


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

_FALLING = [
    _c(0, 1.1080, 1.1090, 1.1070, 1.1075),
    _c(1, 1.1075, 1.1080, 1.1060, 1.1065),
    _c(2, 1.1065, 1.1075, 1.1060, 1.1070),
    _c(3, 1.1070, 1.1080, 1.1065, 1.1075),
    _c(4, 1.1075, 1.1078, 1.1030, 1.1040),
    _c(5, 1.1040, 1.1045, 1.1010, 1.1015),
    _c(6, 1.1015, 1.1020, 1.0995, 1.1000),
    _c(7, 1.1000, 1.1015, 1.0995, 1.1010),
    _c(8, 1.1010, 1.1015, 1.0990, 1.0995),
    _c(9, 1.0995, 1.1000, 1.0960, 1.0965),
]


# --------------------------------------------------------------- §3 MTF reads
def test_mtf_read_is_deterministic_from_confirmed_swings() -> None:
    bias = mtf_bias(_RISING, _RISING, _RISING, _RISING)
    assert bias["H1"] == bias["M15"] == "BULLISH"
    assert bias["conflicts"] == []


def test_mtf_alignment_reports_real_conflict() -> None:
    alignment = mtf_structure_alignment({"H1": _RISING, "M15": _FALLING})
    assert alignment["aligned"] is False
    assert alignment["dominant"] is None
    assert alignment["conflicts"], "a genuine H1 vs M15 conflict must be reported"


def test_mtf_alignment_is_true_when_every_decisive_timeframe_agrees() -> None:
    alignment = mtf_structure_alignment({"H1": _RISING, "M15": _RISING})
    assert alignment["aligned"] is True
    assert alignment["dominant"] == "BULLISH"


def test_unavailable_timeframe_is_null_not_neutral() -> None:
    alignment = mtf_structure_alignment({"H1": _RISING})
    assert alignment["structure"]["M15"] is None
    assert set(alignment["unavailable"]) == {"M15", "M5", "M1"}
    # Only the available decisive timeframe counts; nothing is fabricated.
    assert alignment["aligned"] is True
    assert alignment["dominant"] == "BULLISH"


# ------------------------------------------- §4 deterministic authority / WAIT
def test_ai_bullish_reading_cannot_override_deterministic_wait() -> None:
    vision = SimpleNamespace(direction="bullish")
    decision, notes = apply_deterministic_authority("WAIT", vision, True, True)
    assert decision == "WAIT"
    assert any("remains WAIT" in note for note in notes)


def test_deterministic_buy_is_retained_when_ai_disagrees() -> None:
    vision = SimpleNamespace(direction="bearish")
    decision, notes = apply_deterministic_authority("BUY", vision, True, True)
    assert decision == "BUY"
    assert any("authoritative" in note for note in notes)


def test_unsynchronized_data_forces_wait_with_explanation() -> None:
    decision, notes = apply_deterministic_authority("BUY", None, False, True)
    assert decision == "WAIT"
    assert any("not synchronized" in note for note in notes)


def test_mock_data_is_never_synchronized() -> None:
    state: dict[str, Any] = {
        "md": {"source": "mock", "candles": [{"open": 1.0}], "stale": False},
        "identity_known": True,
        "uncertainty": [],
    }
    out = ScreenshotAnalysisService().node_validate_market_data(state)
    assert out["data_synchronized"] is False
    assert any("mock" in note.lower() for note in out["uncertainty"])


def test_stale_mt5_data_is_not_synchronized() -> None:
    state: dict[str, Any] = {
        "md": {
            "source": "mt5",
            "candles": [{"open": 1.0}],
            "stale": True,
            "last_bar_age_sec": 99999,
        },
        "identity_known": True,
        "uncertainty": [],
    }
    out = ScreenshotAnalysisService().node_validate_market_data(state)
    assert out["data_synchronized"] is False
    assert any("Stale market data" in note for note in out["uncertainty"])


def test_fresh_mt5_data_is_synchronized() -> None:
    state: dict[str, Any] = {
        "md": {"source": "mt5", "candles": [{"open": 1.0}], "stale": False},
        "identity_known": True,
        "uncertainty": [],
    }
    out = ScreenshotAnalysisService().node_validate_market_data(state)
    assert out["data_synchronized"] is True
