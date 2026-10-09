"""Logging helpers: secret redaction and optional JSON formatting (Roadmap Phase 10).

Redaction is defense-in-depth: even if an exception message or a debug statement
leaks a credential-like value, it must never reach log output (MASTER_SPEC §7).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

# Keys whose values are masked when they appear as `key=value`, `key: value`
# or `"key": "value"` in a log message.
SENSITIVE_KEYS = (
    "password",
    "passwd",
    "secret",
    "secret_key",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "credential",
    "credentials",
)

REDACTED = "***REDACTED***"

# Matches `password=...`, `password: ...`, `"password": "..."` (any key from SENSITIVE_KEYS).
_KEY_VALUE_RE = re.compile(
    r"(?i)\b("
    + "|".join(re.escape(k) for k in SENSITIVE_KEYS)
    + r")\"?(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|\S+)"
)

# Matches `Token abc123` / `Bearer abc123` auth headers.
_BEARER_RE = re.compile(r"(?i)\b(token|bearer)\b(\s+)([A-Za-z0-9\-_.+/=]+)")


def redact_text(text: str) -> str:
    """Mask credential-like substrings in *text*. Never raises."""
    if not text:
        return text
    # Bearer/Token patterns first: `Authorization: Token abc` — otherwise the
    # key=value pass would consume only the word "Token" and leak the value.
    out = _BEARER_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", text)
    out = _KEY_VALUE_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", out)
    return out


class SecretRedactionFilter(logging.Filter):
    """Logging filter that redacts secrets from the formatted message."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D102
        try:
            message = record.getMessage()
            redacted = redact_text(message)
            if redacted != message:
                record.msg = redacted
                record.args = ()
            # Exception traces can also contain secrets.
            if record.exc_text:
                record.exc_text = redact_text(record.exc_text)
        except Exception:  # pragma: no cover — never break logging
            pass
        return True


class JsonFormatter(logging.Formatter):
    """Minimal JSON line formatter (one object per line, UTC timestamps)."""

    def format(self, record: logging.LogRecord) -> str:
        from datetime import datetime, timezone

        payload: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(record.getMessage()),
        }
        if record.exc_info:
            payload["exception"] = redact_text(self.formatException(record.exc_info))
        # Preserve explicitly attached structured extras (skipping standard attrs).
        standard = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__)
        for key, value in record.__dict__.items():
            if key not in standard and key not in payload and not key.startswith("_"):
                payload[key] = value if isinstance(value, (str, int, float, bool, type(None), list, dict)) else str(value)
        return json.dumps(payload, ensure_ascii=False, default=str)
