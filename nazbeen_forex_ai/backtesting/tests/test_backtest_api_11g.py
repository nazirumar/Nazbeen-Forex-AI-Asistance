"""Phase 11G: backtest execution + reporting API, metrics math and isolation.

All tests are hermetic: the market-data provider is the labelled mock adapter
(see ``settings.test``) and Celery runs eagerly, so runs complete inline.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient

from nazbeen_forex_ai.backtesting.engine import Trade, run_backtest, summarize_trades
from nazbeen_forex_ai.backtesting.models import BacktestRun
from nazbeen_forex_ai.backtesting.services import (
    _persist_trades,
    compute_lots,
    compute_metrics,
    equity_curve,
    execute_run,
    export_run,
    validate_config,
)
from nazbeen_forex_ai.backtesting.tasks import run_backtest_task
from nazbeen_forex_ai.backtesting.walkforward import walk_forward

User = get_user_model()

RUN_LIST = "backtesting:run-list"
RUN_DETAIL = "backtesting:run-detail"
RUN_TRADES = "backtesting:run-trades"
RUN_METRICS = "backtesting:run-metrics"
RUN_EQUITY = "backtesting:run-equity"
RUN_EXPORT = "backtesting:run-export"
CONFIG_URL = "backtesting:config"


# --- fixtures / helpers ----------------------------------------------------


def _t(entry_time, side, entry, sl, tp, result, pnl, exit_price):
    return Trade(
        entry_time=entry_time,
        exit_time=entry_time + timedelta(hours=1),
        side=side,
        entry=entry,
        sl=sl,
        tp=tp,
        lots=1.0,
        exit_price=exit_price,
        result=result,
        pnl=pnl,
    )


@pytest.fixture
def user():
    return User.objects.create_user("bt11g", password="Jtest-2026!")


@pytest.fixture
def other_user():
    return User.objects.create_user("bt11g-other", password="Jtest-2026!")


@pytest.fixture
def api(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _bar(minute: int, o: float, h: float, l: float, cl: float, day: int = 1) -> dict:
    ts = datetime(2026, 1, day, 0, 0, tzinfo=timezone.utc) + timedelta(minutes=minute)
    return {"time": ts.isoformat(), "open": o, "high": h, "low": l, "close": cl}


def _flat(count: int, day: int = 1) -> list[dict]:
    return [_bar(i, 1.1000, 1.1001, 1.0999, 1.1000, day) for i in range(count)]


# --- configuration validation ---------------------------------------------


def test_validate_config_normalises_valid_input():
    cfg = validate_config({"symbol": "eurusd", "timeframe": "m15", "count": 500})
    assert cfg["symbol"] == "EURUSD"
    assert cfg["timeframe"] == "M15"
    assert cfg["count"] == 500
    assert cfg["strategy_version"]


@pytest.mark.parametrize(
    "payload",
    [
        {"timeframe": "H4"},
        {"count": 5},
        {"initial_balance": 0},
        {"risk_pct": 0},
        {"risk_pct": 150},
        {"spread_pips": -1},
        {"sl_pips": 0},
        {"max_drawdown_pct": 200},
        {"end": "2026-01-01T00:00:00Z", "start": "2026-02-01T00:00:00Z"},
        {"walk_forward": True, "train_size": 0},
    ],
)
def test_validate_config_rejects_invalid(payload):
    with pytest.raises(ValidationError):
        validate_config(payload)


def test_compute_lots_risk_sizing():
    # 1% of 10000 = 100 risk; 10-pip stop, $10/pip per lot → 1.0 lot.
    lots = compute_lots({"initial_balance": 10000.0, "risk_pct": 1.0, "sl_pips": 10.0})
    assert lots == pytest.approx(1.0)


# --- metric mathematics ----------------------------------------------------


@pytest.mark.django_db
def test_compute_metrics_from_recorded_trades(user):
    base = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)
    result = summarize_trades(
        [
            _t(base, "LONG", 1.1000, 1.0990, 1.1020, "WIN", 200.0, 1.1020),
            _t(base + timedelta(hours=2), "SHORT", 1.1000, 1.1010, 1.0980, "LOSS", -100.0, 1.1010),
            _t(base + timedelta(hours=4), "LONG", 1.1000, 1.0990, 1.1020, "BREAK_EVEN", 0.0, 1.1000),
        ]
    )
    run = BacktestRun.objects.create(
        user=user,
        symbol="EURUSD",
        timeframe="M15",
        config={"initial_balance": 10000.0},
        status=BacktestRun.Status.RUNNING,
    )
    _persist_trades(run, result)
    metrics = compute_metrics(run, result, lots=1.0)

    assert metrics["sample_size"] == 3
    assert metrics["wins"] == 1 and metrics["losses"] == 1 and metrics["break_evens"] == 1
    assert metrics["win_rate"] == pytest.approx(33.3333, rel=1e-3)
    assert metrics["gross_profit"] == pytest.approx(200.0)
    assert metrics["gross_loss"] == pytest.approx(100.0)
    assert metrics["net_profit"] == pytest.approx(100.0)
    assert metrics["profit_factor"] == pytest.approx(2.0)
    assert metrics["expectancy"] == pytest.approx(33.3333, rel=1e-3)
    assert metrics["max_drawdown"] == pytest.approx(100.0)
    assert metrics["average_realized_r"] == pytest.approx(0.3333, rel=1e-3)
    assert metrics["max_consecutive_wins"] == 1
    assert metrics["max_consecutive_losses"] == 1
    assert metrics["by_session"]["london"]["trades"] == 2
    assert metrics["by_session"]["new_york"]["trades"] == 1
    assert metrics["by_setup_type"]["LONG"]["trades"] == 2
    assert metrics["assumptions"]["initial_balance"] == 10000.0


@pytest.mark.django_db
def test_metrics_are_null_when_not_computable(user):
    run = BacktestRun.objects.create(
        user=user, symbol="EURUSD", timeframe="M15", config={"initial_balance": 10000.0}
    )
    metrics = compute_metrics(run, summarize_trades([]), lots=1.0)
    assert metrics["sample_size"] == 0
    assert metrics["win_rate"] is None
    assert metrics["profit_factor"] is None
    assert metrics["expectancy"] is None
    assert metrics["average_realized_r"] is None


# --- engine portfolio stops ------------------------------------------------


def _two_trade_series(day: int = 1) -> list[dict]:
    """Bar 30 entry → SL loss; bar 50 entry → TP win (same UTC day)."""
    bars = _flat(31, day)  # indices 0..30 (entry bar 30)
    bars.append(_bar(31, 1.1000, 1.1005, 1.0989, 1.0995, day))  # first trade: SL
    bars.extend(_flat(18, day))  # indices 32..49
    # re-index filler times so the series stays strictly increasing
    for k, c in enumerate(bars[32:], start=32):
        c["time"] = (datetime(2026, 1, day, 0, 0, tzinfo=timezone.utc) + timedelta(minutes=k)).isoformat()
    bars.append(_bar(50, 1.1000, 1.1001, 1.0999, 1.1000, day))  # second entry bar
    bars.append(_bar(51, 1.1000, 1.1030, 1.0999, 1.1010, day))  # second trade: TP
    return bars


def _buy_at_30_and_50(window: list[dict]) -> str:
    return "BUY" if len(window) in (30, 50) else "WAIT"


def test_max_daily_loss_blocks_further_entries_that_day():
    candles = _two_trade_series()
    blocked = run_backtest(candles, strategy=_buy_at_30_and_50, min_bars=30, max_daily_loss=50.0)
    assert blocked.total_trades == 1
    assert blocked.trades[0].result == "LOSS"

    free = run_backtest(candles, strategy=_buy_at_30_and_50, min_bars=30)
    assert free.total_trades == 2


def test_max_drawdown_pct_stops_trading():
    candles = _two_trade_series()
    r = run_backtest(
        candles,
        strategy=_buy_at_30_and_50,
        min_bars=30,
        initial_balance=10000.0,
        max_drawdown_pct=0.5,  # 100 loss = 1% > 0.5% → stop after the first trade
    )
    assert r.total_trades == 1


def test_engine_stops_are_disabled_by_default():
    """Defaults (0) must not change the existing two-trade behaviour."""
    candles = _two_trade_series()
    r = run_backtest(candles, strategy=_buy_at_30_and_50, min_bars=30)
    assert r.total_trades == 2


def test_walk_forward_forwards_engine_kwargs():
    """Phase 11G: sizing/cost kwargs reach the out-of-sample windows."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = []
    for i in range(300):
        o = 1.1000 + 0.0001 * (i % 5)
        c = o + 0.0001
        candles.append(
            {
                "time": (base + timedelta(minutes=i)).isoformat(),
                "open": o,
                "high": max(o, c) + 0.0001,
                "low": min(o, c) - 0.0001,
                "close": c,
            }
        )

    def strat(window: list[dict]) -> str:
        return "BUY" if len(window) == 30 else "WAIT"

    wf = walk_forward(candles, train_size=100, test_size=50, step=50, strategy=strat, lots=2.0)
    assert wf.overall.total_trades >= 1
    assert all(t.lots == 2.0 for t in wf.overall.trades)


