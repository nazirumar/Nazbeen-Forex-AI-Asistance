"""Tests for the `llm_smoke` management command (Phase 11B).

Documents and enforces the smoke-test contract: with mock mode active the
command refuses unless ``--allow-mock`` is passed, and a real-provider run is
labeled as such. No network access — providers are scripted.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from PIL import Image

from nazbeen_forex_ai.analysis import llm as llm_module
from nazbeen_forex_ai.analysis.llm import BaseLLMProvider, LLMError
from nazbeen_forex_ai.analysis.schemas import LLMChartAssessment, LLMReasoningOutput


class FakeReasoning(BaseLLMProvider):
    provider_name = "openai"
    model = "gpt-4o-mini"

    def __init__(self):
        self.role = "reasoning"

    def inspect_chart(self, prompt, image_bytes=None, image_mime=None):
        return LLMChartAssessment()

    def reason(self, prompt):
        return LLMReasoningOutput(
            explanation="Verify AI findings against deterministic market data.",
            key_risks=["over-trusting the model"],
        )


class FakeVision(BaseLLMProvider):
    provider_name = "gemini"
    model = "gemini-1.5-flash"

    def __init__(self, seen: dict):
        self.role = "vision"
        self.seen = seen

    def inspect_chart(self, prompt, image_bytes=None, image_mime=None):
        self.seen["bytes"] = image_bytes
        self.seen["mime"] = image_mime
        return LLMChartAssessment(summary="A chart.", direction="neutral")

    def reason(self, prompt):
        return LLMReasoningOutput()


class BrokenProvider(FakeReasoning):
    def reason(self, prompt):
        raise LLMError("provider unavailable (HTTP 503)")


def _png_path(tmp_path):
    path = tmp_path / "chart.png"
    Image.new("RGB", (4, 4), "red").save(path, format="PNG")
    return str(path)


def test_smoke_refuses_mock_mode_without_allow_mock():
    with pytest.raises(CommandError, match="USE_MOCK_LLM"):
        call_command("llm_smoke", "--role", "reasoning")


def test_smoke_allow_mock_runs_and_is_labeled_mock(capsys):
    call_command("llm_smoke", "--role", "reasoning", "--allow-mock")
    out = capsys.readouterr().out
    assert "MOCK — NOT A REAL PROVIDER TEST" in out
    assert "provider=mock" in out


@override_settings(USE_MOCK_LLM=False, REASONING_LLM_PROVIDER="openai",
                   REASONING_LLM_API_KEY="sk-x", REASONING_LLM_MODEL="gpt-4o-mini")
def test_smoke_real_label_with_scripted_provider(monkeypatch, capsys):
    monkeypatch.setattr(llm_module, "get_llm_provider", lambda role: FakeReasoning())
    call_command("llm_smoke", "--role", "reasoning")
    out = capsys.readouterr().out
    assert "REAL PROVIDER" in out
    assert "provider=openai" in out and "model=gpt-4o-mini" in out
    assert "Verify AI findings" in out


@override_settings(USE_MOCK_LLM=False, VISION_LLM_PROVIDER="gemini",
                   VISION_LLM_API_KEY="AIza-x", VISION_LLM_MODEL="gemini-1.5-flash")
def test_smoke_vision_forwards_image(monkeypatch, tmp_path, capsys):
    seen: dict = {}
    monkeypatch.setattr(llm_module, "get_llm_provider", lambda role: FakeVision(seen))
    image = _png_path(tmp_path)
    call_command("llm_smoke", "--role", "vision", "--image", image)
    assert seen["bytes"] and seen["mime"] == "image/png"
    assert "A chart." in capsys.readouterr().out


def test_smoke_vision_requires_image():
    with pytest.raises(CommandError, match="--image"):
        call_command("llm_smoke", "--role", "vision", "--allow-mock")


def test_smoke_missing_image_file_errors(tmp_path):
    with pytest.raises(CommandError, match="not found"):
        call_command(
            "llm_smoke", "--role", "vision", "--allow-mock",
            "--image", str(tmp_path / "nope.png"),
        )


@override_settings(USE_MOCK_LLM=False, REASONING_LLM_PROVIDER="openai",
                   REASONING_LLM_API_KEY="sk-x", REASONING_LLM_MODEL="gpt-4o-mini")
def test_smoke_provider_failure_exits_nonzero_with_safe_message(monkeypatch):
    monkeypatch.setattr(llm_module, "get_llm_provider", lambda role: BrokenProvider())
    with pytest.raises(CommandError, match="provider call failed"):
        call_command("llm_smoke", "--role", "reasoning")


@override_settings(USE_MOCK_LLM=False, REASONING_LLM_PROVIDER="", REASONING_LLM_API_KEY="",
                   REASONING_LLM_MODEL="")
def test_smoke_misconfiguration_is_an_error_not_a_mock():
    with pytest.raises(CommandError, match="configuration failed"):
        call_command("llm_smoke", "--role", "reasoning")
