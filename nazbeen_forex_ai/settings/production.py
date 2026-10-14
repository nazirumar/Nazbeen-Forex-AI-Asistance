"""Production settings — fail fast when security-critical config is missing."""

from __future__ import annotations

import django

from .base import *  # noqa: F403 — deliberate settings inheritance

DEBUG = False

if SECRET_KEY.startswith("insecure-"):  # noqa: F405
    raise django.core.exceptions.ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a real value in production. "
        "Generate one and store it in the environment, never in source code."
    )

# Behind a reverse proxy in production.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# TLS redirection / HSTS. HSTS is ON by default in production (audit L-04);
# set SECURE_HSTS_SECONDS=0 to disable it for a plain-HTTP compose stack, and
# SECURE_SSL_REDIRECT=true when TLS terminates in front of the app.
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)  # noqa: F405
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31536000)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(  # noqa: F405
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", SECURE_HSTS_SECONDS > 0
)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", SECURE_HSTS_SECONDS > 0)  # noqa: F405
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Celery must never run inline in production (tasks are real background work).
CELERY_TASK_ALWAYS_EAGER = False  # noqa: F405

# Rate limiting: DRF throttles (ResilientAnon/UserRateThrottle) are configured
# in base.py and apply here unchanged — see THROTTLE_RATE_* in .env.
