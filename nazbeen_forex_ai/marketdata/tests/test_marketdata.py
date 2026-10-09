"""Market data tests - run offline with mock provider."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from nazbeen_forex_ai.marketdata.mock import MockMarketDataProvider
from nazbeen_forex_ai.marketdata.providers import Candle


@pytest.fixture
def api() -> APIClient:
    from django.contrib.auth import get_user_model

    client = APIClient()
    u = get_user_model().objects.create_user("t1", password="T1est-2026!")
    client.force_authenticate(user=u)
    return client


@pytest.mark.django_db
def test_mock_provider_connects_and_reports_mock() -> None:
    p = MockMarketDataProvider()
    assert p.connect()
    assert p.is_connected()
    info = p.get_connection_info()
    assert info["mode"] == "mock"
    assert "mock" in info["label"].lower()


@pytest.mark.django_db
def test_mock_candles_have_utc_timestamps() -> None:
    p = MockMarketDataProvider()
    p.connect()
    candles = p.get_candles(symbol="EURUSD", timeframe="M15", count=10)
    assert len(candles) == 10
    for c in candles:
        assert isinstance(c, Candle)
        assert c.time.tzinfo == timezone.utc


@pytest.mark.django_db
def test_candle_normalization() -> None:
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    c = Candle(time=t, open=1.1, high=1.11, low=1.09, close=1.105)
    d = c.to_dict()
    assert d["time"].endswith("Z")


@pytest.mark.django_db
def test_mt5_status_endpoint_returns_mock_when_configured(api: APIClient) -> None:
    resp = api.get(reverse("marketdata:mt5_status"))
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert "connected" in data
    assert "mode" in data


@pytest.mark.django_db
def test_mt5_candles_endpoint_returns_mock_data(api: APIClient) -> None:
    resp = api.get(reverse("marketdata:mt5_candles") + "?symbol=EURUSD&timeframe=M15&count=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "EURUSD"
    assert data["timeframe"] == "M15"
    assert "candles" in data
    assert data["candles"][0]["time"].endswith("Z")
    assert "data_source" in data