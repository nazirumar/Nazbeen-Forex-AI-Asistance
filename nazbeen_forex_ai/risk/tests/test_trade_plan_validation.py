"""Trade-plan request validation tests (Phase 11C — audits M-05/L-02, P1.6).

Contract:
- Malformed input (NaN/inf/non-numeric/out-of-bounds/unknown bias) returns
  **400** with safe field-level messages — never a 500, never a BUY.
- Unexpected internal failures return a generic 500; exception text (which may
  contain provider/database details) never reaches the client.
- Valid input keeps answering 200 with the scenario decision (WAIT when the
  plan is incomplete or inconsistent — ordering is the engine's job).
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.fixture
def api() -> APIClient:
    client = APIClient()
    get_user_model().objects.create_user("riskval", password="Risk1-2026!")
    client.force_authenticate(user=get_user_model().objects.get(username="riskval"))
    return client


def _post(api: APIClient, payload: dict):
    return api.post(reverse("risk:trade_plan"), payload, format="json")


VALID_PLAN = {
    "bias": "bullish",
    "entry": 1.1000,
    "sl": 1.0990,
    "tp": 1.1020,
    "spread_pips": 0.5,
    "symbol": "EURUSD",
    "account_balance": 10000.0,
    "risk_percent": 1.0,
    "max_spread_pips": 2.0,
    "min_rr": 1.0,
}


# ---------------------------------------------------------------------------
# Valid input still works
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_valid_plan_returns_200(api: APIClient) -> None:
    resp = _post(api, dict(VALID_PLAN))
    assert resp.status_code == 200
    assert resp.json()["decision"] in ("BUY", "SELL", "WAIT")


@pytest.mark.django_db
def test_incomplete_plan_answers_wait_not_error(api: APIClient) -> None:
    resp = _post(api, {"bias": "bullish", "account_balance": 10000.0})
    assert resp.status_code == 200
    assert resp.json()["decision"] == "WAIT"


# ---------------------------------------------------------------------------
# M-05/P1.6: strict input validation → 400, never 500
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@pytest.mark.parametrize(
    "field,value",
    [
        ("entry", "abc"),
        ("entry", -1.1000),
        ("risk_percent", "abc"),
        ("risk_percent", -1.0),          # negative risk → never a BUY
        ("risk_percent", 50.0),          # above the sanity cap
        ("account_balance", 0.0),
        ("min_rr", -0.5),
        ("max_spread_pips", -1.0),
        ("bias", "sideways"),
        ("symbol", "EUR USD; DROP"),
    ],
)
def test_invalid_fields_return_400(api: APIClient, field, value) -> None:
    payload = dict(VALID_PLAN)
    payload[field] = value
    resp = _post(api, payload)
    assert resp.status_code == 400, f"{field}={value!r} must be rejected"
    body = resp.json()
    assert body["decision"] == "WAIT"
    assert body["error"] == "Invalid trade plan input"
    assert body["details"], "safe field-level detail must be present"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "body",
    [
        # Non-finite literals can only arrive as raw JSON — the DRF test
        # client (like a strict encoder) refuses to serialize them, but a real
        # HTTP client can post them exactly like this. They must be rejected
        # with 400 — by the JSON parser or by the serializer — never a 500.
        '{"bias":"bullish","account_balance":10000,"entry":NaN}',
        '{"bias":"bullish","account_balance":10000,"sl":NaN}',
        '{"bias":"bullish","account_balance":10000,"tp":Infinity}',
        '{"bias":"bullish","account_balance":Infinity}',
        '{"bias":"bullish","account_balance":10000,"risk_percent":NaN}',
        '{"bias":"bullish","account_balance":10000,"risk_percent":-Infinity}',
    ],
)
def test_nonfinite_json_bodies_return_400(api: APIClient, body: str) -> None:
    resp = api.generic(
        "POST", reverse("risk:trade_plan"), data=body, content_type="application/json"
    )
    assert resp.status_code == 400, f"must reject non-finite input: {body}"
    payload = resp.json()
    assert isinstance(payload, dict), "a JSON error payload, never an HTML 500 page"
    assert "Traceback" not in resp.content.decode()


def test_serializer_rejects_nonfinite_values_directly() -> None:
    """Defense in depth: even if a parser ever lets NaN through, the
    serializer itself refuses non-finite numbers before any engine call."""
    from django.core.exceptions import ValidationError

    from nazbeen_forex_ai.risk.serializers import validate_trade_plan_request

    for field, value in [
        ("entry", float("nan")),
        ("sl", float("inf")),
        ("tp", float("-inf")),
        ("risk_percent", float("nan")),
        ("account_balance", float("inf")),
        ("spread_pips", float("nan")),
    ]:
        payload = {"bias": "bullish", field: value}
        with pytest.raises(ValidationError, match="finite"):
            validate_trade_plan_request(payload)


@pytest.mark.django_db
def test_non_object_body_returns_400(api: APIClient) -> None:
    resp = api.post(reverse("risk:trade_plan"), [1, 2, 3], format="json")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# L-02: internal exception text never leaks
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_internal_failure_returns_generic_500(api: APIClient, monkeypatch) -> None:
    import nazbeen_forex_ai.risk.views as risk_views

    def boom(payload):
        raise RuntimeError("DB-PASSWORD-LEAK-XYZ")

    monkeypatch.setattr(risk_views, "create_trade_plan", boom)
    resp = _post(api, dict(VALID_PLAN))
    assert resp.status_code == 500
    body = resp.content.decode()
    assert "DB-PASSWORD-LEAK" not in body, "exception text leaked to the client"
    assert resp.json()["decision"] == "WAIT"
    assert resp.json()["error"] == "Internal error while evaluating the trade plan"
