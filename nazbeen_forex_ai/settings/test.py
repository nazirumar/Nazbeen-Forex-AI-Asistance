"""Test settings — selected by pytest via ``DJANGO_SETTINGS_MODULE``."""

from __future__ import annotations

from .base import *  # noqa: F403 — deliberate settings inheritance

DEBUG = False

SECRET_KEY = "test-secret-key-not-for-production"

ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

# Fast password hashing — tests never need production-strength hashing.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# In-memory SQLite keeps the suite fast and isolated from db.sqlite3.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Django 6.1: define MAILERS (never the deprecated EMAIL_BACKEND) for tests.
MAILERS = {
    "default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"},
}

# --- Test isolation for market data (audit CRIT-04) ---------------------------
# Force the mock market-data provider for the entire test suite. This makes the
# factory select MockMarketDataProvider regardless of any local `.env` value of
# MT5_USE_MOCK, so the suite is hermetic and never requires a live MT5 terminal.
# NOTE: the factory uses `env_bool(...) or settings.MT5_USE_MOCK`; setting this
# True guarantees mock selection even when a developer's .env has MT5_USE_MOCK=false.
MT5_USE_MOCK = True

# --- Test isolation for LLM providers (Phase 11B) -----------------------------
# The suite always runs against the labeled mock LLM providers regardless of any
# local `.env` (real-provider behavior is covered by unit tests with fake HTTP
# sessions — no network access, no keys required).
USE_MOCK_LLM = True

# Tests never talk to a real broker: tasks run synchronously in-process.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
# Deterministic non-routable URL: configuration assertions don't depend on the
# developer's .env, and nothing ever connects (eager mode + patched pings).
CELERY_BROKER_URL = "redis://broker.test.invalid:6379/0"
CELERY_RESULT_BACKEND = "redis://broker.test.invalid:6379/0"

# Isolated cache per run so throttling state never leaks between runs.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "nazbeen-forex-ai-tests",
    }
}

# High limits by default so unrelated tests never trip throttling;
# dedicated throttle tests override these via ``settings`` override.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {
        "anon": "10000/min",
        "user": "10000/min",
        "auth": "10000/min",
    },
}
