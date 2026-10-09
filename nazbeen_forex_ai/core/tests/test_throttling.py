"""Tests for resilient rate limiting (ADR-008).

These exercise the outage path that plain DRF throttles get wrong: when Redis is
configured but unreachable, throttled endpoints (register/login) must degrade —
never return 500.
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.throttling import SimpleRateThrottle

VALID_PASSWORD = "S3cure-Phr4se-2026!"


class FailingCache:
    """Mimics a configured-but-unreachable Redis cache backend."""

    def get(self, *args, **kwargs):
        raise ConnectionError("Error 10061 connecting to redis:6379")

    def add(self, *args, **kwargs):
        raise ConnectionError("Error 10061 connecting to redis:6379")

    def incr(self, *args, **kwargs):
        raise ConnectionError("Error 10061 connecting to redis:6379")

    def expire(self, *args, **kwargs):
        raise ConnectionError("Error 10061 connecting to redis:6379")

    def set(self, *args, **kwargs):
        raise ConnectionError("Error 10061 connecting to redis:6379")


@pytest.fixture
def api():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.mark.django_db
def test_register_degrades_gracefully_when_throttle_cache_down(api, monkeypatch) -> None:
    """With the cache backend down, registration must still succeed (no 500)."""
    monkeypatch.setattr(SimpleRateThrottle, "cache", FailingCache())

    response = api.post(
        reverse("accounts:register"),
        {"username": "resilient", "email": "r@example.com", "password": VALID_PASSWORD},
    )

    assert response.status_code == 201
    assert response.json()["token"]


@pytest.mark.django_db
def test_login_degrades_gracefully_when_throttle_cache_down(api, monkeypatch) -> None:
    monkeypatch.setattr(SimpleRateThrottle, "cache", FailingCache())

    from django.contrib.auth import get_user_model

    get_user_model().objects.create_user("resilient", password=VALID_PASSWORD)

    response = api.post(
        reverse("accounts:login"),
        {"username": "resilient", "password": VALID_PASSWORD},
    )

    assert response.status_code == 200
    assert response.json()["token"]


@pytest.mark.django_db
def test_rate_limit_still_enforced_when_cache_is_healthy(api, monkeypatch) -> None:
    """With a working cache, exceeding the auth rate must return 429."""
    from django.contrib.auth import get_user_model
    from django.core.cache import cache

    get_user_model().objects.create_user("carol", password=VALID_PASSWORD)
    payload = {"username": "carol", "password": VALID_PASSWORD}

    # THROTTLE_RATES is a class attribute bound at import time, so it is set
    # directly instead of via override_settings.
    monkeypatch.setattr(
        SimpleRateThrottle,
        "THROTTLE_RATES",
        {"anon": "10000/min", "user": "10000/min", "auth": "1/min"},
    )
    cache.clear()  # LocMemCache persists across tests — start clean.

    first = api.post(reverse("accounts:login"), payload)
    second = api.post(reverse("accounts:login"), payload)

    assert first.status_code == 200
    assert second.status_code == 429