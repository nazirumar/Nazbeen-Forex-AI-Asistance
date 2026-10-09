"""Health-check endpoints.

Liveness/readiness probes for operators (see ``docs/API.md``). Exposes no
secrets and no market data.

Checks:
- ``database`` — round-trip query against the configured database.
- ``cache`` — set/get against the configured Django cache (Redis when configured).
- ``celery`` — broker reachability (skipped when no broker is configured, and
  skipped when the broker is unreachable only in the sense of reporting
  ``unavailable`` so the caller sees the truth).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

_CACHE_KEY = "health:probe"
_CACHE_PROBE_VALUE = "ok"


def check_database() -> str:
    """Return ``"ok"`` when a database round-trip succeeds, else ``"fail"``."""
    try:
        connection.ensure_connection()
    except Exception:  # noqa: BLE001 — any driver error means the check failed
        logger.exception("Health check: database connection failed")
        return "fail"
    return "ok"


def check_cache() -> str:
    """Return ``"ok"`` when a cache write/read round-trip succeeds."""
    try:
        cache.set(_CACHE_KEY, _CACHE_PROBE_VALUE, timeout=10)
        if cache.get(_CACHE_KEY) != _CACHE_PROBE_VALUE:
            return "fail"
    except Exception:  # noqa: BLE001
        logger.exception("Health check: cache round-trip failed")
        return "fail"
    return "ok"


def check_celery() -> str:
    """Report broker status without blocking the response.

    Returns ``"ok"`` when a broker is configured and accepts a connection,
    ``"unconfigured"`` when no broker is set (dev with eager tasks), or
    ``"fail"`` when configured but unreachable. Never raises.
    """
    broker_url = settings.CELERY_BROKER_URL
    if not broker_url:
        return "unconfigured"
    if settings.CELERY_TASK_ALWAYS_EAGER:
        return "eager"
    try:
        import redis as redis_lib

        with redis_lib.Redis.from_url(broker_url, socket_connect_timeout=1) as client:
            client.ping()
    except Exception:  # noqa: BLE001 — report, don't crash the probe
        logger.warning("Health check: celery broker unreachable", exc_info=True)
        return "fail"
    return "ok"


class HealthView(APIView):
    """GET /api/health/ — application health with per-dependency checks."""

    authentication_classes: list = []
    permission_classes: list = []
    throttle_classes: list = []  # probes must never be throttled

    def get(self, request) -> Response:
        checks = {
            "database": check_database(),
            "cache": check_cache(),
            "celery": check_celery(),
        }
        # "unconfigured"/"eager" are truthful states, not failures.
        healthy = all(result in {"ok", "unconfigured", "eager"} for result in checks.values())
        payload = {
            "status": "ok" if healthy else "degraded",
            "service": "nazbeen-forex-ai",
            "version": settings.APP_VERSION,
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "checks": checks,
        }
        http_status = (
            status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return Response(payload, status=http_status)