# --- execution service -----------------------------------------------------


@pytest.mark.django_db
def test_execute_run_with_insufficient_candles_fails_safely(user):
    run = BacktestRun.objects.create(
        user=user,
        symbol="EURUSD",
        timeframe="M15",
        config={"symbol": "EURUSD", "timeframe": "M15", "count": 5},
        status=BacktestRun.Status.QUEUED,
    )
    execute_run(run)
    run.refresh_from_db()
    assert run.status == BacktestRun.Status.FAILED
    assert run.error
    assert run.trades.count() == 0


@pytest.mark.django_db
def test_run_backtest_task_records_failure(user):
    run = BacktestRun.objects.create(
        user=user,
        symbol="EURUSD",
        timeframe="M15",
        config={"symbol": "EURUSD", "timeframe": "M15", "count": 5},
        status=BacktestRun.Status.QUEUED,
    )
    status_value = run_backtest_task(str(run.id))
    assert status_value == BacktestRun.Status.FAILED
    run.refresh_from_db()
    assert run.status == BacktestRun.Status.FAILED


@pytest.mark.django_db
def test_execute_run_completes_with_mock_provider(user):
    config = validate_config({"symbol": "EURUSD", "timeframe": "M15", "count": 300})
    run = BacktestRun.objects.create(
        user=user,
        symbol=config["symbol"],
        timeframe=config["timeframe"],
        config=config,
        status=BacktestRun.Status.QUEUED,
    )
    execute_run(run)
    run.refresh_from_db()
    assert run.status == BacktestRun.Status.COMPLETED
    assert run.finished_at is not None
    assert run.metrics["sample_size"] == run.trades.count()


