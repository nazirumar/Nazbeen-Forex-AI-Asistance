"""Real LLM provider adapters: OpenAI and Google Gemini (Phase 11B).

Both adapters:
- send the chart screenshot as an image input (vision) — OpenAI via a base64
  ``image_url`` data part, Gemini via an ``inline_data`` part;
- force structured JSON output — OpenAI via ``response_format: json_object``,
  Gemini via ``responseMimeType: application/json`` — and validate the parsed
  body against the Pydantic claim schemas (invalid output raises
  :class:`LLMResponseFormatError`, it is never guessed at);
- keep the API key out of URLs, logs, reprs and error messages (Gemini uses the
  ``x-goog-api-key`` header rather than a ``?key=`` URL parameter).

All network I/O goes through :class:`HTTPTransport`, which adds per-attempt
timeouts, bounded retries with backoff, ``Retry-After`` rate-limit handling and
secret-stripped error messages.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, Optional

from django.conf import settings

from nazbeen_forex_ai.analysis.llm import BaseLLMProvider, LLMRole
from nazbeen_forex_ai.analysis.llm_errors import LLMResponseFormatError
from nazbeen_forex_ai.analysis.llm_transport import HTTPTransport
from nazbeen_forex_ai.analysis.schemas import LLMChartAssessment, LLMReasoningOutput

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

_TEMPERATURE = 0.1  # low: we want faithful readings, not creative ones

# JSON contracts embedded in the prompts. The models are told to return ONLY
# JSON matching these keys; anything else fails schema validation loudly.
_CHART_ASSESSMENT_CONTRACT = (
    "Respond with ONLY a JSON object (no prose, no markdown fences) matching:\n"
    '{"observed_symbol": string|null, "observed_timeframe": string|null, '
    '"summary": string, "direction": "bullish"|"bearish"|"neutral", '
    '"observations": [string], "candidate_levels": [number], '
    '"uncertainty": [string], "missing_evidence": [string], '
    '"self_reported_confidence": number|null}\n'
    "Rules: never invent exact price levels that are not legible in the image; "
    "put any unreadable or missing information into missing_evidence/uncertainty; "
    "you never make a trading decision — you only report what you observe."
)

_REASONING_CONTRACT = (
    "Respond with ONLY a JSON object (no prose, no markdown fences) matching:\n"
    '{"explanation": string, "bullish_scenario": string, "bearish_scenario": string, '
    '"key_risks": [string], "uncertainty": [string], "missing_evidence": [string]}\n'
    "Rules: explain the supplied deterministic findings — never invent market "
    "facts, price levels or probabilities; state uncertainty explicitly."
)


def _strip_code_fences(text: str) -> str:
    """Remove ```json fences if a model wrapped its JSON anyway."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        # drop the opening fence (and its language tag) and a trailing fence
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


class BaseHTTPProvider(BaseLLMProvider):
    """Shared construction/validation logic for HTTP-backed providers."""

    def __init__(
        self,
        *,
        role: LLMRole,
        model: str,
        api_key: str,
        transport: HTTPTransport | None = None,
    ) -> None:
        self.role = role
        self.model = model
        self._api_key = api_key  # never exposed via repr/describe/errors
        self._transport = transport or HTTPTransport(
            timeout_seconds=getattr(settings, "LLM_TIMEOUT_SECONDS", 60),
            max_retries=getattr(settings, "LLM_MAX_RETRIES", 2),
            backoff_seconds=getattr(settings, "LLM_RETRY_BACKOFF_SECONDS", 1),
            secrets=[api_key],
        )

    # -- JSON handling -------------------------------------------------------
    def _extract_json(self, text: str) -> Dict[str, Any]:
        candidate = _strip_code_fences(text or "")
        if not candidate:
            raise LLMResponseFormatError(f"{self.provider_name} returned an empty response")
        # Tolerate a model that prefaced the object with stray prose.
        if not candidate.startswith("{"):
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start == -1 or end <= start:
                raise LLMResponseFormatError(
                    f"{self.provider_name} response did not contain a JSON object"
                )
            candidate = candidate[start : end + 1]
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            raise LLMResponseFormatError(
                f"{self.provider_name} response was not valid JSON"
            ) from None
        if not isinstance(data, dict):
            raise LLMResponseFormatError(
                f"{self.provider_name} response JSON was not an object"
            )
        return data

    @staticmethod
    def _validate_or_fail(schema, data: Dict[str, Any], provider: str, what: str):
        try:
            return schema.model_validate(data)
        except Exception as exc:
            raise LLMResponseFormatError(
                f"{provider} {what} failed schema validation ({type(exc).__name__})"
            ) from None

    # -- public contract -----------------------------------------------------
    def inspect_chart(
        self,
        prompt: str,
        image_bytes: Optional[bytes] = None,
        image_mime: Optional[str] = None,
    ) -> LLMChartAssessment:
        full_prompt = f"{prompt.strip()}\n\n{_CHART_ASSESSMENT_CONTRACT}"
        raw = self._complete(full_prompt, image_bytes=image_bytes, image_mime=image_mime)
        data = self._extract_json(raw)
        return self._validate_or_fail(
            LLMChartAssessment, data, self.provider_name, "chart assessment"
        )

    def reason(self, prompt: str) -> LLMReasoningOutput:
        full_prompt = f"{prompt.strip()}\n\n{_REASONING_CONTRACT}"
        raw = self._complete(full_prompt, image_bytes=None, image_mime=None)
        data = self._extract_json(raw)
        return self._validate_or_fail(
            LLMReasoningOutput, data, self.provider_name, "reasoning output"
        )

    # -- provider-specific ---------------------------------------------------
    def _complete(
        self,
        prompt: str,
        image_bytes: Optional[bytes] = None,
        image_mime: Optional[str] = None,
    ) -> str:
        raise NotImplementedError


class OpenAIProvider(BaseHTTPProvider):
    """OpenAI Chat Completions adapter (vision via base64 ``image_url`` part)."""

    provider_name = "openai"

    def _complete(
        self,
        prompt: str,
        image_bytes: Optional[bytes] = None,
        image_mime: Optional[str] = None,
    ) -> str:
        content: list[Dict[str, Any]] = [{"type": "text", "text": prompt}]
        if image_bytes:
            mime = image_mime or "image/png"
            encoded = base64.b64encode(image_bytes).decode("ascii")
            content.append(
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}
            )
        payload = {
            "model": self.model,
            "temperature": _TEMPERATURE,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a forex chart analyst. You report observations only; "
                        "you never issue trading decisions and never invent price levels."
                    ),
                },
                {"role": "user", "content": content},
            ],
        }
        data = self._transport.post_json(
            OPENAI_CHAT_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            payload=payload,
            provider_label="openai",
        )
        try:
            message = data["choices"][0]["message"]
            text = message.get("content") or ""
        except (KeyError, IndexError, TypeError):
            raise LLMResponseFormatError(
                "openai response missing choices[0].message.content"
            ) from None
        if not isinstance(text, str):
            raise LLMResponseFormatError("openai response content was not text")
        return text


class GeminiProvider(BaseHTTPProvider):
    """Google Gemini ``generateContent`` adapter (vision via ``inline_data``)."""

    provider_name = "gemini"

    def _complete(
        self,
        prompt: str,
        image_bytes: Optional[bytes] = None,
        image_mime: Optional[str] = None,
    ) -> str:
        parts: list[Dict[str, Any]] = [{"text": prompt}]
        if image_bytes:
            mime = image_mime or "image/png"
            parts.append(
                {
                    "inline_data": {
                        "mime_type": mime,
                        "data": base64.b64encode(image_bytes).decode("ascii"),
                    }
                }
            )
        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": _TEMPERATURE,
                "responseMimeType": "application/json",
            },
        }
        model = self.model.removeprefix("models/")
        # API key travels in a header — never in the URL (logs, proxies).
        data = self._transport.post_json(
            f"{GEMINI_BASE_URL}/{model}:generateContent",
            headers={"x-goog-api-key": self._api_key, "Content-Type": "application/json"},
            payload=payload,
            provider_label="gemini",
        )
        try:
            candidate = data["candidates"][0]
            parts_out = candidate["content"]["parts"]
            text = "".join(
                part["text"]
                for part in parts_out
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            )
        except (KeyError, IndexError, TypeError):
            raise LLMResponseFormatError(
                "gemini response missing candidates[0].content.parts"
            ) from None
        if not text:
            raise LLMResponseFormatError("gemini returned no text parts")
        return text
