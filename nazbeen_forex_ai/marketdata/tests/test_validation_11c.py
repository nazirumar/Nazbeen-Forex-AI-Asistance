"""API input validation, error redaction, and freshness tests (Phase 11C).

Covers audits M-03 (bounded/numeric ``count`` → 400, not 500), M-04 (correct
provider-mode label on the error path), L-02 (no exception text leaked to
clients), and H-09 helpers (staleness + market-closure detection).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from nazbeen_forex_ai.marketdata.freshness import (
    assess_staleness,
    bar_age_seconds,
    is_market_closed,
    market_state,
)
from nazbeen_forex_ai.marketdata.mock import MockMarketDataProvider
from nazbeen_forex_ai.marketdata.mt5_connector import MT5MarketDataProvider
from nazbeen_forex_ai.marketdata.providers import MarketDataProviderError


@pytest.fixture
def api() -> APIClient:
    client = APIClient()
    get_user_model().objects.create_user("val1", password="Val1-2026!")
    client.force_authenticate(user=get_user_model().objects.get(username="val1"))
    return client


# ---------------------------------------------------------------------------
# M-03: strict candles-parameter validation → 400, never 500
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@pytest.mark.parametrize(
    "query",
    [
        "?symbol=EURUSD&timeframe=M15&count=abc",
        "?symbol=EURUSD&timeframe=M15&count=0",
        "?symbol=EURUSD&timeframe=M15&count=-5",
        "?symbol=EURUSD&timeframe=M15&count=99999",
        "?symbol=EURUSD&timeframe=M15&count=1.5",
        "?symbol=EURUSD&timeframe=M30",
        "?symbol=EUR;DROP TABLE&timeframe=M15",
        "?symbol=EURUSD&timeframe=M15&start=not-a-date",
    ],
)
def test_invalid_candle_params_return_400(api: APIClient, query: str) -> None:
    resp = api.get(reverse("marketdata:mt5_candles") + query)
    assert resp.status_code == 400, f"{query} should be rejected, got {resp.status_code}"
    assert resp.json()["error"] == "Invalid request"


@pytest.mark.django_db
@pytest.mark.parametrize("query", [
    "?symbol=EURUSD&timeframe=M15&count=5",
    "?symbol=EURUSD&timeframe=M15",
    "?symbol=eurusd&timeframe=M1&count=1",
    "?symbol=EURUSD&timeframe=M15&count=5000",
    "?symbol=EURUSD&timeframe=M15&start=2026-01-01T00:00:00Z&count=5",
])
def test_valid_candle_params_still_work(api: APIClient, query: str) -> None:
    resp = api.get(reverse("marketdata:mt5_candles") + query)
    assert resp.status_code == 200
    assert resp.json()["data_source"] == "mock"


@pytest.mark.django_db
def test_invalid_tick_symbol_returns_400(api: APIClient) -> None:
    resp = api.get(reverse("marketdata:mt5_tick") + "?symbol=%3Cscript%3E")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# L-02 + M-04: generic client errors, correct mode label, detail to logs
# ---------------------------------------------------------------------------

class _ExplodingProvider(MockMarketDataProvider):
    """A provider whose failure text must never reach the client."""

    def connect(self) -> bool:
        raise MarketDataProviderError("SECRET-DETAIL-DB-PASSWORD-XYZ")


@pytest.mark.django_db
def test_provider_error_text_is_never_leaked(api: APIClient, monkeypatch) -> None:
    from nazbeen_forex_ai.marketdata import views as md_views

    monkeypatch.setattr(md_views, "get_market_data_provider", lambda: _ExplodingProvider())
    for url in ("marketdata:mt5_candles", "marketdata:mt5_status", "marketdata:mt5_symbols"):
        resp = api.get(reverse(url) + "?symbol=EURUSD&timeframe=M15&count=5")
        assert resp.status_code == 503
        body = resp.content.decode()
        assert "SECRET-DETAIL" not in body, f"exception text leaked via {url}"
        assert resp.json()["error"] == md_views.GENERIC_PROVIDER_ERROR


@pytest.mark.django_db
def test_error_path_mode_label_is_correct_mock(api: APIClient, monkeypatch) -> None:
    from nazbeen_forex_ai.marketdata import views as md_views

    monkeypatch.setattr(md_views, "get_market_data_provider", lambda: _ExplodingProvider())
    resp = api.get(reverse("marketdata:mt5_status"))
    assert resp.status_code == 503
    assert resp.json()["mode"] == "mock", "M-04: mock provider must be labeled mock"


@pytest.mark.django_db
def test_error_path_mode_label_is_correct_mt5(api: APIClient, monkeypatch) -> None:
    from nazbeen_forex_ai.marketdata import views as md_views
    from nazbeen_forex_ai.marketdata import mt5_connector

    # Hermetic: force the "no module" path regardless of any local terminal
    # installation. The label must still honestly report "mt5" (audit M-04:
    # the old expression was inverted).
    monkeypatch.setattr(mt5_connector, "mt5", None)
    monkeypatch.setattr(md_views, "get_market_data_provider", lambda: MT5MarketDataProvider())
    resp = api.get(reverse("marketdata:mt5_status"))
    assert resp.status_code == 503
    assert resp.json()["mode"] == "mt5"


@pytest.mark.django_db
def test_status_reports_market_state(api: APIClient) -> None:
    resp = api.get(reverse("marketdata:mt5_status"))
    assert resp.status_code == 200
    assert resp.json()["market_state"] in ("open", "closed")


# ---------------------------------------------------------------------------
# H-09 helpers: staleness and market-closure detection (pure functions)
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)  # a Wednesday, noon UTC


def test_bar_age_seconds_parses_iso_and_datetime() -> None:
    assert bar_age_seconds(_NOW - timedelta(seconds=90), _NOW) == pytest.approx(90.0)
    assert bar_age_seconds((_NOW - timedelta(minutes=5)).isoformat(), _NOW) == pytest.approx(300.0)
    assert bar_age_seconds(None, _NOW) is None
    assert bar_age_seconds("garbage", _NOW) is None


def test_fresh_data_is_not_stale() -> None:
    fresh = assess_staleness(_NOW - timedelta(minutes=10), "M15", now=_NOW, threshold_sec=900)
    assert fresh["stale"] is False
    assert fresh["last_bar_age_sec"] == pytest.approx(600.0)


def test_old_data_is_stale() -> None:
    old = assess_staleness(_NOW - timedelta(hours=3), "M15", now=_NOW, threshold_sec=900)
    assert old["stale"] is True


def test_staleness_threshold_scales_with_timeframe() -> None:
    # A 40-minute-old H1 bar is still the forming/recent bar (1.5×3600s grace),
    # not stale; the same age for M15 is stale.
    age = timedelta(minutes=40)
    assert assess_staleness(_NOW - age, "H1", now=_NOW, threshold_sec=900)["stale"] is False
    assert assess_staleness(_NOW - age, "M15", now=_NOW, threshold_sec=900)["stale"] is True


def test_market_closed_windows() -> None:
    # Friday 21:00+ → closed.
    assert is_market_closed(datetime(2026, 10, 9, 22, 0, tzinfo=timezone.utc)) is True
    # All Saturday → closed.
    assert is_market_closed(datetime(2026, 10, 10, 3, 0, tzinfo=timezone.utc)) is True
    # Sunday before 21:00 → closed.
    assert is_market_closed(datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)) is True
    # Sunday 21:00+ → open.
    assert is_market_closed(datetime(2026, 10, 11, 22, 0, tzinfo=timezone.utc)) is False
    # Friday 20:59 → open; Monday noon → open.
    assert is_market_closed(datetime(2026, 10, 9, 20, 59, tzinfo=timezone.utc)) is False
    assert is_market_closed(_NOW) is False
    assert market_state(_NOW) == "open"
