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
