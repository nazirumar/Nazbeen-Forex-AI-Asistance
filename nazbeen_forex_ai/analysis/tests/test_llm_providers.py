"""LLM provider adapter tests (Phase 11B) — no network, no keys.

Real HTTP is replaced by fake sessions; the suite runs hermetically with
``USE_MOCK_LLM=true`` while exercising every real-provider code path.
"""

from __future__ import annotations

import json

import pytest
from django.test import override_settings

from nazbeen_forex_ai.analysis import llm as llm_module
from nazbeen_forex_ai.analysis.llm import (
    LLMConfigurationError,
    LLMError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMResponseFormatError,
    MockLLMProvider,
    get_llm_provider,
)
from nazbeen_forex_ai.analysis.llm_providers import (
    OPENAI_CHAT_URL,
    GeminiProvider,
    OpenAIProvider,
)
from nazbeen_forex_ai.analysis.llm_transport import HTTPTransport

FAKE_KEY = "sk-test-super-secret-key-123456"
FAKE_GEMINI_KEY = "AIza-test-gemini-key-123456"


# ---------------------------------------------------------------------------
# Fake HTTP session plumbing
# ---------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status_code: int, json_data=None, text: str = "", headers=None):
        self.status_code = status_code
        self._json = json_data
        self.text = text
        self.headers = headers or {}

    def json(self):
        if self._json is None:
            raise ValueError("no json body")
        return self._json


