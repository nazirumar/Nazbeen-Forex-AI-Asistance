"""Fabrication-guard tests (Phase 11C — audit H-04, fixes P1.2/P1.8 surface).

Contract:
- Missing symbol/timeframe → symbol/timeframe ``None``, decision WAIT, no
  market-data fetch. Never fabricated EURUSD/M15 defaults.
- Mock data is never "synchronized": it cannot authorize a BUY/SELL decision
  or any price level.
- Stale data is never synchronized either, and the reason is labeled.
- Real MTF conflicts (H1/M15/M5/M1) reach the output.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from nazbeen_forex_ai.analysis import services as services_module
from nazbeen_forex_ai.analysis.llm import BaseLLMProvider
from nazbeen_forex_ai.analysis.schemas import LLMChartAssessment, LLMReasoningOutput
from nazbeen_forex_ai.analysis.services import ScreenshotAnalysisService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _c(i: int, o: float, h: float, l: float, cl: float) -> dict:
    return {
        "time": datetime(2026, 1, 1, 0, i, tzinfo=timezone.utc).isoformat(),
        "open": o,
        "high": h,
        "low": l,
        "close": cl,
        "volume": 10,
    }


def _flat_candles(n: int = 40) -> list[dict]:
    return [_c(i, 1.1000, 1.1001, 1.0999, 1.1000) for i in range(n)]


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
    {**c, "open": round(2.2070 - c["open"], 6), "close": round(2.2070 - c["close"], 6),
     "high": round(2.2070 - c["low"], 6), "low": round(2.2070 - c["high"], 6)}
    for c in _RISING
]


def _md(
    candles: list[dict] | None = None,
    source: str = "mock",
    timeframe: str = "M15",
    stale: bool = False,
    last_bar_age_sec: float | None = 0.0,
) -> dict:
    return {
        "symbol": "EURUSD",
        "timeframe": timeframe,
        "candles": _flat_candles() if candles is None else candles,
        "source": source,
        "retrieved_at": "2026-01-01T00:00:00Z",
        "stale": stale,
        "last_bar_age_sec": last_bar_age_sec,
        "market_state": "open",
    }


class ScriptedVision(BaseLLMProvider):
    provider_name = "scripted"
    model = "scripted-vision-1"

    def __init__(self, assessment: Optional[LLMChartAssessment] = None):
        self.role = "vision"
        self.assessment = assessment or LLMChartAssessment()
        self.calls: list[dict] = []

    def inspect_chart(self, prompt, image_bytes=None, image_mime=None):
        self.calls.append({"prompt": prompt})
        return self.assessment

    def reason(self, prompt):
        return LLMReasoningOutput()


def _patch_providers(monkeypatch):
    def factory(role):
        return ScriptedVision()

    monkeypatch.setattr(services_module, "get_llm_provider", factory)


def _patch_md(monkeypatch, md_by_timeframe: dict[str, dict], calls: list | None = None):
    def fake(self, symbol, timeframe, count=100):
        if calls is not None:
            calls.append(timeframe.upper())
        return md_by_timeframe.get(timeframe.upper(), _md())

    monkeypatch.setattr(ScreenshotAnalysisService, "retrieve_market_data", fake)


HINTS = {"symbol": "EURUSD", "timeframe": "M15"}


# ---------------------------------------------------------------------------
# H-04: never fabricate the chart identity
# ---------------------------------------------------------------------------

def test_missing_identity_yields_null_symbol_timeframe_and_wait(monkeypatch):
    calls: list = []
    _patch_md(monkeypatch, {}, calls=calls)
    _patch_providers(monkeypatch)

    result = ScreenshotAnalysisService().analyze(user_hints={})

    assert calls == [], "no market data may be fetched without symbol/timeframe"
    assert result.symbol is None
    assert result.timeframe is None
    assert result.decision == "WAIT"
    assert result.data_synchronized is False
    assert result.source == "unknown"
    assert result.entry_levels == [] and result.sl is None and result.tp is None
    assert result.uses_mtf_data is False
    assert any("identity unknown" in u for u in result.uncertainty)


def test_blank_hints_are_treated_as_missing(monkeypatch):
    _patch_md(monkeypatch, {})
    _patch_providers(monkeypatch)
    result = ScreenshotAnalysisService().analyze(
        user_hints={"symbol": "   ", "timeframe": ""}
    )
    assert result.symbol is None and result.timeframe is None
    assert result.decision == "WAIT"


# ---------------------------------------------------------------------------
# H-04: mock data can never synchronize / authorize
# ---------------------------------------------------------------------------

def test_mock_data_is_never_synchronized(monkeypatch):
    _patch_md(monkeypatch, {"M15": _md(source="mock")})
    _patch_providers(monkeypatch)

    result = ScreenshotAnalysisService().analyze(user_hints=dict(HINTS))

    assert result.source == "mock"
    assert result.data_synchronized is False, "mock must never count as synchronized"
    assert result.decision == "WAIT"
    assert any("mock" in u and "decision forced to WAIT" in u for u in result.uncertainty)


def test_llm_price_level_with_mock_data_is_rejected(monkeypatch):
    """H-04 required regression: LLM-emitted level + mock data → rejected."""
    vision = ScriptedVision(
        assessment=LLMChartAssessment(direction="bullish", candidate_levels=[1.1234])
    )
    monkeypatch.setattr(services_module, "get_llm_provider", lambda role: vision)
    _patch_md(monkeypatch, {"M15": _md(source="mock")})

    result = ScreenshotAnalysisService().analyze(user_hints=dict(HINTS))

    assert result.data_synchronized is False
    assert result.decision == "WAIT"
    assert result.entry_levels == []
    assert result.sl is None and result.tp is None
    levels = [e for e in result.evidence if e.type == "candidate_level"]
    assert levels and levels[0].source == "ai", "the level stays an AI observation"


def test_fresh_mt5_data_is_synchronized(monkeypatch):
    _patch_md(monkeypatch, {"M15": _md(source="mt5", stale=False)})
    _patch_providers(monkeypatch)

    result = ScreenshotAnalysisService().analyze(user_hints=dict(HINTS))

    assert result.source == "mt5"
    assert result.data_synchronized is True
    assert not any("decision forced to WAIT" in u for u in result.uncertainty)


def test_stale_mt5_data_blocks_synchronization(monkeypatch):
    _patch_md(
        monkeypatch,
        {"M15": _md(source="mt5", stale=True, last_bar_age_sec=86400.0)},
    )
    _patch_providers(monkeypatch)

    result = ScreenshotAnalysisService().analyze(user_hints=dict(HINTS))

    assert result.data_synchronized is False, "stale data is not current evidence"
    assert result.decision == "WAIT"
    assert any("Stale market data" in u for u in result.uncertainty)


# ---------------------------------------------------------------------------
# H-05: real multi-timeframe conflicts reach the output
# ---------------------------------------------------------------------------

def test_mtf_conflicts_surface_in_analysis_output(monkeypatch):
    md_by_tf = {
        "M15": _md(candles=_RISING, source="mt5", timeframe="M15"),
        "H1": _md(candles=_RISING, source="mt5", timeframe="H1"),
        "M5": _md(candles=_FALLING, source="mt5", timeframe="M5"),
        "M1": _md(candles=_flat_candles(), source="mt5", timeframe="M1"),
    }
    _patch_md(monkeypatch, md_by_tf)
    _patch_providers(monkeypatch)

    result = ScreenshotAnalysisService().analyze(user_hints=dict(HINTS))

    assert result.mtf_conflicts, "MTF conflicts must be computed, not stubbed"
    assert any("M15 BULLISH vs M5 BEARISH" in c for c in result.mtf_conflicts)
    assert result.deterministic_signals["bias_mtf"]["H1"] == "BULLISH"
    assert result.deterministic_signals["bias_mtf"]["M5"] == "BEARISH"
    assert result.uses_mtf_data is True
    conflict_evidence = [e for e in result.evidence if e.type == "mtf_conflict"]
    assert conflict_evidence and conflict_evidence[0].source == "deterministic"


def test_single_timeframe_data_reports_no_conflicts(monkeypatch):
    md_by_tf = {
        "M15": _md(candles=_RISING, source="mt5", timeframe="M15"),
        "H1": _md(candles=[], source="mt5", timeframe="H1"),
        "M5": _md(candles=[], source="mt5", timeframe="M5"),
        "M1": _md(candles=[], source="mt5", timeframe="M1"),
    }
    _patch_md(monkeypatch, md_by_tf)
    _patch_providers(monkeypatch)

    result = ScreenshotAnalysisService().analyze(user_hints=dict(HINTS))
    assert result.mtf_conflicts == []
    assert result.uses_mtf_data is False
