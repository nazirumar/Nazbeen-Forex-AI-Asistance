"""Journal tests."""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.fixture
def api() -> APIClient:
    from django.contrib.auth import get_user_model

    client = APIClient()
    u = get_user_model().objects.create_user("j1", password="Jtest-2026!")
    client.force_authenticate(user=u)
    return client


@pytest.mark.django_db
def test_create_journal_entry(api: APIClient):
    resp = api.post(reverse("journal:entries"), {"symbol": "EURUSD", "outcome": "PENDING", "notes": "test"})
    assert resp.status_code == 201


@pytest.mark.django_db
def test_search_journal(api: APIClient):
    api.post(reverse("journal:entries"), {"symbol": "EURUSD", "notes": "setup A"})
    resp = api.get(reverse("journal:search") + "?q=setup")
    assert resp.status_code == 200
    assert len(resp.json()["entries"]) >= 1


@pytest.mark.django_db
def test_mentor_ask(api: APIClient):
    resp = api.post(reverse("journal:mentor_ask"), {"question": "Why WAIT?"})
    assert resp.status_code == 200
    assert "answer" in resp.json()
