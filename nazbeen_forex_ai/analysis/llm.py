"""LLM provider abstraction (mock-first)."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional
from django.conf import settings
from nazbeen_forex_ai.config import env_bool, env_str

USE_MOCK_LLM = env_bool("USE_MOCK_LLM", True)


class LLMError(Exception):
    pass


class BaseLLMProvider:
    def generate_analysis(self, prompt: str, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError


class MockLLMProvider(BaseLLMProvider):
    def generate_analysis(self, prompt: str, **kwargs) -> Dict[str, Any]:
        return {
            "symbol": None,
            "timeframe": None,
            "summary": "Mock analysis: chart uploaded. Insufficient synchronized data to extract exact levels; awaiting MT5 data.",
            "decision": "WAIT",
            "direction": "neutral",
            "entry_levels": [],
            "sl": None,
            "tp": None,
            "risk_reward": None,
            "evidence": [],
            "disagreements": [],
            "mtf_conflicts": [],
            "uncertainty": ["No synchronized price levels extracted from image"],
            "analysis_timestamp": "",
            "uses_mtf_data": False,
            "data_synchronized": False,
            "deterministic_signals": {},
            "ai_explanation": "Mock LLM: cannot fabricate exact price levels.",
            "raw_ai_response": {"mock": True},
            "model": "mock",
            "errors": [],
        }


class OpenAIProvider(BaseLLMProvider):
    def generate_analysis(self, prompt: str, **kwargs) -> Dict[str, Any]:
        raise LLMError("OpenAI provider not configured (stub)")


def get_llm_provider() -> BaseLLMProvider:
    if USE_MOCK_LLM:
        return MockLLMProvider()
    return MockLLMProvider()  # safe default
