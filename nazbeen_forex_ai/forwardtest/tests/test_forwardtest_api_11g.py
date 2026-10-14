"""Phase 11G WS4: simulated forward-testing engine + API (§9/§10).

Covers config validation, the observation cycle (dedupe, checkpoint, outcome
tracking), Celery failure capture, the owner-scoped API, and typed journal
integration. Everything is asserted to be **simulated** — no orders anywhere.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from nazbeen_forex_ai.forwardtest import services
from nazbeen_forex_ai.forwardtest.models import ForwardTestObservation, ForwardTestRun
from nazbeen_forex_ai.forwardtest.tasks import observe_run_task

User = get_user_model()

RUN_LIST = "forwardtest:run-list"
RUN_DETAIL = "forwardtest:run-detail"
RUN_OBSERVE = "forwardtest:run-observe"
RUN_STOP = "forwardtest:run-stop"
RUN_OBS = "forwardtest:run-observations"
OBS_JOURNAL = "forwardtest:observation-journal"
CONFIG = "forwardtest:config"


def _bar(i: int, o: float, h: float, l: float, c: float) -> dict:  # noqa: E741
    t = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=15 * i)
    return {
        "time": t.isoformat().replace("+00:00", "Z"),
        "open": o,
        "high": h,
        "low": l,
        "close": c,
    }


def _flat(count: int, close: float = 1.1000) -> list[dict]:
    return [_bar(i, close, close + 0.0002, close - 0.0002, close) for i in range(count)]


@pytest.fixture
def user():
    return User.objects.create_user("fwd11g", password="Jtest-2026!")


@pytest.fixture
def other_user():
    return User.objects.create_user("fwd11g-other", password="Jtest-2026!")


@pytest.fixture
def api(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# --------------------------------------------------------------- config/levels
def test_validate_config_normalises_valid_input():
    cfg = services.validate_config({"symbol": "eurusd", "timeframe": "m15", "count": 200})
    assert cfg["symbol"] == "EURUSD"
    assert cfg["timeframe"] == "M15"
    assert cfg["count"] == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"timeframe": "D1"},
        {"count": 5},
        {"count": 999999},
        {"sl_pips": 0},
        {"tp_pips": -1},
    ],
)
def test_validate_config_rejects_invalid(payload):
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        services.validate_config(payload)


def test_levels_are_deterministic_and_bounded():
    cfg = {"sl_pips": 10.0, "tp_pips": 20.0}
    buy = services._levels("BUY", 1.1000, cfg)
    assert buy["sl"] == pytest.approx(1.0990)
    assert buy["tp"] == pytest.approx(1.1020)
    assert buy["rr"] == pytest.approx(2.0)
    sell = services._levels("SELL", 1.1000, cfg)
    assert sell["sl"] == pytest.approx(1.1010)
    assert sell["tp"] == pytest.approx(1.0980)
    wait = services._levels("WAIT", 1.1000, cfg)
    assert wait == {"entry": None, "sl": None, "tp": None, "rr": None}


# ------------------------------------------------------------- observation cycle
@pytest.mark.django_db
def test_observe_creates_simulated_observation_with_levels(user, monkeypatch):
    run = ForwardTestRun.objects.create(
        user=user, symbol="EURUSD", timeframe="M15",
        config=services.validate_config({}), status=ForwardTestRun.Status.ACTIVE,
    )
    monkeypatch.setattr(
        "nazbeen_forex_ai.forwardtest.services._fetch_window", lambda config: _flat(60)
    )
    monkeypatch.setattr(
        "nazbeen_forex_ai.forwardtest.services.evaluate_scenario",
        lambda *a, **k: {"decision": "BUY", "bias": {"M15": "BULLISH", "conflicts": []}, "evidence": {}},
    )
    created = services.observe_run(run)
    assert created == 1
    run.refresh_from_db()
    obs = run.observations.get()
    assert obs.decision == "BUY"
    assert obs.simulated is True
    assert obs.entry == pytest.approx(1.1000)
    assert obs.sl is not None and obs.tp is not None
    assert run.observations_count == 1
    assert run.last_observed_bar


@pytest.mark.django_db
def test_observe_is_idempotent_per_bar(user, monkeypatch):
    run = ForwardTestRun.objects.create(
        user=user, symbol="EURUSD", timeframe="M15",
        config=services.validate_config({}), status=ForwardTestRun.Status.ACTIVE,
    )
    data = _flat(60)
    monkeypatch.setattr("nazbeen_forex_ai.forwardtest.services._fetch_window", lambda config: list(data))
    monkeypatch.setattr(
        "nazbeen_forex_ai.forwardtest.services.evaluate_scenario",
        lambda *a, **k: {"decision": "WAIT", "bias": {"M15": "NEUTRAL", "conflicts": []}, "evidence": {}},
    )
    assert services.observe_run(run) == 1
    assert services.observe_run(run) == 0  # same latest bar → deduped
    assert run.observations.count() == 1


@pytest.mark.django_db
def test_observe_tracks_outcome_on_later_bars(user, monkeypatch):
    run = ForwardTestRun.objects.create(
        user=user, symbol="EURUSD", timeframe="M15",
        config=services.validate_config({}), status=ForwardTestRun.Status.ACTIVE,
    )
    data = _flat(60, close=1.1000)
    monkeypatch.setattr("nazbeen_forex_ai.forwardtest.services._fetch_window", lambda config: list(data))
    monkeypatch.setattr(
        "nazbeen_forex_ai.forwardtest.services.evaluate_scenario",
        lambda *a, **k: {"decision": "BUY", "bias": {"M15": "BULLISH", "conflicts": []}, "evidence": {}},
    )
    services.observe_run(run)
    first = run.observations.get()

    # Extend with a bar that reaches the target (tp = 1.1020).
    extended = data + [_bar(60, 1.1000, 1.1030, 1.1005, 1.1025)]
    monkeypatch.setattr("nazbeen_forex_ai.forwardtest.services._fetch_window", lambda config: list(extended))
    services.observe_run(run)

    first.refresh_from_db()
    assert first.outcome == ForwardTestObservation.Outcome.WIN
    assert first.outcome_r == pytest.approx(2.0)
    assert first.resolved_at is not None


@pytest.mark.django_db
def test_resolve_pending_is_stop_first_when_one_bar_touches_both(user):
    run = ForwardTestRun.objects.create(
        user=user, symbol="EURUSD", timeframe="M15",
        config=services.validate_config({}), status=ForwardTestRun.Status.ACTIVE,
    )
    obs = ForwardTestObservation.objects.create(
        run=run, bar_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        decision="BUY", entry=1.1000, sl=1.0990, tp=1.1020, rr=2.0,
    )
    both = [_bar(1, 1.1000, 1.1030, 1.0980, 1.1000)]  # hits tp AND sl in one bar
    services._resolve_pending(run, both)
    obs.refresh_from_db()
    assert obs.outcome == ForwardTestObservation.Outcome.LOSS
    assert obs.outcome_r == pytest.approx(-1.0)


@pytest.mark.django_db
def test_observe_run_task_records_safe_failure(user, monkeypatch):
    run = ForwardTestRun.objects.create(
        user=user, symbol="EURUSD", timeframe="M15",
        config=services.validate_config({}), status=ForwardTestRun.Status.ACTIVE,
    )

    def boom(_run):
        raise services.ForwardTestExecutionError("No market data.")

    monkeypatch.setattr("nazbeen_forex_ai.forwardtest.tasks.observe_run", boom)
    status_ = observe_run_task(str(run.id))
    run.refresh_from_db()
    assert status_ == "failed"
    assert run.status == ForwardTestRun.Status.FAILED
    assert "No market data" in run.error


@pytest.mark.django_db
def test_observe_run_task_missing_run_is_safe():
    import uuid as _uuid

    assert observe_run_task(str(_uuid.uuid4())) == "missing"


# ------------------------------------------------------------- journal linkage
@pytest.mark.django_db
def test_journalize_creates_typed_entry(user):
    run = ForwardTestRun.objects.create(
        user=user, symbol="EURUSD", timeframe="M15",
        config=services.validate_config({}), status=ForwardTestRun.Status.ACTIVE,
    )
    obs = ForwardTestObservation.objects.create(
        run=run, bar_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        decision="BUY", entry=1.1, sl=1.09, tp=1.12, rr=2.0,
    )
    entry = services.journalize_observation(user, obs)
    assert entry is not None
    assert entry.source == "forward_test"
    assert entry.source_ref == str(obs.id)
    assert "simulated" in entry.tags
    assert entry.scenario_decision == "BUY"


@pytest.mark.django_db
def test_journalize_rejects_other_user(user, other_user):
    run = ForwardTestRun.objects.create(
        user=user, symbol="EURUSD", timeframe="M15",
        config=services.validate_config({}), status=ForwardTestRun.Status.ACTIVE,
    )
    obs = ForwardTestObservation.objects.create(
        run=run, bar_time=datetime(2026, 1, 1, tzinfo=timezone.utc), decision="WAIT",
    )
    assert services.journalize_observation(other_user, obs) is None


# ------------------------------------------------------------------------- API
@pytest.mark.django_db
def test_create_run_requires_auth():
    resp = APIClient().post(reverse(RUN_LIST), {"symbol": "EURUSD"}, format="json")
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_create_list_detail_flow(api, user):
    resp = api.post(reverse(RUN_LIST), {"symbol": "eurusd", "timeframe": "M15"}, format="json")
    assert resp.status_code == 201
    run = resp.json()["run"]
    assert run["simulated"] is True
    assert run["status"] == "active"
    assert run["data_source"] == "mock"

    listing = api.get(reverse(RUN_LIST))
    assert listing.json()["count"] == 1

    detail = api.get(reverse(RUN_DETAIL, args=[run["id"]]))
    assert detail.status_code == 200
    assert detail.json()["run"]["id"] == run["id"]


@pytest.mark.django_db
def test_create_run_rejects_invalid_config(api):
    resp = api.post(reverse(RUN_LIST), {"count": 3}, format="json")
    assert resp.status_code == 400
    assert resp.json()["error"] == "Invalid configuration"


@pytest.mark.django_db
def test_runs_are_isolated_between_users(api, other_user):
    run = ForwardTestRun.objects.create(
        user=other_user, symbol="EURUSD", timeframe="M15",
        config=services.validate_config({}), status=ForwardTestRun.Status.ACTIVE,
    )
    assert api.get(reverse(RUN_DETAIL, args=[str(run.id)])).status_code == 404
    assert api.post(reverse(RUN_OBSERVE, args=[str(run.id)])).status_code == 404


@pytest.mark.django_db
def test_observe_endpoint_records_and_lists_observations(api, user):
    run = ForwardTestRun.objects.create(
        user=user, symbol="EURUSD", timeframe="M15",
        config=services.validate_config({}), status=ForwardTestRun.Status.ACTIVE,
    )
    resp = api.post(reverse(RUN_OBSERVE, args=[str(run.id)]))
    assert resp.status_code == 202

    obs = api.get(reverse(RUN_OBS, args=[str(run.id)]))
    assert obs.status_code == 200
    rows = obs.json()["observations"]
    assert len(rows) >= 1
    assert rows[0]["decision"] in ("BUY", "SELL", "WAIT")
    assert rows[0]["simulated"] is True


@pytest.mark.django_db
def test_observe_stopped_run_conflicts(api, user):
    run = ForwardTestRun.objects.create(
        user=user, symbol="EURUSD", timeframe="M15",
        config=services.validate_config({}), status=ForwardTestRun.Status.STOPPED,
    )
    assert api.post(reverse(RUN_OBSERVE, args=[str(run.id)])).status_code == 409


@pytest.mark.django_db
def test_stop_run(api, user):
    run = ForwardTestRun.objects.create(
        user=user, symbol="EURUSD", timeframe="M15",
        config=services.validate_config({}), status=ForwardTestRun.Status.ACTIVE,
    )
    resp = api.post(reverse(RUN_STOP, args=[str(run.id)]))
    assert resp.status_code == 200
    assert resp.json()["run"]["status"] == "stopped"


@pytest.mark.django_db
def test_observation_journal_endpoint(api, user):
    run = ForwardTestRun.objects.create(
        user=user, symbol="EURUSD", timeframe="M15",
        config=services.validate_config({}), status=ForwardTestRun.Status.ACTIVE,
    )
    obs = ForwardTestObservation.objects.create(
        run=run, bar_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        decision="SELL", entry=1.1, sl=1.11, tp=1.08, rr=3.0,
    )
    resp = api.post(reverse(OBS_JOURNAL, args=[str(obs.id)]))
    assert resp.status_code == 201
    assert resp.json()["source"] == "forward_test"


@pytest.mark.django_db
def test_config_endpoint(api):
    resp = api.get(reverse(CONFIG))
    assert resp.status_code == 200
    body = resp.json()
    assert body["defaults"]["timeframe"] == "M15"
    assert body["limits"]["max_active_runs"] == services.MAX_ACTIVE_RUNS


@pytest.mark.django_db
def test_active_run_cap(api):
    for _ in range(services.MAX_ACTIVE_RUNS):
        assert api.post(reverse(RUN_LIST), {"symbol": "EURUSD"}, format="json").status_code == 201
    resp = api.post(reverse(RUN_LIST), {"symbol": "EURUSD"}, format="json")
    assert resp.status_code == 429
