"""Analysis tests - mock LLM, provider failures, safety checks."""

from __future__ import annotations

from django.urls import reverse
from rest_framework.test import APIClient
import pytest


@pytest.fixture
def api() -> APIClient:
    from django.contrib.auth import get_user_model

    client = APIClient()
    u = get_user_model().objects.create_user("a1", password="Atest-2026!")
    client.force_authenticate(user=u)
    return client


@pytest.mark.django_db
def test_upload_requires_auth(client: APIClient):
    client.logout()
    resp = client.post(reverse("analysis:upload"))
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_upload_no_file(api: APIClient):
    resp = api.post(reverse("analysis:upload"))
    assert resp.status_code == 400


@pytest.mark.django_db
def test_mock_llm_analysis_safe(api: APIClient):
    # create minimal fake png
    from io import BytesIO

    from django.core.files.uploadedfile import SimpleUploadedFile
    # use regular bytes - DRF will handle
    from io import BytesIO
    data = BytesIO(b"\x89PNG\r\n\x1a\n1234567890")
    # send as multipart with name
    resp = api.post(reverse("analysis:upload"), {"image": (data, "test.png")}, format="multipart")
    assert resp.status_code == 201
    res = resp.json()["result"]
    assert res["decision"] in ("BUY", "SELL", "WAIT")
    assert isinstance(res["disagreements"], list)
    assert isinstance(res["mtf_conflicts"], list)
    assert isinstance(res["uncertainty"], list)
    # AI must not fabricate prices when sync unknown? enforce
    assert res["data_synchronized"] is False or res["source"] in ("mock", "mt5")
    assert res["entry_levels"] == [] or isinstance(res["entry_levels"], list)


@pytest.mark.django_db
def test_structured_output_validates_schema(api: APIClient):
    from io import BytesIO

    data = BytesIO(b"\x89PNG\r\n\x1a\nTEST")
    data.name = "test.png"
    data.seek(0)
    resp = api.post(reverse("analysis:upload"), {"image": data}, format="multipart")
    assert resp.status_code == 201
    res = resp.json()["result"]
    # required keys
    for k in ["decision", "direction", "summary", "evidence", "disagreements"]:
        assert k in res


@pytest.mark.django_db
def test_provider_failure_handling(api: APIClient, monkeypatch):
    from nazbeen_forex_ai.analysis import services

    def bad_retrieve(*args, **kwargs):
        raise Exception("market data unavailable")

    monkeypatch.setattr(services.ScreenshotAnalysisService, "retrieve_market_data", bad_retrieve)
    from io import BytesIO

    data = BytesIO(b"\x89PNG\r\n\x1a\nBAD")
    data.name = "bad.png"
    data.seek(0)
    resp = api.post(reverse("analysis:upload"), {"image": data}, format="multipart")
    assert resp.status_code == 201  # safe response
    res = resp.json()["result"]
    assert res["decision"] == "WAIT"
    assert isinstance(res["errors"], list) or "uncertainty" in res
