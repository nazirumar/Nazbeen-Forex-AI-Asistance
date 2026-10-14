"""Phase 11G WS1: MT5 symbol-metadata endpoint (§2).

Metadata is only ever the provider's real values (mock values are explicitly
labelled ``source: mock``); a provider that cannot supply metadata yields **503**,
never a fabricated digits/point/tick value.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from nazbeen_forex_ai.marketdata.mock import MockMarketDataProvider
from nazbeen_forex_ai.marketdata.providers import MarketDataProvider, MarketDataProviderError

SYMBOL_INFO_URL = "marketdata:mt5_symbol_info"


@pytest.fixture
def api() -> APIClient:
    client = APIClient()
    user = get_user_model().objects.create_user("sym11g", password="Jtest-2026!")
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_symbol_info_requires_auth() -> None:
    resp = APIClient().get(reverse(SYMBOL_INFO_URL) + "?symbol=EURUSD")
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_symbol_info_returns_labelled_mock_metadata(api: APIClient) -> None:
    resp = api.get(reverse(SYMBOL_INFO_URL) + "?symbol=eurusd")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "EURUSD"
    assert data["source"] == "mock"
    assert data["data_source"] == "mock"
    assert data["digits"] == 5
    assert data["point"] > 0
    assert data["contract_size"] > 0


@pytest.mark.django_db
def test_symbol_info_rejects_invalid_symbol(api: APIClient) -> None:
    resp = api.get(reverse(SYMBOL_INFO_URL) + "?symbol=" + "x" * 33)
    assert resp.status_code == 400
    assert resp.json()["error"] == "Invalid request"


@pytest.mark.django_db
def test_symbol_info_provider_without_metadata_returns_503(api: APIClient, monkeypatch) -> None:
    class _NoMetaProvider(MarketDataProvider):
        def connect(self) -> bool:
            return True

        def is_connected(self) -> bool:
            return True

        def get_connection_info(self) -> dict:
            return {}

        def get_symbols(self, search=None):  # noqa: ANN001
            return []

        def get_candles(self, symbol, timeframe, start=None, count=None):  # noqa: ANN001
            return []

        def get_tick(self, symbol: str) -> dict:
            return {}

    monkeypatch.setattr(
        "nazbeen_forex_ai.marketdata.views.get_market_data_provider",
        lambda: _NoMetaProvider(),
    )
    resp = api.get(reverse(SYMBOL_INFO_URL) + "?symbol=EURUSD")
    assert resp.status_code == 503
    assert "unavailable" in resp.json()["error"].lower()


@pytest.mark.django_db
def test_mock_provider_symbol_info_is_consistent() -> None:
    provider = MockMarketDataProvider()
    provider.connect()
    info = provider.get_symbol_info("GBPUSD")
    assert info["symbol"] == "GBPUSD"
    assert info["currency_base"] == "GBP"
    assert info["currency_profit"] == "USD"
    assert info["source"] == "mock"
