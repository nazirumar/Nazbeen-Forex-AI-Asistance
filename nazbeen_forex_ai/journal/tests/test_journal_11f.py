"""Phase 11F journal tests: spec §3.H fields, CRUD, performance, export.

Covers audit M-15 / RECOMMENDED_FIXES P2.5.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from nazbeen_forex_ai.analysis.models import ScreenshotAnalysis
from nazbeen_forex_ai.journal.models import JournalEntry

User = get_user_model()


@pytest.fixture
def user():
    return User.objects.create_user("j11f", password="Jtest-2026!")


@pytest.fixture
def other_user():
    return User.objects.create_user("j11f-other", password="Jtest-2026!")


@pytest.fixture
def api(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


ENTRIES_URL = "journal:entries"
DETAIL_URL = "journal:entry_detail"
PERF_URL = "journal:performance"
EXPORT_URL = "journal:export"


# --------------------------------------------------------------------- create
@pytest.mark.django_db
def test_create_returns_full_spec_fields(api, user):
    payload = {
        "symbol": "EURUSD",
        "timeframe": "M15",
        "scenario_decision": "BUY",
        "entry": 1.0850,
        "sl": 1.0820,
        "tp": 1.0910,
        "rr": 2.0,
        "outcome": "PENDING",
        "notes": "spec fields",
        "tags": ["london"],
        "estimated_probability": 0.61,
        "model_version": "vision=a/reasoning=b",
        "strategy_version": "v3",
        "market_snapshot": {"source": "mock"},
        "detected_structures": {"bias_mtf": "bullish"},
    }
    resp = api.post(reverse(ENTRIES_URL), payload, format="json")
    assert resp.status_code == 201
    body = resp.json()
    for key in (
        "id", "symbol", "timeframe", "analysis_session_id", "screenshot_analysis_id",
        "analysis_timestamp", "market_snapshot", "detected_structures", "model_version",
        "strategy_version", "scenario_decision", "entry", "sl", "tp", "rr",
        "estimated_probability", "outcome", "pnl", "notes", "tags", "metrics",
        "created_at", "updated_at",
    ):
        assert key in body, f"missing spec field: {key}"
    assert body["symbol"] == "EURUSD"
    assert body["estimated_probability"] == 0.61
    assert body["market_snapshot"] == {"source": "mock"}
    assert body["detected_structures"] == {"bias_mtf": "bullish"}


@pytest.mark.django_db
def test_unset_spec_fields_are_null_not_invented(api):
    resp = api.post(reverse(ENTRIES_URL), {"symbol": "EURUSD"}, format="json")
    assert resp.status_code == 201
    body = resp.json()
    # Nothing was recorded → nothing is fabricated (audit M-08).
    assert body["estimated_probability"] is None
    assert body["entry"] is None
    assert body["sl"] is None
    assert body["tp"] is None
    assert body["rr"] is None
    assert body["pnl"] is None
    assert body["market_snapshot"] == {}
    assert body["detected_structures"] == {}
    assert body["outcome"] == "PENDING"


@pytest.mark.django_db
def test_create_links_analysis_and_derives_context(api, user):
    analysis = ScreenshotAnalysis.objects.create(
        user=user,
        symbol="GBPUSD",
        timeframe="H1",
        structured_output={
            "source": "mock",
            "data_synchronized": True,
            "uses_mtf_data": True,
            "model": "vision=x/reasoning=y",
            "deterministic_signals": {"bias_mtf": "bearish", "fvg_count": 2},
            "analysis_timestamp": "2026-10-14T00:00:00Z",
        },
        metadata={"model": "meta-model"},
    )
    resp = api.post(
        reverse(ENTRIES_URL),
        {"analysis_session_id": str(analysis.id), "outcome": "PENDING"},
        format="json",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["screenshot_analysis_id"] == str(analysis.id)
    assert body["symbol"] == "GBPUSD"
    assert body["timeframe"] == "H1"
    assert body["model_version"] == "vision=x/reasoning=y"
    assert body["detected_structures"] == {"bias_mtf": "bearish", "fvg_count": 2}
    assert body["market_snapshot"]["source"] == "mock"
    assert body["analysis_timestamp"] is not None


@pytest.mark.django_db
def test_create_cannot_link_another_users_analysis(api, other_user):
    analysis = ScreenshotAnalysis.objects.create(user=other_user, symbol="USDJPY", timeframe="M5")
    resp = api.post(
        reverse(ENTRIES_URL),
        {"analysis_session_id": str(analysis.id), "symbol": "EURUSD"},
        format="json",
    )
    assert resp.status_code == 201
    body = resp.json()
    # Not linked: another user's analysis id is opaque.
    assert body["screenshot_analysis_id"] is None
    assert body["symbol"] == "EURUSD"


@pytest.mark.django_db
def test_create_invalid_outcome_400(api):
    resp = api.post(reverse(ENTRIES_URL), {"outcome": "MAYBE"}, format="json")
    assert resp.status_code == 400
    assert "outcome" in str(resp.json()["details"])


@pytest.mark.django_db
def test_create_non_finite_number_400(api):
    resp = api.post(reverse(ENTRIES_URL), {"entry": "inf"}, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_create_bad_numeric_400(api):
    resp = api.post(reverse(ENTRIES_URL), {"entry": "not-a-number"}, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_create_bad_tags_type_400(api):
    resp = api.post(reverse(ENTRIES_URL), {"tags": {"a": 1}}, format="json")
    assert resp.status_code == 400


# --------------------------------------------------------------------- detail
@pytest.mark.django_db
def test_retrieve_own_entry(api, user):
    entry = JournalEntry.objects.create(user=user, symbol="EURUSD", outcome="WIN")
    resp = api.get(reverse(DETAIL_URL, args=[entry.id]))
    assert resp.status_code == 200
    assert resp.json()["id"] == str(entry.id)


@pytest.mark.django_db
def test_retrieve_other_users_entry_404(api, other_user):
    entry = JournalEntry.objects.create(user=other_user, symbol="EURUSD")
    resp = api.get(reverse(DETAIL_URL, args=[entry.id]))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_patch_updates_only_supplied_fields(api, user):
    entry = JournalEntry.objects.create(user=user, symbol="EURUSD", outcome="PENDING", notes="keep")
    resp = api.patch(
        reverse(DETAIL_URL, args=[entry.id]),
        {"outcome": "WIN", "pnl": 120.5},
        format="json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "WIN"
    assert body["pnl"] == 120.5
    assert body["symbol"] == "EURUSD"
    assert body["notes"] == "keep"


@pytest.mark.django_db
def test_patch_other_users_entry_404(api, other_user):
    entry = JournalEntry.objects.create(user=other_user, symbol="EURUSD")
    resp = api.patch(reverse(DETAIL_URL, args=[entry.id]), {"outcome": "WIN"}, format="json")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_patch_invalid_outcome_400(api, user):
    entry = JournalEntry.objects.create(user=user, symbol="EURUSD")
    resp = api.patch(reverse(DETAIL_URL, args=[entry.id]), {"outcome": "NOPE"}, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_delete_entry(api, user):
    entry = JournalEntry.objects.create(user=user, symbol="EURUSD")
    resp = api.delete(reverse(DETAIL_URL, args=[entry.id]))
    assert resp.status_code == 204
    assert not JournalEntry.objects.filter(id=entry.id).exists()
    assert api.get(reverse(DETAIL_URL, args=[entry.id])).status_code == 404


@pytest.mark.django_db
def test_delete_other_users_entry_404(api, other_user):
    entry = JournalEntry.objects.create(user=other_user, symbol="EURUSD")
    resp = api.delete(reverse(DETAIL_URL, args=[entry.id]))
    assert resp.status_code == 404
    assert JournalEntry.objects.filter(id=entry.id).exists()


# --------------------------------------------------------------------- search
@pytest.mark.django_db
def test_list_filters_by_symbol_and_outcome(api, user):
    JournalEntry.objects.create(user=user, symbol="EURUSD", outcome="WIN", notes="alpha")
    JournalEntry.objects.create(user=user, symbol="GBPUSD", outcome="LOSS", notes="beta")
    by_symbol = api.get(reverse(ENTRIES_URL) + "?symbol=EURUSD").json()
    assert by_symbol["count"] == 1
    assert by_symbol["entries"][0]["symbol"] == "EURUSD"
    by_outcome = api.get(reverse(ENTRIES_URL) + "?outcome=LOSS").json()
    assert by_outcome["count"] == 1
    assert by_outcome["entries"][0]["outcome"] == "LOSS"


@pytest.mark.django_db
def test_list_bad_limit_400(api):
    assert api.get(reverse(ENTRIES_URL) + "?limit=abc").status_code == 400


# ---------------------------------------------------------------- performance
@pytest.mark.django_db
def test_performance_empty_is_honest(api):
    body = api.get(reverse(PERF_URL)).json()
    assert body["total_entries"] == 0
    assert body["win_rate"] is None
    assert body["average_rr"] is None
    assert body["total_pnl"] is None
    assert body["expectancy"] is None
    assert body["profit_factor"] is None
    assert body["max_drawdown"] is None
    assert body["pnl_sample"] == 0


@pytest.mark.django_db
def test_performance_math(api, user):
    base = timezone.now() - timedelta(hours=3)
    JournalEntry.objects.create(user=user, symbol="EURUSD", outcome="WIN", rr=2.0, pnl=100.0, created_at=base)
    JournalEntry.objects.create(user=user, symbol="EURUSD", outcome="LOSS", rr=1.0, pnl=-50.0, created_at=base + timedelta(hours=1))
    JournalEntry.objects.create(user=user, symbol="EURUSD", outcome="WIN", rr=3.0, pnl=100.0, created_at=base + timedelta(hours=2))
    JournalEntry.objects.create(user=user, symbol="EURUSD", outcome="PENDING", created_at=base + timedelta(hours=3))

    body = api.get(reverse(PERF_URL)).json()
    assert body["total_entries"] == 4
    assert body["outcomes"] == {"WIN": 2, "LOSS": 1, "BE": 0, "PENDING": 1}
    assert body["closed"] == 3
    assert body["open"] == 1
    assert body["win_rate"] == pytest.approx(2 / 3)
    assert body["average_rr"] == pytest.approx(2.0)
    assert body["total_pnl"] == pytest.approx(150.0)
    assert body["expectancy"] == pytest.approx(50.0)
    assert body["profit_factor"] == pytest.approx(4.0)
    assert body["max_drawdown"] == pytest.approx(50.0)
    assert body["pnl_sample"] == 3
    assert body["rr_sample"] == 3


@pytest.mark.django_db
def test_performance_without_pnl_is_null(api, user):
    JournalEntry.objects.create(user=user, symbol="EURUSD", outcome="WIN", rr=2.0)
    JournalEntry.objects.create(user=user, symbol="EURUSD", outcome="LOSS", rr=1.0)
    body = api.get(reverse(PERF_URL)).json()
    assert body["win_rate"] == pytest.approx(0.5)
    assert body["average_rr"] == pytest.approx(1.5)
    # No P&L was ever recorded → those statistics are None, not zero.
    assert body["total_pnl"] is None
    assert body["expectancy"] is None
    assert body["profit_factor"] is None
    assert body["max_drawdown"] is None
    assert body["pnl_sample"] == 0


@pytest.mark.django_db
def test_performance_scoped_to_user(api, user, other_user):
    JournalEntry.objects.create(user=other_user, symbol="EURUSD", outcome="WIN", pnl=999.0)
    body = api.get(reverse(PERF_URL)).json()
    assert body["total_entries"] == 0
    assert body["total_pnl"] is None


# --------------------------------------------------------------------- export
@pytest.mark.django_db
def test_export_json(api, user):
    JournalEntry.objects.create(user=user, symbol="EURUSD", outcome="WIN", rr=2.0, pnl=10.0)
    resp = api.get(reverse(EXPORT_URL) + "?format=json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["entries"][0]["symbol"] == "EURUSD"


@pytest.mark.django_db
def test_export_csv(api, user):
    JournalEntry.objects.create(user=user, symbol="EURUSD", outcome="WIN")
    resp = api.get(reverse(EXPORT_URL) + "?format=csv")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    text = resp.content.decode("utf-8")
    assert text.splitlines()[0].startswith("id,created_at,symbol")
    assert "EURUSD" in text


@pytest.mark.django_db
def test_export_invalid_format_400(api):
    assert api.get(reverse(EXPORT_URL) + "?format=xml").status_code == 400


@pytest.mark.django_db
def test_export_scoped_to_user(api, user, other_user):
    JournalEntry.objects.create(user=other_user, symbol="USDJPY", outcome="WIN")
    body = api.get(reverse(EXPORT_URL) + "?format=json").json()
    assert body["count"] == 0


# --------------------------------------------------------------- unknown UUID
@pytest.mark.django_db
def test_detail_unknown_uuid_404(api):
    assert api.get(reverse(DETAIL_URL, args=[uuid.uuid4()])).status_code == 404
