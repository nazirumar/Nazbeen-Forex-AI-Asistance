"""LLM error hierarchy (Phase 11B).

Messages are safe by construction: they carry a provider label, an HTTP status
and at most a truncated, secret-stripped provider message. They never contain
the request payload, headers or API keys (MASTER_SPEC §7).
"""

from __future__ import annotations


class LLMError(Exception):
    """Base class for provider/transport failures with a safe message."""


class LLMConfigurationError(LLMError):
    """The provider is not configured (missing provider/key/model, bad name)."""


class LLMAuthenticationError(LLMError):
    """The provider rejected the API key (HTTP 401/403)."""


class LLMRateLimitError(LLMError):
    """The provider rate limit was hit and retries were exhausted (HTTP 429)."""


class LLMResponseFormatError(LLMError):
    """The provider answered, but the body was not the expected structured JSON."""
