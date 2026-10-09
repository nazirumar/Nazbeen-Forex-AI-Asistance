"""LLM provider abstraction, mock provider and configuration factory (Phase 11B).

Contract: a provider exposes two typed operations that return **validated
Pydantic claims** — never decisions:

- ``inspect_chart(prompt, image_bytes, image_mime)`` (vision role) returns an
  :class:`LLMChartAssessment` of what the model observed in the screenshot.
- ``reason(prompt)`` (reasoning role) returns an :class:`LLMReasoningOutput`
  grounded in deterministic findings supplied in the prompt.

Decisions (BUY/SELL/WAIT) are produced by the deterministic engine and the
risk service — the LLM explains findings, it does not decide (MASTER_SPEC
§3.D/§3.E; audit H-05).

Factory rules (audit H-03/CRIT-05-adjacent, MASTER_SPEC §4):
- ``USE_MOCK_LLM=true`` → the labeled mock provider (development + test suite).
- Otherwise the configured real provider (``openai`` / ``gemini``) is built from
  ``<ROLE>_LLM_PROVIDER/_API_KEY/_MODEL``. Misconfiguration raises
  :class:`LLMConfigurationError`; a real provider that fails at runtime raises
  :class:`LLMError` — **there is no silent fallback to the mock provider**.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from django.conf import settings

from nazbeen_forex_ai.analysis.llm_errors import (  # noqa: F401 — re-exported
    LLMError,
    LLMConfigurationError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMResponseFormatError,
)
from nazbeen_forex_ai.analysis.schemas import LLMChartAssessment, LLMReasoningOutput

LLMRole = Literal["vision", "reasoning"]
SUPPORTED_PROVIDERS = ("openai", "gemini")

REDACTED = "***REDACTED***"


class BaseLLMProvider(ABC):
    """Typed provider contract. Subclasses must never leak credentials."""

    role: LLMRole = "vision"
    provider_name: str = "base"
    model: str = ""

    @abstractmethod
    def inspect_chart(
        self,
        prompt: str,
        image_bytes: Optional[bytes] = None,
        image_mime: Optional[str] = None,
    ) -> LLMChartAssessment:
        """Analyze a chart screenshot (vision)."""

    @abstractmethod
    def reason(self, prompt: str) -> LLMReasoningOutput:
        """Produce a grounded explanation/scenario write-up (reasoning)."""

    def describe(self) -> Dict[str, Any]:
        """Safe, loggable description — never includes the API key."""
        return {
            "provider": self.provider_name,
            "model": self.model,
            "role": self.role,
            "mock": self.provider_name == "mock",
        }

    def __repr__(self) -> str:  # defense in depth: repr never shows the key
        return (
            f"{type(self).__name__}(role={self.role!r}, model={self.model!r}, "
            f"api_key={REDACTED!r})"
        )


class MockLLMProvider(BaseLLMProvider):
    """Labeled mock provider for development and the automated test suite.

    It performs no inference and fabricates nothing: observations are empty,
    direction is neutral, and every response states that it is a mock.
    """

    provider_name = "mock"
    model = "mock"

    def __init__(self, role: LLMRole = "vision") -> None:
        self.role = role

    def inspect_chart(
        self,
        prompt: str,
        image_bytes: Optional[bytes] = None,
        image_mime: Optional[str] = None,
    ) -> LLMChartAssessment:
        has_image = image_bytes is not None
        return LLMChartAssessment(
            observed_symbol=None,
            observed_timeframe=None,
            summary=(
                "Mock vision provider: no inference performed. Chart content was "
                "not inspected; exact price levels are never fabricated."
            ),
            direction="neutral",
            observations=[],
            candidate_levels=[],
            uncertainty=[
                "Mock provider active — screenshot not actually inspected."
            ],
            missing_evidence=(
                [] if has_image else ["No image was provided to the vision provider."]
            ),
            self_reported_confidence=None,
        )

    def reason(self, prompt: str) -> LLMReasoningOutput:
        return LLMReasoningOutput(
            explanation=(
                "Mock reasoning provider: no inference performed. Explanations "
                "must come from a configured real provider when USE_MOCK_LLM=false."
            ),
            bullish_scenario="",
            bearish_scenario="",
            key_risks=[],
            uncertainty=["Mock provider active — no reasoning performed."],
            missing_evidence=["Real reasoning provider not configured or not enabled."],
        )


@dataclass(frozen=True)
class LLMRoleConfig:
    role: LLMRole
    provider: str
    api_key: str
    model: str

    @property
    def env_prefix(self) -> str:
        return self.role.upper()


def _config_for_role(role: LLMRole) -> LLMRoleConfig:
    if role == "vision":
        return LLMRoleConfig(
            role="vision",
            provider=(getattr(settings, "VISION_LLM_PROVIDER", "") or "").strip().lower(),
            api_key=getattr(settings, "VISION_LLM_API_KEY", "") or "",
            model=(getattr(settings, "VISION_LLM_MODEL", "") or "").strip(),
        )
    if role == "reasoning":
        return LLMRoleConfig(
            role="reasoning",
            provider=(getattr(settings, "REASONING_LLM_PROVIDER", "") or "").strip().lower(),
            api_key=getattr(settings, "REASONING_LLM_API_KEY", "") or "",
            model=(getattr(settings, "REASONING_LLM_MODEL", "") or "").strip(),
        )
    raise ValueError(f"unknown LLM role: {role!r}")


def get_llm_provider(role: LLMRole = "vision") -> BaseLLMProvider:
    """Build the provider for ``role``.

    - Mock mode (``USE_MOCK_LLM=true``): labeled mock provider.
    - Real mode: the configured provider; misconfiguration raises
      :class:`LLMConfigurationError`. There is **no** silent mock fallback —
      a real provider failure surfaces to the caller.
    """
    if role not in ("vision", "reasoning"):
        raise ValueError(f"unknown LLM role: {role!r}")
    if getattr(settings, "USE_MOCK_LLM", True):
        return MockLLMProvider(role=role)

    cfg = _config_for_role(role)
    prefix = cfg.env_prefix
    if not cfg.provider:
        raise LLMConfigurationError(
            f"{role} LLM provider is not configured — set {prefix}_LLM_PROVIDER "
            f"({'|'.join(SUPPORTED_PROVIDERS)}), {prefix}_LLM_API_KEY and "
            f"{prefix}_LLM_MODEL, or set USE_MOCK_LLM=true to use the mock provider"
        )
    if cfg.provider not in SUPPORTED_PROVIDERS:
        raise LLMConfigurationError(
            f"unsupported {role} LLM provider {cfg.provider!r} — "
            f"supported: {', '.join(SUPPORTED_PROVIDERS)}"
        )
    if not cfg.api_key:
        raise LLMConfigurationError(
            f"{role} LLM API key is missing — set {prefix}_LLM_API_KEY"
        )
    if not cfg.model:
        raise LLMConfigurationError(
            f"{role} LLM model is missing — set {prefix}_LLM_MODEL"
        )

    # Imported lazily so the provider HTTP layer is only needed in real mode.
    from nazbeen_forex_ai.analysis.llm_providers import GeminiProvider, OpenAIProvider

    if cfg.provider == "openai":
        return OpenAIProvider(role=role, model=cfg.model, api_key=cfg.api_key)
    return GeminiProvider(role=role, model=cfg.model, api_key=cfg.api_key)


def get_vision_llm() -> BaseLLMProvider:
    return get_llm_provider("vision")


def get_reasoning_llm() -> BaseLLMProvider:
    return get_llm_provider("reasoning")
