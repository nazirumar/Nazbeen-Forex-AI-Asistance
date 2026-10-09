"""Screenshot-analysis service tests for real-LLM integration (Phase 11B).

Focus: deterministic findings stay authoritative over LLM claims, the vision
provider actually receives the screenshot bytes, and a failing configured
provider is surfaced loudly (never silently replaced by the mock).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from nazbeen_forex_ai.analysis import services as services_module
from nazbeen_forex_ai.analysis.llm import BaseLLMProvider, LLMError
from nazbeen_forex_ai.analysis.llm import LLMConfigurationError
from nazbeen_forex_ai.analysis.schemas import LLMChartAssessment, LLMReasoningOutput
from nazbeen_forex_ai.analysis.services import (
    ScreenshotAnalysisService,
    apply_deterministic_authority,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _flat_candles(n: int = 40, price: float = 1.1000) -> list[dict]:
    """No gaps, no structure: the deterministic scenario must stay WAIT."""
    return [
        {
            "time": datetime(2026, 1, 1, 0, i, tzinfo=timezone.utc).isoformat(),
            "open": price,
            "high": price + 0.0001,
            "low": price - 0.0001,
            "close": price,
            "volume": 10,
        }
        for i in range(n)
    ]


def _md(candles: list[dict] | None = None, source: str = "mock") -> dict:
    return {
        "symbol": "EURUSD",
        "timeframe": "M15",
        "candles": _flat_candles() if candles is None else candles,
        "source": source,
        "retrieved_at": "2026-01-01T00:00:00Z",
        "stale": False,
    }


class ScriptedVision(BaseLLMProvider):
    provider_name = "scripted"
    model = "scripted-vision-1"

    def __init__(self, assessment: Optional[LLMChartAssessment] = None, error: Exception | None = None):
        self.role = "vision"
        self.assessment = assessment
        self.error = error
        self.calls: list[dict] = []

    def inspect_chart(self, prompt, image_bytes=None, image_mime=None):
        self.calls.append({"prompt": prompt, "image_bytes": image_bytes, "image_mime": image_mime})
        if self.error is not None:
            raise self.error
        return self.assessment

    def reason(self, prompt):
        return LLMReasoningOutput()


class ScriptedReasoning(BaseLLMProvider):
    provider_name = "scripted"
    model = "scripted-reasoning-1"

    def __init__(self, output: Optional[LLMReasoningOutput] = None, error: Exception | None = None):
        self.role = "reasoning"
        self.output = output or LLMReasoningOutput()
        self.error = error
        self.prompts: list[str] = []

    def inspect_chart(self, prompt, image_bytes=None, image_mime=None):
        return LLMChartAssessment()

    def reason(self, prompt):
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return self.output


def _bullish_claim() -> LLMChartAssessment:
    return LLMChartAssessment(
        observed_symbol="EURUSD",
        observed_timeframe="M15",
        summary="Looks bullish with a visible imbalance.",
        direction="bullish",
        observations=["higher highs", "bullish FVG"],
        candidate_levels=[1.1234],
        uncertainty=["timestamp unknown"],
        missing_evidence=["volume panel not visible"],
        self_reported_confidence=0.55,
    )


def _patch_md(monkeypatch, md: dict | None = None):
    monkeypatch.setattr(
        ScreenshotAnalysisService,
        "retrieve_market_data",
        lambda self, symbol, timeframe, count=100: md if md is not None else _md(),
    )


def _patch_providers(monkeypatch, vision=None, reasoning=None):
    def factory(role):
        return vision if role == "vision" else reasoning

    monkeypatch.setattr(services_module, "get_llm_provider", factory)


def _png_upload() -> SimpleUploadedFile:
    from io import BytesIO

    buf = BytesIO()
    Image.new("RGB", (8, 8), "steelblue").save(buf, format="PNG")
    return SimpleUploadedFile("chart.png", buf.getvalue(), "image/png")


# ---------------------------------------------------------------------------
# Pure precedence logic
# ---------------------------------------------------------------------------

def test_authority_llm_cannot_upgrade_wait_to_buy():
    decision, notes = apply_deterministic_authority("WAIT", _bullish_claim(), True, True)
    assert decision == "WAIT"
    assert any("decision remains WAIT" in n for n in notes)


def test_authority_deterministic_buy_survives_bearish_llm():
    bearish = LLMChartAssessment(direction="bearish", summary="spike looks heavy")
    decision, notes = apply_deterministic_authority("BUY", bearish, True, True)
    assert decision == "BUY"
    assert any("authoritative" in n for n in notes)


def test_authority_no_synchronized_data_forces_wait():
    decision, notes = apply_deterministic_authority("BUY", None, False, False)
    assert decision == "WAIT"
    assert any("forced to WAIT" in n for n in notes)


def test_authority_agreeing_llm_changes_nothing():
    decision, notes = apply_deterministic_authority("BUY", _bullish_claim(), True, True)
    assert decision == "BUY"
    assert notes == []


# ---------------------------------------------------------------------------
# Service behavior
# ---------------------------------------------------------------------------

def test_vision_provider_receives_screenshot_bytes(monkeypatch):
    vision = ScriptedVision(assessment=_bullish_claim())
    reasoning = ScriptedReasoning(
        output=LLMReasoningOutput(explanation="Bias is neutral; nothing confirmed.")
    )
    _patch_md(monkeypatch)
    _patch_providers(monkeypatch, vision=vision, reasoning=reasoning)

    upload = _png_upload()
    result = ScreenshotAnalysisService().analyze(image_file=upload)

    assert len(vision.calls) == 1
    call = vision.calls[0]
    assert call["image_bytes"] == upload.read(), "vision provider did not receive the image"
    assert call["image_mime"] == "image/png"
    assert result.decision == "WAIT"  # deterministic scenario on flat data


def test_llm_levels_never_become_entry_levels(monkeypatch):
    """Candidate levels read by the vision model stay unverified observations."""
    vision = ScriptedVision(assessment=_bullish_claim())
    _patch_md(monkeypatch)
    _patch_providers(monkeypatch, vision=vision, reasoning=ScriptedReasoning())

    result = ScreenshotAnalysisService().analyze()
    assert result.decision == "WAIT"
    assert result.entry_levels == []
    assert result.sl is None and result.tp is None
    ai_levels = [e for e in result.evidence if e.type == "candidate_level"]
    assert ai_levels and ai_levels[0].price_level == pytest.approx(1.1234)
    assert ai_levels[0].source == "ai"
    assert "unverified" in ai_levels[0].description


def test_direction_disagreement_recorded_and_resolved_for_deterministic(monkeypatch):
    vision = ScriptedVision(assessment=_bullish_claim())
    _patch_md(monkeypatch)
    _patch_providers(monkeypatch, vision=vision, reasoning=ScriptedReasoning())

    result = ScreenshotAnalysisService().analyze()
    direction_conflicts = [d for d in result.disagreements if d.aspect == "direction"]
    assert direction_conflicts, "LLM/deterministic direction mismatch not recorded"
    assert direction_conflicts[0].resolved is True  # deterministic retained
    assert any("decision remains WAIT" in u for u in result.uncertainty)


def test_vision_failure_is_loud_and_never_mocked(monkeypatch):
    """A configured real provider that fails must surface an error, not mock."""
    vision = ScriptedVision(error=LLMError("vision provider unreachable"))
    reasoning = ScriptedReasoning(output=LLMReasoningOutput(explanation="grounded write-up"))
    _patch_md(monkeypatch)
    _patch_providers(monkeypatch, vision=vision, reasoning=reasoning)

    result = ScreenshotAnalysisService().analyze()
    assert any("vision provider failed" in e for e in result.errors)
    assert any("not inspected" in u for u in result.uncertainty)
    assert result.raw_ai_response["vision"] is None
    assert result.raw_ai_response["provider_failures"]
    # The failure is attributed to the real provider — never labeled as mock.
    assert result.model == "reasoning=scripted/scripted-reasoning-1"
    assert "mock" not in (result.model or "")
    assert result.decision == "WAIT"
    # The reasoning write-up still ran: one provider failing doesn't kill the other.
    assert "grounded write-up" in result.ai_explanation


def test_reasoning_failure_keeps_deterministic_analysis(monkeypatch):
    reasoning = ScriptedReasoning(error=LLMError("reasoning overloaded (HTTP 503)"))
    _patch_md(monkeypatch)
    _patch_providers(monkeypatch, vision=ScriptedVision(assessment=_bullish_claim()),
                     reasoning=reasoning)

    result = ScreenshotAnalysisService().analyze()
    assert any("reasoning provider failed" in e for e in result.errors)
    assert result.ai_explanation == ""
    assert result.decision == "WAIT"
    assert result.raw_ai_response["reasoning"] is None


def test_configuration_error_surfaces_as_loud_error(monkeypatch):
    """Misconfiguration (real mode, no keys) is an error, not a silent mock."""

    def factory(role):
        raise LLMConfigurationError(f"{role} LLM provider is not configured")

    _patch_md(monkeypatch)
    monkeypatch.setattr(services_module, "get_llm_provider", factory)

    result = ScreenshotAnalysisService().analyze()
    assert any("vision provider failed" in e for e in result.errors)
    assert any("reasoning provider failed" in e for e in result.errors)
    assert result.decision == "WAIT"
    assert result.model is None  # no provider actually ran


def test_prompt_contains_deterministic_findings(monkeypatch):
    vision = ScriptedVision(assessment=_bullish_claim())
    _patch_md(monkeypatch)
    _patch_providers(monkeypatch, vision=vision, reasoning=ScriptedReasoning())

    ScreenshotAnalysisService().analyze()
    prompt = vision.calls[0]["prompt"]
    assert "deterministic_findings" in prompt
    assert "scenario_decision" in prompt
    assert "Never fabricate exact price levels" in prompt


def test_reasoning_prompt_includes_vision_summary(monkeypatch):
    reasoning = ScriptedReasoning()
    _patch_md(monkeypatch)
    _patch_providers(monkeypatch, vision=ScriptedVision(assessment=_bullish_claim()),
                     reasoning=reasoning)

    ScreenshotAnalysisService().analyze()
    assert reasoning.prompts and "Looks bullish" in reasoning.prompts[0]


# ---------------------------------------------------------------------------
# End-to-end through the API (mock LLM via test settings)
# ---------------------------------------------------------------------------

@pytest.fixture
def api() -> APIClient:
    client = APIClient()
    get_user_model().objects.create_user("llm1", password="Llm1-2026!")
    client.force_authenticate(user=get_user_model().objects.get(username="llm1"))
    return client


@pytest.mark.django_db
def test_upload_with_scripted_real_providers_returns_deterministic_wait(api, monkeypatch):
    """Full request path: LLM claims BUY-ish, deterministic says WAIT → WAIT."""
    vision = ScriptedVision(assessment=_bullish_claim())
    reasoning = ScriptedReasoning(output=LLMReasoningOutput(explanation="Neutral read."))
    _patch_md(monkeypatch)
    _patch_providers(monkeypatch, vision=vision, reasoning=reasoning)

    resp = api.post(
        reverse("analysis:upload"), {"image": _png_upload()}, format="multipart"
    )
    assert resp.status_code == 201
    result = resp.json()["result"]
    assert result["decision"] == "WAIT"
    assert result["entry_levels"] == []
    assert result["sl"] is None and result["tp"] is None
    assert "scripted" in result["model"]


@pytest.mark.django_db
def test_upload_with_default_mock_providers_still_works(api):
    """Test-suite default: mock providers, no network, safe WAIT analysis."""
    resp = api.post(
        reverse("analysis:upload"), {"image": _png_upload()}, format="multipart"
    )
    assert resp.status_code == 201
    result = resp.json()["result"]
    assert result["decision"] == "WAIT"
    assert result["model"] == "vision=mock/mock, reasoning=mock/mock"
