"""Phase 11F: read-only backtest-history surfacing, scoped to the owner."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from nazbeen_forex_ai.backtesting.models import BacktestRun

User = get_user_model()

RUNS_URL = "backtesting:runs"


@pytest.fixture
def user():
    return User.objects.create_user("bt11f", password="Jtest-2026!")


@pytest.fixture
def other_user():
    return User.objects.create_user("bt11f-other", password="Jtest-2026!")


@pytest.fixture
def api(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_backtest_history_returns_only_own_runs(api, user, other_user):
    mine = BacktestRun.objects.create(
        user=user, symbol="EURUSD", timeframe="M15", total_trades=10, win_rate=60.0
    )
    BacktestRun.objects.create(user=other_user, symbol="GBPUSD", timeframe="H1")
    BacktestRun.objects.create(user=None, symbol="USDJPY", timeframe="H4")

    resp = api.get(reverse(RUNS_URL))
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["runs"][0]["id"] == str(mine.id)
    assert body["runs"][0]["symbol"] == "EURUSD"
    assert body["runs"][0]["win_rate"] == 60.0


@pytest.mark.django_db
def test_backtest_history_requires_auth():
    client = APIClient()
    resp = client.get(reverse(RUNS_URL))
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_backtest_history_empty(api):
    resp = api.get(reverse(RUNS_URL))
    assert resp.status_code == 200
    assert resp.json() == {"count": 0, "runs": []}
