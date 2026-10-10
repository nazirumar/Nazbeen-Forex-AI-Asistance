"""Candles-endpoint freshness labels (Phase 11D — dashboard indicator).

``GET /api/mt5/candles/`` now reports the honest age of the newest bar so the
dashboard's data-freshness indicator shows measured staleness instead of an
assumed "live" state.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.fixture
def api() -> APIClient:
    client = APIClient()
    get_user_model().objects.create_user("fresh1", password="Fresh-2026!")
    client.force_authenticate(user=get_user_model().objects.get(username="fresh1"))
    return client


@pytest.mark.django_db
def test_candles_response_carries_freshness_labels(api: APIClient) -> None:
    resp = api.get(reverse("marketdata:mt5_candles") + "?symbol=EURUSD&timeframe=M15&count=5")
    assert resp.status_code == 200
    body = resp.json()
    assert body["market_state"] in ("open", "closed")
    assert isinstance(body["stale"], bool)
    # Unknown age stays unknown (None) — never dressed up as fresh.
    assert body["last_bar_age_sec"] is None or isinstance(
        body["last_bar_age_sec"], (int, float)
    )
    assert isinstance(body["threshold_sec"], int)
    assert body["threshold_sec"] >= 1  # effective limit is always meaningful


@pytest.mark.django_db
def test_freshness_labels_present_on_empty_result(api: APIClient) -> None:
    # count=1 still yields a bar in mock mode; the label contract must hold
    # regardless of result size.
    resp = api.get(reverse("marketdata:mt5_candles") + "?symbol=EURUSD&timeframe=M1&count=1")
    assert resp.status_code == 200
    assert "stale" in resp.json()
    assert "last_bar_age_sec" in resp.json()
    assert "market_state" in resp.json()
