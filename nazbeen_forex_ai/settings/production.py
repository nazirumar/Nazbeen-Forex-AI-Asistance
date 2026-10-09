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

# Behind a reverse proxy in production; kept minimal until Phase 10.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
