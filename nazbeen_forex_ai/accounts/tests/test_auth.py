"""Tests for authentication endpoints (register/login/logout/me)."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()

VALID_PASSWORD = "S3cure-Phr4se-2026!"


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.mark.django_db
def test_register_creates_user_token_and_profile(api: APIClient) -> None:
    response = api.post(
        reverse("accounts:register"),
        {"username": "trader1", "email": "t1@example.com", "password": VALID_PASSWORD},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["token"]
    assert body["user"]["username"] == "trader1"
    assert body["user"]["profile"]["display_timezone"] == "UTC"
    # Password must never appear in any response.
    assert "password" not in str(response.content)
    assert User.objects.filter(username="trader1").exists()


@pytest.mark.django_db
def test_register_rejects_weak_password(api: APIClient) -> None:
    response = api.post(
        reverse("accounts:register"),
        {"username": "weak", "email": "w@example.com", "password": "123"},
    )
    assert response.status_code == 400
    assert not User.objects.filter(username="weak").exists()


@pytest.mark.django_db
def test_register_rejects_duplicate_username(api: APIClient) -> None:
    User.objects.create_user("dup", password=VALID_PASSWORD)
    response = api.post(
        reverse("accounts:register"),
        {"username": "dup", "email": "d@example.com", "password": VALID_PASSWORD},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_login_success_returns_token(api: APIClient) -> None:
    User.objects.create_user("alice", password=VALID_PASSWORD)
    response = api.post(
        reverse("accounts:login"),
        {"username": "alice", "password": VALID_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["user"]["username"] == "alice"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "username,password",
    [("alice", "wrong-password"), ("nobody", VALID_PASSWORD)],
)
def test_login_rejects_bad_credentials_without_leaking(
    api: APIClient, username: str, password: str
) -> None:
    User.objects.create_user("alice", password=VALID_PASSWORD)
    response = api.post(
        reverse("accounts:login"),
        {"username": username, "password": password},
    )
    assert response.status_code == 400
    # Uniform message — never reveals whether the account exists.
    assert response.json() == {"detail": "Invalid credentials."}


@pytest.mark.django_db
def test_me_requires_authentication(api: APIClient) -> None:
    response = api.get(reverse("accounts:me"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_me_returns_profile_for_token_holder(api: APIClient) -> None:
    User.objects.create_user("bob", password=VALID_PASSWORD)
    login = api.post(
        reverse("accounts:login"),
        {"username": "bob", "password": VALID_PASSWORD},
    )
    api.credentials(HTTP_AUTHORIZATION=f"Token {login.json()['token']}")

    response = api.get(reverse("accounts:me"))

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "bob"
    assert body["profile"]["display_timezone"] == "UTC"


@pytest.mark.django_db
def test_me_rejects_bad_token(api: APIClient) -> None:
    api.credentials(HTTP_AUTHORIZATION="Token not-a-real-token")
    response = api.get(reverse("accounts:me"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_logout_deletes_token_and_blocks_reuse(api: APIClient) -> None:
    User.objects.create_user("carol", password=VALID_PASSWORD)
    login = api.post(
        reverse("accounts:login"),
        {"username": "carol", "password": VALID_PASSWORD},
    )
    token = login.json()["token"]
    api.credentials(HTTP_AUTHORIZATION=f"Token {token}")

    logout = api.post(reverse("accounts:logout"))
    assert logout.status_code == 200

    # The same token must no longer authenticate.
    response = api.get(reverse("accounts:me"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_default_permission_is_denied_for_unknown_endpoints(api: APIClient) -> None:
    """Secure default: endpoints require auth unless explicitly public."""
    response = api.get("/api/definitely-not-a-route/")
    assert response.status_code == 404  # routing first…

    from nazbeen_forex_ai.settings.base import REST_FRAMEWORK

    assert REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] == [
        "rest_framework.permissions.IsAuthenticated"
    ]


@pytest.mark.django_db
def test_auth_endpoints_are_rate_limited(api: APIClient) -> None:
    """Login attempts use the tighter 'auth' throttle scope."""
    from django.test import override_settings
    from rest_framework.settings import api_settings
    from rest_framework.throttling import SimpleRateThrottle

    class _Probe(SimpleRateThrottle):
        scope = "auth"

    with override_settings():
        from django.conf import settings as dj_settings

        rates = dj_settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
        assert rates["auth"]  # auth scope configured

    # The view declares the scope so anon login attempts are throttled.
    from nazbeen_forex_ai.accounts.views import LoginView, RegisterView

    assert LoginView.throttle_scope == "auth"
    assert RegisterView.throttle_scope == "auth"
    assert _Probe.scope == "auth"
    assert api_settings.DEFAULT_THROTTLE_RATES.get("auth")