class FakeSession:
    """Returns scripted responses/exceptions in order; records every call."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self):
        pass


def _transport(session, max_retries=2, secrets=()):
    return HTTPTransport(
        timeout_seconds=5,
        max_retries=max_retries,
        backoff_seconds=0,
        session=session,
        sleep=lambda _s: None,
        secrets=secrets,
    )


VALID_ASSESSMENT = {
    "observed_symbol": "EURUSD",
    "observed_timeframe": "M15",
    "summary": "Rising structure with a bullish imbalance.",
    "direction": "bullish",
    "observations": ["higher highs", "bullish FVG visible"],
    "candidate_levels": [1.102, 1.099],
    "uncertainty": ["spread not legible"],
    "missing_evidence": ["screenshot timestamp unknown"],
    "self_reported_confidence": 0.6,
}

VALID_REASONING = {
    "explanation": "Deterministic bias is bullish and an FVG is present.",
    "bullish_scenario": "Retest of the imbalance then continuation.",
    "bearish_scenario": "Loss of the last swing low invalidates.",
    "key_risks": ["news event"],
    "uncertainty": ["M1 confirmation missing"],
    "missing_evidence": [],
}


def _openai_completion(content: str) -> FakeResponse:
    return FakeResponse(200, {"choices": [{"message": {"content": content}}]})


def _gemini_response(text: str) -> FakeResponse:
    return FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": text}]}}]})


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

@override_settings(USE_MOCK_LLM=True, VISION_LLM_PROVIDER="openai",
                   VISION_LLM_API_KEY=FAKE_KEY, VISION_LLM_MODEL="gpt-4o-mini")
def test_factory_returns_mock_in_mock_mode_even_when_real_configured():
    provider = get_llm_provider("vision")
    assert isinstance(provider, MockLLMProvider)
    assert provider.describe()["mock"] is True


@override_settings(USE_MOCK_LLM=False, VISION_LLM_PROVIDER="openai",
                   VISION_LLM_API_KEY=FAKE_KEY, VISION_LLM_MODEL="gpt-4o-mini")
def test_factory_builds_openai_vision_provider():
    provider = get_llm_provider("vision")
    assert isinstance(provider, OpenAIProvider)
    assert provider.model == "gpt-4o-mini"
    assert provider.role == "vision"


@override_settings(USE_MOCK_LLM=False, REASONING_LLM_PROVIDER="gemini",
                   REASONING_LLM_API_KEY=FAKE_GEMINI_KEY, REASONING_LLM_MODEL="gemini-1.5-flash")
def test_factory_builds_gemini_reasoning_provider():
    provider = get_llm_provider("reasoning")
    assert isinstance(provider, GeminiProvider)
    assert provider.model == "gemini-1.5-flash"
    assert provider.role == "reasoning"


@override_settings(USE_MOCK_LLM=False, VISION_LLM_PROVIDER="", VISION_LLM_API_KEY=FAKE_KEY,
                   VISION_LLM_MODEL="gpt-4o-mini")
def test_factory_unconfigured_raises_never_silently_mocks():
    with pytest.raises(LLMConfigurationError, match="VISION_LLM_PROVIDER"):
        get_llm_provider("vision")


@override_settings(USE_MOCK_LLM=False, VISION_LLM_PROVIDER="anthropic",
                   VISION_LLM_API_KEY=FAKE_KEY, VISION_LLM_MODEL="claude")
def test_factory_unsupported_provider_raises():
    with pytest.raises(LLMConfigurationError, match="supported: openai, gemini"):
        get_llm_provider("vision")


@override_settings(USE_MOCK_LLM=False, VISION_LLM_PROVIDER="openai", VISION_LLM_API_KEY="",
                   VISION_LLM_MODEL="gpt-4o-mini")
def test_factory_missing_key_raises():
    with pytest.raises(LLMConfigurationError, match="VISION_LLM_API_KEY"):
        get_llm_provider("vision")


@override_settings(USE_MOCK_LLM=False, VISION_LLM_PROVIDER="openai", VISION_LLM_API_KEY=FAKE_KEY,
                   VISION_LLM_MODEL="")
def test_factory_missing_model_raises():
    with pytest.raises(LLMConfigurationError, match="VISION_LLM_MODEL"):
        get_llm_provider("vision")


def test_factory_unknown_role_raises():
    with pytest.raises(ValueError, match="unknown LLM role"):
        get_llm_provider("not-a-role")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Mock provider honesty
# ---------------------------------------------------------------------------

def test_mock_provider_fabricates_nothing():
    p = MockLLMProvider(role="vision")
    a = p.inspect_chart("prompt", b"\x89PNGdata", "image/png")
    assert a.direction == "neutral"
    assert a.candidate_levels == []
    assert a.observations == []
    assert any("Mock" in u for u in a.uncertainty)
    r = p.reason("prompt")
    assert "Mock" in r.explanation
    assert r.bullish_scenario == "" and r.bearish_scenario == ""


def test_mock_provider_repr_and_describe_hide_nothing_but_have_no_key():
    p = MockLLMProvider(role="reasoning")
    assert "mock" in repr(p)
    assert p.describe() == {"provider": "mock", "model": "mock", "role": "reasoning", "mock": True}


# ---------------------------------------------------------------------------
# Transport: retries, rate limits, safe errors
# ---------------------------------------------------------------------------

def test_transport_success_single_call():
    session = FakeSession([FakeResponse(200, {"ok": True})])
    data = _transport(session).post_json("https://x", headers={}, payload={})
    assert data == {"ok": True}
    assert len(session.calls) == 1


def test_transport_429_retries_and_honours_retry_after():
    sleeps = []
    session = FakeSession([
        FakeResponse(429, text="rate limited", headers={"Retry-After": "7"}),
        FakeResponse(200, {"ok": True}),
    ])
    transport = HTTPTransport(
        timeout_seconds=5, max_retries=2, backoff_seconds=0,
        session=session, sleep=sleeps.append,
    )
    assert transport.post_json("https://x", headers={}, payload={}) == {"ok": True}
    assert len(session.calls) == 2
    assert sleeps and sleeps[0] == 7  # Retry-After honoured exactly


def test_transport_rate_limit_exhausted_raises():
    session = FakeSession([FakeResponse(429, text="rate limited") for _ in range(3)])
    with pytest.raises(LLMRateLimitError, match="rate limit"):
        _transport(session).post_json("https://x", headers={}, payload={})
    assert len(session.calls) == 3  # initial + 2 retries


def test_transport_5xx_retries_then_succeeds():
    session = FakeSession([
        FakeResponse(500, text="boom"),
        FakeResponse(500, text="boom"),
        FakeResponse(200, {"ok": True}),
    ])
    assert _transport(session, max_retries=2).post_json("https://x", headers={}, payload={}) == {"ok": True}
    assert len(session.calls) == 3


def test_transport_timeout_retries_then_succeeds():
    session = FakeSession([TimeoutError("timed out"), FakeResponse(200, {"ok": True})])
    assert _transport(session).post_json("https://x", headers={}, payload={}) == {"ok": True}


def test_transport_401_fails_fast_and_names_no_key():
    session = FakeSession([FakeResponse(401, text="invalid api key")])
    with pytest.raises(LLMAuthenticationError) as exc:
        _transport(session, secrets=[FAKE_KEY]).post_json(
            "https://x", headers={"Authorization": f"Bearer {FAKE_KEY}"}, payload={}
        )
    assert len(session.calls) == 1  # no retry on auth failure
    message = str(exc.value)
    assert "authentication failed" in message
    assert FAKE_KEY not in message


def test_transport_400_fails_fast_without_retry():
    session = FakeSession([FakeResponse(400, text="bad request")])
    with pytest.raises(LLMError, match="HTTP 400"):
        _transport(session).post_json("https://x", headers={}, payload={})
    assert len(session.calls) == 1


def test_transport_redacts_secret_from_provider_error_body():
    # max_retries=2 → 3 attempts, so script one 500 body per attempt.
    session = FakeSession([FakeResponse(500, text=f"upstream leaked {FAKE_KEY} in trace")] * 3)
    with pytest.raises(LLMError) as exc:
        _transport(session, secrets=[FAKE_KEY]).post_json("https://x", headers={}, payload={})
    assert FAKE_KEY not in str(exc.value)
    assert "***REDACTED***" in str(exc.value)
    assert len(session.calls) == 3


def test_transport_non_json_success_body_raises_format_error():
    session = FakeSession([FakeResponse(200, json_data=None, text="<html>gateway</html>")])
    with pytest.raises(LLMResponseFormatError, match="non-JSON"):
        _transport(session).post_json("https://x", headers={}, payload={})


def test_transport_retry_after_header_is_capped():
    sleeps = []
    session = FakeSession([
        FakeResponse(429, headers={"Retry-After": "9999"}),
        FakeResponse(200, {"ok": True}),
    ])
    transport = HTTPTransport(
        timeout_seconds=5, max_retries=1, backoff_seconds=0,
        session=session, sleep=sleeps.append,
    )
    transport.post_json("https://x", headers={}, payload={})
    assert sleeps and sleeps[0] == 30  # capped at MAX_RETRY_AFTER_SECONDS


# ---------------------------------------------------------------------------
# OpenAI adapter
# ---------------------------------------------------------------------------

def _openai(image_bytes=None, mime="image/png", script=None):
    session = FakeSession(script or [_openai_completion(json.dumps(VALID_ASSESSMENT))])
    provider = OpenAIProvider(role="vision", model="gpt-4o-mini", api_key=FAKE_KEY,
                              transport=_transport(session, secrets=[FAKE_KEY]))
    return provider, session


def test_openai_inspect_chart_parses_structured_json():
    provider, session = _openai()
    a = provider.inspect_chart("analyze", b"PNGDATA", "image/png")
    assert a.direction == "bullish"
    assert a.observed_symbol == "EURUSD"
    assert a.candidate_levels == [1.102, 1.099]
    call = session.calls[0]
    assert call["url"] == OPENAI_CHAT_URL
    assert call["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    assert call["json"]["response_format"] == {"type": "json_object"}
    # vision payload: base64 data URL image part
    user_content = call["json"]["messages"][1]["content"]
    image_parts = [p for p in user_content if p.get("type") == "image_url"]
    assert len(image_parts) == 1
    assert image_parts[0]["image_url"]["url"].startswith("data:image/png;base64,")


def test_openai_strips_markdown_fences():
    fenced = "```json\n" + json.dumps(VALID_ASSESSMENT) + "\n```"
    provider, _ = _openai(script=[_openai_completion(fenced)])
    assert provider.inspect_chart("p").observed_symbol == "EURUSD"


def test_openai_tolerates_surrounding_prose():
    noisy = "Here you go:\n" + json.dumps(VALID_ASSESSMENT) + "\nHope that helps."
    provider, _ = _openai(script=[_openai_completion(noisy)])
    assert provider.inspect_chart("p").direction == "bullish"


def test_openai_invalid_json_raises_format_error():
    provider, _ = _openai(script=[_openai_completion("not json at all")])
    with pytest.raises(LLMResponseFormatError):
        provider.inspect_chart("p")


def test_openai_schema_violation_raises_format_error():
    bad = dict(VALID_ASSESSMENT, direction="sideways")
    provider, _ = _openai(script=[_openai_completion(json.dumps(bad))])
    with pytest.raises(LLMResponseFormatError, match="schema validation"):
        provider.inspect_chart("p")


def test_openai_missing_choices_raises_format_error():
    provider, _ = _openai(script=[FakeResponse(200, {"choices": []})])
    with pytest.raises(LLMResponseFormatError):
        provider.inspect_chart("p")


def test_openai_reason_returns_reasoning_output():
    provider, _ = _openai(script=[_openai_completion(json.dumps(VALID_REASONING))])
    r = provider.reason("explain")
    assert r.bullish_scenario.startswith("Retest")
    assert r.key_risks == ["news event"]


def test_openai_provider_never_renders_api_key():
    provider, _ = _openai()
    assert FAKE_KEY not in repr(provider)
    assert FAKE_KEY not in str(provider.describe())


# ---------------------------------------------------------------------------
# Gemini adapter
# ---------------------------------------------------------------------------

def _gemini(image_bytes=None, mime="image/png", script=None):
    session = FakeSession(script or [_gemini_response(json.dumps(VALID_ASSESSMENT))])
    provider = GeminiProvider(role="vision", model="gemini-1.5-flash", api_key=FAKE_GEMINI_KEY,
                              transport=_transport(session, secrets=[FAKE_GEMINI_KEY]))
    return provider, session


def test_gemini_inspect_chart_parses_and_sends_inline_image():
    provider, session = _gemini()
    a = provider.inspect_chart("analyze", b"PNGDATA", "image/png")
    assert a.direction == "bullish"
    call = session.calls[0]
    assert "gemini-1.5-flash:generateContent" in call["url"]
    # API key travels in a header, never in the URL
    assert FAKE_GEMINI_KEY not in call["url"]
    assert call["headers"]["x-goog-api-key"] == FAKE_GEMINI_KEY
    parts = call["json"]["contents"][0]["parts"]
    inline = [p for p in parts if "inline_data" in p]
    assert len(inline) == 1
    assert inline[0]["inline_data"]["mime_type"] == "image/png"
    assert call["json"]["generationConfig"]["responseMimeType"] == "application/json"


def test_gemini_model_prefix_normalized():
    provider, session = _gemini(script=[_gemini_response(json.dumps(VALID_REASONING))])
    provider.model = "models/gemini-1.5-flash"
    provider.reason("p")
    url = session.calls[0]["url"]
    # The "models/" model-name prefix is stripped so the path never doubles up.
    assert url.endswith("/v1beta/models/gemini-1.5-flash:generateContent")
    assert "models/models/" not in url


def test_gemini_missing_candidates_raises_format_error():
    provider, _ = _gemini(script=[FakeResponse(200, {"candidates": []})])
    with pytest.raises(LLMResponseFormatError):
        provider.inspect_chart("p")


def test_gemini_joins_multiple_text_parts():
    payload = json.dumps(VALID_ASSESSMENT)
    split = _gemini_response("")  # placeholder replaced below
    split._json = {"candidates": [{"content": {"parts": [
        {"text": payload[:50]}, {"text": payload[50:]},
    ]}}]}
    provider, _ = _gemini(script=[split])
    assert provider.inspect_chart("p").direction == "bullish"


def test_gemini_provider_never_renders_api_key():
    provider, _ = _gemini()
    assert FAKE_GEMINI_KEY not in repr(provider)
    assert FAKE_GEMINI_KEY not in str(provider.describe())
