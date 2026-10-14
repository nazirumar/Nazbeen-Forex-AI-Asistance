"""Phase 11G WS6: journal source typing (§10).

Journal rows carry a typed ``source`` so manual entries, screenshot analyses,
backtests and forward tests are never conflated. ``source_ref`` links back to the
originating row when one exists.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from nazbeen_forex_ai.journal.models import JournalEntry

User = get_user_model()

ENTRIES_URL = "journal:entries"
EXPORT_URL = "journal:export"


@pytest.fixture
def user():
    return User.objects.create_user("j11gsrc", password="Jtest-2026!")


@pytest.fixture
def api(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_default_source_is_manual(api, user):
    resp = api.post(reverse(ENTRIES_URL), {"symbol": "EURUSD", "outcome": "PENDING"}, format="json")
    assert resp.status_code == 201
    assert resp.json()["source"] == "manual"
    assert JournalEntry.objects.get(user=user).source == "manual"


@pytest.mark.django_db
def test_create_with_backtest_source_persists_and_serializes(api):
    payload = {
        "symbol": "GBPUSD",
        "outcome": "WIN",
        "source": "backtest",
        "source_ref": "run-123",
    }
    resp = api.post(reverse(ENTRIES_URL), payload, format="json")
    assert resp.status_code == 201
    body = resp.json()
    assert body["source"] == "backtest"
    assert body["source_ref"] == "run-123"


@pytest.mark.django_db
def test_invalid_source_is_rejected(api):
    resp = api.post(
        reverse(ENTRIES_URL),
        {"symbol": "EURUSD", "source": "telepathy"},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "Invalid journal entry"
    assert JournalEntry.objects.count() == 0


@pytest.mark.django_db
def test_list_can_filter_by_source(api, user):
    JournalEntry.objects.create(user=user, symbol="EURUSD", source="backtest", source_ref="r1")
    JournalEntry.objects.create(user=user, symbol="EURUSD", source="forward_test", source_ref="f1")
    JournalEntry.objects.create(user=user, symbol="EURUSD", source="manual")

    resp = api.get(reverse(ENTRIES_URL) + "?source=forward_test")
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["source"] == "forward_test"


@pytest.mark.django_db
def test_export_includes_source(api, user):
    JournalEntry.objects.create(user=user, symbol="EURUSD", source="forward_test", source_ref="f9")
    resp = api.get(reverse(EXPORT_URL) + "?format=json")
    assert resp.status_code == 200
    row = resp.json()["entries"][0]
    assert row["source"] == "forward_test"
    assert row["source_ref"] == "f9"
