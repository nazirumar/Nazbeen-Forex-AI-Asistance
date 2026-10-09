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
