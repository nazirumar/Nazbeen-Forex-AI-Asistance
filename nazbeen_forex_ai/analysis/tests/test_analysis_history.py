"""Analysis-history list endpoint tests (Phase 11D).

The history table and the "reopen" flow read from ``GET /api/analysis/``.
Ownership isolation is the critical property: a caller must only ever see
their own analyses (cross-user leak = fail).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from nazbeen_forex_ai.analysis.models import ScreenshotAnalysis

User = get_user_model()


def _make(user, symbol: str, created_at: datetime, decision: str = "WAIT") -> ScreenshotAnalysis:
    return ScreenshotAnalysis.objects.create(
        user=user,
        symbol=symbol,
        timeframe="M15",
        ai_summary=f"summary for {symbol}",
        structured_output={"decision": decision, "source": "mock", "summary": "schema summary"},
        created_at=created_at,
    )


def _url() -> str:
    return reverse("analysis:list")


@pytest.mark.django_db
def test_history_requires_authentication() -> None:
    resp = APIClient().get(_url())
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_returns_own_analyses_newest_first_with_real_fields() -> None:
    user = User.objects.create_user("hist1", password="Hist-2026!")
    client = APIClient()
    client.force_authenticate(user=user)
    older = _make(user, "EURUSD", datetime(2026, 10, 8, 10, 0, tzinfo=timezone.utc), decision="BUY")
    newer = _make(user, "GBPUSD", datetime(2026, 10, 9, 10, 0, tzinfo=timezone.utc), decision="WAIT")

    resp = client.get(_url())
    assert resp.status_code == 200
    rows = resp.json()["analyses"]
    assert [r["id"] for r in rows] == [str(newer.id), str(older.id)]

    row = rows[0]
    assert row["symbol"] == "GBPUSD"
    assert row["timeframe"] == "M15"
    assert row["decision"] == "WAIT"          # real field from structured_output
    assert row["data_source"] == "mock"       # real field, honest labeling
    assert row["summary"] == "summary for GBPUSD"
    assert row["created_at"].endswith("Z")    # UTC ISO-8601 convention
    assert row["screenshot_stored"] is False  # no file persisted in this test


@pytest.mark.django_db
def test_cross_user_isolation() -> None:
    a = User.objects.create_user("iso_a", password="IsoA-2026!")
    b = User.objects.create_user("iso_b", password="IsoB-2026!")
    _make(a, "EURUSD", datetime(2026, 10, 9, 9, 0, tzinfo=timezone.utc))
    only_b = _make(b, "GBPUSD", datetime(2026, 10, 9, 9, 30, tzinfo=timezone.utc))

    client_a = APIClient()
    client_a.force_authenticate(user=a)
    rows = client_a.get(_url()).json()["analyses"]
    ids = {r["id"] for r in rows}
    assert str(only_b.id) not in ids, "another user's analysis must never appear"
    assert all(r["symbol"] == "EURUSD" for r in rows)

    client_b = APIClient()
    client_b.force_authenticate(user=b)
    rows_b = client_b.get(_url()).json()["analyses"]
    assert [r["id"] for r in rows_b] == [str(only_b.id)]
