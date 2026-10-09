"""End-to-end workflow test: register → analyze → plan → journal → mentor.

Offline (mock providers), covering the major user journey documented in
`docs/PHASE_REPORTS/PHASE_09.md` §4. No MT5 terminal, Redis or LLM required.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.fixture
def api() -> APIClient:
    """DRF test client (JSON by default) — the plain Django `client` fixture
    posts multipart, which the auth endpoints reject with 415."""
    return APIClient()


@pytest.mark.django_db
def test_full_user_workflow(api: APIClient) -> None:
    # 1. Register
    resp = api.post(
        reverse("accounts:register"),
        {"username": "e2e_user", "password": "E2e-Strong-Pass-2026!", "email": "e2e@example.com"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    token = resp.json()["token"]
    api.credentials(HTTP_AUTHORIZATION=f"Token {token}")

    # 2. Who am I
    resp = api.get(reverse("accounts:me"))
    assert resp.status_code == 200
    assert resp.json()["username"] == "e2e_user"

    # 3. MT5 status (mock provider — labeled, never silently live)
    resp = api.get(reverse("marketdata:mt5_status"))
    assert resp.status_code in (200, 503)
    assert "mode" in resp.json()

    # 4. Candles are source-labeled with UTC timestamps
    resp = api.get(reverse("marketdata:mt5_candles") + "?symbol=EURUSD&timeframe=M15&count=5")
    assert resp.status_code == 200
    body = resp.json()
    # Tests are hermetic: the mock provider must be selected (Phase 11A).
    assert body["data_source"] == "mock"
    assert body["candles"][0]["time"].endswith("Z")

    # 5. Upload a screenshot and get a structured analysis
    # Strict validation (Phase 11A): uploads must be real decodable images.
    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (8, 8), "steelblue").save(buf, format="PNG")
    image = SimpleUploadedFile("chart.png", buf.getvalue(), "image/png")
    resp = api.post(
        reverse("analysis:upload"),
        {"image": (image, "chart.png"), "symbol": "EURUSD", "timeframe": "M15"},
        format="multipart",
    )
    assert resp.status_code == 201, resp.content
    result = resp.json()["result"]
    analysis_id = resp.json()["analysis_id"]
    assert result["decision"] in ("BUY", "SELL", "WAIT")

    # 6. Retrieve the saved analysis (owner-only)
    resp = api.get(reverse("analysis:detail", kwargs={"analysis_id": analysis_id}))
    assert resp.status_code == 200

    # 7. Trade plan (analysis-only; invalid input must yield WAIT)
    resp = api.post(
        reverse("risk:trade_plan"),
        {"bias": "BULLISH", "entry": 1.1000, "sl": 1.0990, "tp": 1.1020,
         "spread_pips": 0.5, "symbol": "EURUSD", "account_balance": 10000, "min_rr": 1.0},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["decision"] in ("BUY", "SELL", "WAIT")

    # 8. Journal entry + search
    resp = api.post(
        reverse("journal:entries"),
        {"symbol": "EURUSD", "scenario_decision": "WAIT", "notes": "e2e setup note"},
        format="json",
    )
    assert resp.status_code == 201
    resp = api.get(reverse("journal:search") + "?q=e2e")
    assert resp.status_code == 200
    assert len(resp.json()["entries"]) >= 1

    # 9. Mentor question answered with context
    resp = api.post(reverse("journal:mentor_ask"), {"question": "Why WAIT?"}, format="json")
    assert resp.status_code == 200
    assert "answer" in resp.json()

    # 10. Logout revokes the token
    resp = api.post(reverse("accounts:logout"))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_workflow_is_isolated_between_users(api: APIClient) -> None:
    # User A creates a journal entry
    resp = api.post(
        reverse("accounts:register"),
        {"username": "iso_a", "password": "IsoA-Strong-2026!", "email": "a@example.com"},
        format="json",
    )
    token = resp.json()["token"]
    api.credentials(HTTP_AUTHORIZATION=f"Token {token}")
    api.post(reverse("journal:entries"), {"symbol": "EURUSD", "notes": "private-A"}, format="json")

    # User B must not see it
    resp = api.post(
        reverse("accounts:register"),
        {"username": "iso_b", "password": "IsoB-Strong-2026!", "email": "b@example.com"},
        format="json",
    )
    token_b = resp.json()["token"]
    api.credentials(HTTP_AUTHORIZATION=f"Token {token_b}")
    resp = api.get(reverse("journal:search") + "?q=private")
    assert resp.status_code == 200
    assert resp.json()["entries"] == []
