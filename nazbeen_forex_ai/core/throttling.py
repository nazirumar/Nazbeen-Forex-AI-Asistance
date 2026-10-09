"""Rate-limit throttles that degrade gracefully when the cache backend is down.

DRF stores throttle counters in the Django cache. When Redis is configured but
unreachable, an unhandled ``ConnectionError`` from the redis client escapes
``allow_request`` and turns *every* throttled request into a 500 — including
registration and login (discovered during Phase 1 smoke testing, because test
settings use LocMemCache and therefore never exercised the outage path).

These subclasses catch cache failures, log a warning and allow the request, so
a broker outage degrades rate limiting (silently loses it) instead of taking
the whole API down. See ADR-008 in ``docs/DECISIONS.md``.
"""

from __future__ import annotations

import logging

from rest_framework.throttling import AnonRateThrottle as _AnonRateThrottle
from rest_framework.throttling import ScopedRateThrottle as _ScopedRateThrottle
from rest_framework.throttling import UserRateThrottle as _UserRateThrottle

logger = logging.getLogger(__name__)


class _ResilientMixin:
    """Allow the request when the throttling cache backend is unavailable."""

    def allow_request(self, request, view) -> bool:
        try:
            return super().allow_request(request, view)  # type: ignore[misc]
        except Exception:  # noqa: BLE001 — a cache outage must never 500
            logger.warning(
                "Rate-limiting cache unavailable — allowing request "
                "(rate limiting lost while the backend is down)",
                exc_info=True,
            )
            return True


class ResilientAnonRateThrottle(_ResilientMixin, _AnonRateThrottle):
    """Anonymous-user throttle that survives a cache/broker outage."""


class ResilientUserRateThrottle(_ResilientMixin, _UserRateThrottle):
    """Authenticated-user throttle that survives a cache/broker outage."""


class ResilientScopedRateThrottle(_ResilientMixin, _ScopedRateThrottle):
    """View-scoped throttle (e.g. the ``auth`` scope on login/register) that
    survives a cache/broker outage."""