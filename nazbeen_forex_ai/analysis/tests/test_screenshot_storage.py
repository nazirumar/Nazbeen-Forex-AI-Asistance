"""Screenshot persistence tests (Phase 11C — audit H-02).

Contract:
- The uploaded screenshot is written under MEDIA_ROOT/screenshots with a
  server-generated name; the record stores only the relative path.
- The retrieval endpoint is ownership-scoped (404 for everyone else) and
  refuses path-traversal payloads.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from nazbeen_forex_ai.analysis.storage import (
    resolve_screenshot_path,
    save_screenshot,
    screenshots_base_dir,
)


def _png_bytes(size: int = 8) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (size, size), "steelblue").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def api() -> APIClient:
    client = APIClient()
    get_user_model().objects.create_user("shot1", password="Shot1-2026!")
    client.force_authenticate(user=get_user_model().objects.get(username="shot1"))
    return client


@pytest.fixture(autouse=True)
def isolated_media(settings, tmp_path):
    """Persist test uploads into a per-test temp MEDIA_ROOT."""
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def _upload(client: APIClient, data: bytes, hints: dict | None = None):
    payload = {"image": SimpleUploadedFile("chart.png", data, "image/png")}
    if hints:
        payload.update(hints)
    return client.post(reverse("analysis:upload"), payload, format="multipart")


@pytest.mark.django_db
def test_upload_persists_screenshot_with_server_side_name(api: APIClient, isolated_media):
    original = _png_bytes()
    resp = _upload(api, original, {"symbol": "EURUSD", "timeframe": "M15"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["screenshot_stored"] is True

    from nazbeen_forex_ai.analysis.models import ScreenshotAnalysis

    record = ScreenshotAnalysis.objects.get(id=body["analysis_id"])
    assert record.image_path.startswith("screenshots/")
    # Server-generated name: never the client's filename.
    assert "chart.png" not in record.image_path
    stored = isolated_media / record.image_path
    assert stored.is_file()
    assert stored.read_bytes() == original


@pytest.mark.django_db
def test_screenshot_endpoint_returns_image_to_owner(api: APIClient, isolated_media):
    original = _png_bytes()
    resp = _upload(api, original, {"symbol": "EURUSD", "timeframe": "M15"})
    analysis_id = resp.json()["analysis_id"]

    shot = api.get(reverse("analysis:screenshot", args=[analysis_id]))
    assert shot.status_code == 200
    assert shot["Content-Type"] == "image/png"
    assert b"".join(shot.streaming_content) == original


@pytest.mark.django_db
def test_screenshot_endpoint_denies_other_users(api: APIClient):
    resp = _upload(api, _png_bytes(), {"symbol": "EURUSD", "timeframe": "M15"})
    analysis_id = resp.json()["analysis_id"]

    other = APIClient()
    get_user_model().objects.create_user("shot2", password="Shot2-2026!")
    other.force_authenticate(user=get_user_model().objects.get(username="shot2"))
    assert other.get(reverse("analysis:screenshot", args=[analysis_id])).status_code == 404
    # Detail view equally ownership-scoped.
    assert other.get(reverse("analysis:detail", args=[analysis_id])).status_code == 404


@pytest.mark.django_db
def test_screenshot_endpoint_requires_auth(client: APIClient):
    client.logout()
    resp = client.get(reverse("analysis:screenshot", args=["00000000-0000-0000-0000-000000000000"]))
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_screenshot_not_stored_returns_404(api: APIClient):
    from nazbeen_forex_ai.analysis.models import ScreenshotAnalysis

    user = get_user_model().objects.get(username="shot1")
    record = ScreenshotAnalysis.objects.create(user=user, image_path="")
    resp = api.get(reverse("analysis:screenshot", args=[record.id]))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_screenshot_path_traversal_is_refused(api: APIClient, isolated_media):
    from nazbeen_forex_ai.analysis.models import ScreenshotAnalysis

    user = get_user_model().objects.get(username="shot1")
    secret = isolated_media.parent / "secret.txt"
    secret.write_text("not-a-screenshot", encoding="utf-8")
    record = ScreenshotAnalysis.objects.create(
        user=user, image_path="../secret.txt"
    )
    resp = api.get(reverse("analysis:screenshot", args=[record.id]))
    assert resp.status_code == 404


def test_storage_helpers_refuse_traversal_and_absolute_paths(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    (tmp_path / "screenshots").mkdir()
    assert resolve_screenshot_path("") is None
    assert resolve_screenshot_path("../pyproject.toml") is None
    assert resolve_screenshot_path("..\\pyproject.toml") is None
    assert resolve_screenshot_path(str(tmp_path / "pyproject.toml")) is None


def test_save_screenshot_generates_uuid_names(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    rel = save_screenshot(b"\x89PNG-fake", "evil-name.exe")
    assert rel.startswith("screenshots/")
    assert rel.endswith(".png"), "non-image extension must be coerced to .png"
    assert "evil-name" not in rel
    stored = resolve_screenshot_path(rel)
    assert stored is not None and stored.is_file()
    with pytest.raises(ValueError):
        save_screenshot(b"", "empty.png")
    # Base dir is where the files live.
    assert screenshots_base_dir() == tmp_path / "screenshots"
