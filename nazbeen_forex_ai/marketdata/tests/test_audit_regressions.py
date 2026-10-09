"""Migrated audit regression tests + test-isolation checks (Phase 11A).

Source: docs/audits/repro/test_audit_regressions.py (mock tick NameError,
unknown timeframe) and workstream 11A.4 (hermetic tests, no MT5 terminal).
"""

from __future__ import annotations

import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient

from nazbeen_forex_ai.marketdata.factory import get_market_data_provider
from nazbeen_forex_ai.marketdata.mock import MockMarketDataProvider


# --------------------------------------------------------------------------
# Migrated repro tests
# --------------------------------------------------------------------------

def test_bug_mock_tick_works_after_connect() -> None:
    """M-01: MockMarketDataProvider.get_tick raised NameError: utcnow.

    `utcnow` was never imported in mock.py (=> HTTP 500 in default mock mode).
    """
    p = MockMarketDataProvider()
    p.connect()
    tick = p.get_tick("EURUSD")
    assert tick["mode"] == "mock"


def test_bug_mock_rejects_unknown_timeframe() -> None:
    """M-02: unknown timeframe silently returned M15 candles mislabeled as requested.

    Actual before fix: 10 candles spaced 15 minutes for timeframe='M30'.
    """
    p = MockMarketDataProvider()
    p.connect()
    with pytest.raises(Exception):
        p.get_candles(symbol="EURUSD", timeframe="M30", count=10)


# --------------------------------------------------------------------------
# 11A.4 — test isolation
# --------------------------------------------------------------------------

def test_test_settings_force_mock_provider() -> None:
    assert settings.MT5_USE_MOCK is True


def test_factory_returns_mock_under_test_settings() -> None:
    provider = get_market_data_provider()
    assert isinstance(provider, MockMarketDataProvider)


def test_factory_ignores_contaminating_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """A local `.env` with MT5_USE_MOCK=false must not select a live provider.

    Test settings pin MT5_USE_MOCK=True, which wins over the env value, so the
    suite never depends on an installed MT5 terminal (audit CRIT-04).
    """
    monkeypatch.setenv("MT5_USE_MOCK", "false")
    provider = get_market_data_provider()
    assert isinstance(provider, MockMarketDataProvider)


@pytest.mark.django_db
def test_candles_endpoint_never_uses_live_provider(api_client_factory=None) -> None:
    from django.contrib.auth import get_user_model

    client = APIClient()
    u = get_user_model().objects.create_user("iso1", password="Iso1-2026!")
    client.force_authenticate(user=u)
    resp = client.get(reverse("marketdata:mt5_candles") + "?symbol=EURUSD&timeframe=M15&count=3")
    assert resp.status_code == 200
    assert resp.json()["data_source"] == "mock"
