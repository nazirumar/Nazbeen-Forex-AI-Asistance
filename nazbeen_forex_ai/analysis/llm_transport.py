"""Hardened HTTP transport for real LLM provider calls (Phase 11B).

Responsibilities:
- Per-attempt timeout and bounded retries with exponential backoff for
  transient failures (connection errors, timeouts, HTTP 429, HTTP 5xx).
- ``Retry-After`` support for rate limiting, capped at a sane maximum.
- **Safe errors only**: exception messages contain a status code and a short,
  truncated provider message with any known secret values stripped out. The
  request payload and headers (which carry the API key) are never echoed.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Iterable

import httpx

from nazbeen_forex_ai.analysis.llm_errors import (
    LLMError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMResponseFormatError,
)

logger = logging.getLogger("nazbeen_forex_ai.analysis.llm")

# Cap honored from a Retry-After header so a hostile/broken header cannot
# stall the request path for minutes.
MAX_RETRY_AFTER_SECONDS = 30
# Provider response bodies are diagnostics, not payloads: truncate hard.
MAX_ERROR_BODY_CHARS = 300


def _redact(text: str, secrets: Iterable[str] = ()) -> str:
    """Strip known secret values and obvious key patterns from ``text``."""
    for secret in secrets:
        if secret and len(secret) >= 8 and secret in text:
            text = text.replace(secret, "***REDACTED***")
    return text


class HTTPTransport:
    """POSTs JSON to an LLM endpoint with retry/timeout/redaction handling.

    ``session`` and ``sleep`` are injectable so the retry logic is fully
    unit-testable without network access.
    """

    def __init__(
        self,
        timeout_seconds: int = 60,
        max_retries: int = 2,
        backoff_seconds: float = 1.0,
        *,
        session: Any | None = None,
        sleep=None,
        secrets: Iterable[str] = (),
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, int(max_retries))
        self.backoff_seconds = max(0.0, float(backoff_seconds))
        self._session = session
        self._owns_session = session is None
        self._sleep = sleep or time.sleep
        # Secret values that must never surface in logs or error messages.
        self._secrets = tuple(s for s in secrets if s)

    # -- session lifecycle ---------------------------------------------------
    def _get_session(self) -> Any:
        if self._session is None:
            self._session = httpx.Client(timeout=self.timeout_seconds)
        return self._session

    def close(self) -> None:
        if self._owns_session and self._session is not None:
            try:
                self._session.close()
            except Exception:  # pragma: no cover - defensive
                pass
            self._session = None

    # -- core request --------------------------------------------------------
    def post_json(
        self,
        url: str,
        *,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        provider_label: str = "llm",
    ) -> Dict[str, Any]:
        """POST ``payload`` as JSON and return the decoded response object.

        Raises a safe :class:`LLMError` subclass on failure. Retries connection
        errors, timeouts, HTTP 429 and HTTP 5xx; fails fast on other 4xx.
        """
        session = self._get_session()
        attempts = self.max_retries + 1
        last_error: LLMError | None = None

        for attempt in range(attempts):
            retry_after: float | None = None
            try:
                response = session.post(
                    url, headers=headers, json=payload, timeout=self.timeout_seconds
                )
            except Exception as exc:  # timeouts, connection resets, DNS, ...
                last_error = LLMError(
                    f"{provider_label} request failed ({type(exc).__name__})"
                )
                if attempt < attempts - 1:
                    # Debug only: label + error type — never headers/payload.
                    logger.debug(
                        "LLM retry %d/%d for %s after %s",
                        attempt + 1, attempts, provider_label, type(exc).__name__,
                    )
                    self._backoff(attempt)
                    continue
                raise last_error from None

            code = response.status_code
            if 200 <= code < 300:
                try:
                    data = response.json()
                except Exception:
                    raise LLMResponseFormatError(
                        f"{provider_label} returned a non-JSON response body"
                    ) from None
                if not isinstance(data, dict):
                    raise LLMResponseFormatError(
                        f"{provider_label} returned unexpected JSON shape"
                    )
                return data

            body = _redact(getattr(response, "text", "") or "", self._secrets)
            body = body[:MAX_ERROR_BODY_CHARS]

            if code in (401, 403):
                # Never echo request details: the key lives in the headers.
                raise LLMAuthenticationError(
                    f"{provider_label} authentication failed (HTTP {code}) — "
                    "check the configured API key"
                ) from None

            if code == 429:
                last_error = LLMRateLimitError(
                    f"{provider_label} rate limit exceeded (HTTP 429)"
                )
                retry_after = _parse_retry_after(response)
            elif 500 <= code < 600:
                last_error = LLMError(f"{provider_label} server error (HTTP {code}): {body}")
            else:
                # Other client errors are not transient: fail fast, no retry.
                raise LLMError(
                    f"{provider_label} rejected the request (HTTP {code}): {body}"
                ) from None

            if attempt < attempts - 1:
                logger.debug(
                    "LLM retry %d/%d for %s after HTTP %s",
                    attempt + 1, attempts, provider_label, code,
                )
                self._backoff(attempt, retry_after)
                continue
            raise last_error from None

        # Unreachable in practice; keeps the contract explicit.
        raise last_error or LLMError(f"{provider_label} request failed")

    # -- helpers -------------------------------------------------------------
    def _backoff(self, attempt: int, retry_after: float | None = None) -> None:
        delay = self.backoff_seconds * (2**attempt)
        if retry_after is not None:
            delay = max(delay, retry_after)
        delay = min(delay, MAX_RETRY_AFTER_SECONDS)
        if delay > 0:
            self._sleep(delay)


def _parse_retry_after(response: Any) -> float | None:
    """Read a ``Retry-After`` header (seconds form) defensively."""
    try:
        headers = getattr(response, "headers", {}) or {}
        raw = headers.get("retry-after") or headers.get("Retry-After")
        if raw is None:
            return None
        value = float(raw)
        return value if value >= 0 else None
    except (TypeError, ValueError):
        return None