# --- API: lifecycle, isolation, exports -----------------------------------


@pytest.mark.django_db
def test_create_run_requires_auth():
    client = APIClient()
    resp = client.post(reverse(RUN_LIST), {"symbol": "EURUSD"}, format="json")
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_create_run_executes_and_is_retrievable(api, user):
    resp = api.post(
        reverse(RUN_LIST), {"symbol": "EURUSD", "timeframe": "M15", "count": 300}, format="json"
    )
    assert resp.status_code == 202
    run_id = resp.json()["run"]["id"]
    assert BacktestRun.objects.get(pk=run_id).user_id == user.id

    detail = api.get(reverse(RUN_DETAIL, args=[run_id]))
    assert detail.status_code == 200
    assert detail.json()["run"]["id"] == run_id
    assert detail.json()["run"]["status"] in ("completed", "queued")


@pytest.mark.django_db
def test_create_run_rejects_invalid_config(api):
    resp = api.post(reverse(RUN_LIST), {"timeframe": "H4", "risk_pct": 500}, format="json")
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "Invalid configuration"
    assert body["details"]


@pytest.mark.django_db
def test_runs_are_isolated_between_users(api, user, other_user):
    mine = BacktestRun.objects.create(user=user, symbol="EURUSD", timeframe="M15")
    theirs = BacktestRun.objects.create(user=other_user, symbol="GBPUSD", timeframe="H1")

    listing = api.get(reverse(RUN_LIST)).json()
    assert listing["count"] == 1
    assert listing["runs"][0]["id"] == str(mine.id)

    # A cross-user id is a 404, never a disclosure.
    assert api.get(reverse(RUN_DETAIL, args=[str(theirs.id)])).status_code == 404
    assert api.get(reverse(RUN_TRADES, args=[str(theirs.id)])).status_code == 404
    assert api.get(reverse(RUN_METRICS, args=[str(theirs.id)])).status_code == 404
    assert api.get(reverse(RUN_EQUITY, args=[str(theirs.id)])).status_code == 404
    assert api.get(reverse(RUN_EXPORT, args=[str(theirs.id)])).status_code == 404


