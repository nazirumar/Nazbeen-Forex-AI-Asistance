"""Tests for GET /api/health/ (docs/API.md)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_health_returns_ok_with_checks(client) -> None:
    response = client.get(reverse("core:health"))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "nazbeen-forex-ai"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["cache"] == "ok"
    # Test settings run Celery eagerly — a truthful state, not a failure.
    assert body["checks"]["celery"] in {"eager", "unconfigured", "ok"}
    # UTC ISO-8601 timestamp with Z suffix.
    assert body["time"].endswith("Z")
    assert body["version"]


def test_health_reports_degraded_when_database_down(client) -> None:
    with patch(
        "nazbeen_forex_ai.core.views.check_database", return_value="fail"
    ):
        response = client.get(reverse("core:health"))

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"] == "fail"


def test_health_reports_degraded_when_cache_down(client) -> None:
    with patch(
        "nazbeen_forex_ai.core.views.check_cache", return_value="fail"
    ):
        response = client.get(reverse("core:health"))

    assert response.status_code == 503
    assert response.json()["checks"]["cache"] == "fail"


def test_health_reports_fail_when_broker_unreachable(client) -> None:
    with patch(
        "nazbeen_forex_ai.core.views.check_celery", return_value="fail"
    ):
        response = client.get(reverse("core:health"))

    assert response.status_code == 503
    assert response.json()["checks"]["celery"] == "fail"


@pytest.mark.django_db
def test_health_requires_no_authentication(client) -> None:
    response = client.get(reverse("core:health"))
    # Anonymous request must never be redirected to a login page.
    assert response.status_code in (200, 503)
    assert response["Content-Type"].startswith("application/json")
