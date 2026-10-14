"""Tests for settings safety rules (ADR-004, MASTER_SPEC §7)."""

from __future__ import annotations

import importlib
import sys

import django
import pytest


def test_production_settings_reject_insecure_secret_key(monkeypatch) -> None:
    """Production must refuse to start with the development fallback key."""
    import nazbeen_forex_ai.settings.base as base_module

    monkeypatch.setattr(
        base_module,
        "SECRET_KEY",
        "insecure-development-only-key-do-not-use-in-prod",
    )
    sys.modules.pop("nazbeen_forex_ai.settings.production", None)

    with pytest.raises(django.core.exceptions.ImproperlyConfigured):
        importlib.import_module("nazbeen_forex_ai.settings.production")

    sys.modules.pop("nazbeen_forex_ai.settings.production", None)


def test_base_settings_use_utc() -> None:
    from django.conf import settings

    assert settings.USE_TZ is True
    assert settings.TIME_ZONE == "UTC"


def test_installed_apps_include_project_apps() -> None:
    from django.conf import settings

    assert "nazbeen_forex_ai.core" in settings.INSTALLED_APPS
    assert "rest_framework" in settings.INSTALLED_APPS


def test_production_settings_default_hsts_on(monkeypatch) -> None:
    """L-04: HSTS must be on by default in production (override to disable)."""
    import nazbeen_forex_ai.settings.base as base_module

    monkeypatch.setattr(base_module, "SECRET_KEY", "prod-test-key-not-insecure")
    monkeypatch.delenv("SECURE_HSTS_SECONDS", raising=False)
    sys.modules.pop("nazbeen_forex_ai.settings.production", None)
    try:
        prod = importlib.import_module("nazbeen_forex_ai.settings.production")
        assert prod.SECURE_HSTS_SECONDS == 31536000
        assert prod.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
        assert prod.SECURE_HSTS_PRELOAD is True
    finally:
        sys.modules.pop("nazbeen_forex_ai.settings.production", None)


def test_env_example_defaults_to_mock_market_data() -> None:
    """M-12: the template must be mock-first, never claim live MT5 data."""
    from django.conf import settings

    text = (settings.BASE_DIR / ".env.example").read_text(encoding="utf-8")
    assert "MT5_USE_MOCK=true" in text
    assert "MT5_USE_MOCK=false" not in text
