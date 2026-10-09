"""Logging redaction and JSON formatting tests (Roadmap Phase 10)."""

from __future__ import annotations

import json
import logging

from nazbeen_forex_ai.core.logging_extras import (
    REDACTED,
    JsonFormatter,
    SecretRedactionFilter,
    redact_text,
)


def test_redact_password_assignment() -> None:
    out = redact_text("login attempt password=SuperSecret123 ok")
    assert "SuperSecret123" not in out
    assert REDACTED in out


def test_redact_json_style_secret() -> None:
    out = redact_text('{"secret_key": "abcdef123456"}')
    assert "abcdef123456" not in out
    assert REDACTED in out


def test_redact_bearer_token() -> None:
    out = redact_text("Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b")
    assert "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b" not in out


def test_redact_leaves_normal_text_alone() -> None:
    msg = "Health check passed in 12ms"
    assert redact_text(msg) == msg


def test_filter_redacts_log_record() -> None:
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="connecting with password=%s", args=("hunter2",),
        exc_info=None,
    )
    SecretRedactionFilter().filter(record)
    formatted = record.getMessage()
    assert "hunter2" not in formatted
    assert REDACTED in formatted


def test_json_formatter_outputs_valid_json_and_redacts() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test.json", level=logging.WARNING, pathname=__file__, lineno=2,
        msg="token %s leaked", args=("abc123secret",), exc_info=None,
    )
    line = formatter.format(record)
    payload = json.loads(line)
    assert payload["level"] == "WARNING"
    assert payload["logger"] == "test.json"
    assert "abc123secret" not in payload["message"]
    assert payload["time"].endswith("Z")