@pytest.mark.django_db
def test_metrics_trades_equity_and_export_endpoints(api, user):
    config = validate_config({"symbol": "EURUSD", "timeframe": "M15", "count": 300})
    run = BacktestRun.objects.create(user=user, symbol="EURUSD", timeframe="M15", config=config)
    execute_run(run)

    assert api.get(reverse(RUN_METRICS, args=[str(run.id)])).status_code == 200
    trades = api.get(reverse(RUN_TRADES, args=[str(run.id)]))
    assert trades.status_code == 200
    assert trades.json()["count"] == run.trades.count()

    equity = api.get(reverse(RUN_EQUITY, args=[str(run.id)])).json()["points"]
    assert equity and equity[0]["equity"] == 10000.0

    csv_resp = api.get(reverse(RUN_EXPORT, args=[str(run.id)]) + "?format=csv")
    assert csv_resp.status_code == 200
    assert csv_resp["Content-Type"].startswith("text/csv")

    json_resp = api.get(reverse(RUN_EXPORT, args=[str(run.id)]) + "?format=json")
    assert json_resp.status_code == 200
    assert "trades" in json_resp.json()

    bad = api.get(reverse(RUN_EXPORT, args=[str(run.id)]) + "?format=xml")
    assert bad.status_code == 400


@pytest.mark.django_db
def test_config_endpoint(api):
    resp = api.get(reverse(CONFIG_URL))
    assert resp.status_code == 200
    body = resp.json()
    assert "defaults" in body and "limits" in body
    assert "M15" in body["timeframes"]


@pytest.mark.django_db
def test_equity_curve_and_export_helpers(user):
    config = validate_config({"symbol": "EURUSD", "timeframe": "M15", "count": 300})
    run = BacktestRun.objects.create(user=user, symbol="EURUSD", timeframe="M15", config=config)
    execute_run(run)
    run.refresh_from_db()

    points = equity_curve(run)
    assert points[0]["equity"] == 10000.0
    content, ctype, filename = export_run(run, "csv")
    assert ctype == "text/csv" and filename.endswith(".csv")
    content_json, ctype_json, _ = export_run(run, "json")
    assert ctype_json == "application/json" and "run" in content_json


@pytest.mark.django_db
def test_active_run_limit(api, user):
    for _ in range(10):
        BacktestRun.objects.create(
            user=user, symbol="EURUSD", timeframe="M15", status=BacktestRun.Status.QUEUED
        )
    resp = api.post(reverse(RUN_LIST), {"symbol": "EURUSD", "count": 300}, format="json")
    assert resp.status_code == 429
