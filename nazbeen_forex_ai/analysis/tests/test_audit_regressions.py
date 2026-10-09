"""Migrated audit regression tests — screenshot upload security (Phase 11A).

Source: docs/audits/repro/test_audit_regressions.py (H-01/H-02: view swallowed
validation errors; validators ended in `pass`). Strict validation must return
safe 400s for non-image content and oversized files.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.fixture
def api() -> APIClient:
    client = APIClient()
    get_user_model().objects.create_user("repro_up", password="Repro-2026!")
    client.force_authenticate(user=get_user_model().objects.get(username="repro_up"))
    return client


@pytest.mark.django_db
def test_bug_upload_rejects_non_image_content(api: APIClient) -> None:
    """H-02: view swallowed ValidationError 'to be permissive for tests'.

    Upload of b'not an image' named x.png with Content-Type image/png must be 400.
    Actual before fix: 201 (validation dead; content never verified).
    """
    resp = api.post(
        reverse("analysis:upload"),
        {"image": (BytesIO(b"not an image at all"), "x.png")},
        format="multipart",
    )
    assert resp.status_code == 400, f"expected 400, got {resp.status_code}"


@pytest.mark.django_db
def test_bug_upload_rejects_oversized_file(api: APIClient) -> None:
    """H-01: the 5MB limit existed but was bypassed.

    Actual before fix: a 6MB payload was accepted (201); correct: 400.
    """
    payload = BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * (6 * 1024 * 1024))
    resp = api.post(
        reverse("analysis:upload"),
        {"image": (payload, "big.png")},
        format="multipart",
    )
    assert resp.status_code == 400, f"expected 400 for 6MB file, got {resp.status_code}"


@pytest.mark.django_db
def test_upload_rejects_disallowed_extension(api: APIClient) -> None:
    from django.core.files.uploadedfile import SimpleUploadedFile

    svg = SimpleUploadedFile("icon.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>", "image/svg+xml")
    resp = api.post(reverse("analysis:upload"), {"image": svg}, format="multipart")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_upload_rejects_image_with_wrong_content_type(api: APIClient) -> None:
    """A real PNG mislabeled with a non-image content type is rejected."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    png = SimpleUploadedFile("test.png", b"\x89PNG\r\n\x1a\n000", "text/plain")
    resp = api.post(reverse("analysis:upload"), {"image": png}, format="multipart")
    assert resp.status_code == 400
