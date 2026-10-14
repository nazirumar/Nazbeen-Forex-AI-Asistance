"""Backtesting API views.

Phase 11F introduced the read-only history endpoint. Phase 11G adds the
execution and reporting surface:

    POST   /api/backtests/runs/                 create + queue a run
    GET    /api/backtests/runs/                 list the caller's runs
    GET    /api/backtests/runs/<uuid>/          run detail
    GET    /api/backtests/runs/<uuid>/trades/   simulated trades
    GET    /api/backtests/runs/<uuid>/metrics/  §6 performance metrics
    GET    /api/backtests/runs/<uuid>/equity/   equity/balance curve
    GET    /api/backtests/runs/<uuid>/export/   CSV/JSON export

``GET /api/backtests/`` (the Phase 11F read-only list) is preserved unchanged.

Every endpoint is authenticated and scoped to the requesting user: a run is only
ever visible to its owner (runs recorded without an owner are hidden entirely).
Validation failures answer **400**; unexpected failures are logged server-side
and answered generically (mirrors ``marketdata/views.py``).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nazbeen_forex_ai.backtesting.models import BacktestRun
from nazbeen_forex_ai.backtesting.services import (
    DEFAULT_CONFIG,
    BacktestExecutionError,
    default_config_response,
    equity_curve,
    export_run,
    serialize_run,
    serialize_trade,
    validate_config,
)
from nazbeen_forex_ai.backtesting.tasks import run_backtest_task
from nazbeen_forex_ai.marketdata.factory import get_market_data_provider
from nazbeen_forex_ai.marketdata.views import provider_mode

logger = logging.getLogger(__name__)

GENERIC_INTERNAL_ERROR = "Internal error while processing the request."
MAX_ACTIVE_RUNS = 10


def _serialize(run: BacktestRun) -> dict:
    """Backward-compatible name kept for the Phase 11F list endpoint."""
    return serialize_run(run)


def _get_own_run(request, run_id: str) -> BacktestRun:
    """Return the caller's run or raise 404 (never reveals other users' runs)."""
    try:
        return BacktestRun.objects.get(pk=run_id, user=request.user)
    except (BacktestRun.DoesNotExist, ValidationError, ValueError):
        raise Http404


class BacktestRunListView(APIView):
    """`GET /api/backtests/runs/` list · `POST /api/backtests/runs/` create."""

    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        runs = BacktestRun.objects.filter(user=request.user).order_by("-created_at")[:100]
        return Response(
            {"count": len(runs), "runs": [serialize_run(r) for r in runs]},
            status=status.HTTP_200_OK,
        )

    def post(self, request) -> Response:
        try:
            config = validate_config(request.data)
        except ValidationError as e:
            return Response(
                {"error": "Invalid configuration", "details": e.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        active = BacktestRun.objects.filter(
            user=request.user,
            status__in=[BacktestRun.Status.QUEUED, BacktestRun.Status.RUNNING],
        ).count()
        if active >= MAX_ACTIVE_RUNS:
            return Response(
                {"error": "Too many active backtests. Wait for one to finish."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        run = BacktestRun.objects.create(
            user=request.user,
            symbol=config["symbol"],
            timeframe=config["timeframe"],
            config=config,
            strategy_version=config["strategy_version"],
            status=BacktestRun.Status.QUEUED,
            data_source=_data_source_label(),
        )
        try:
            run_backtest_task.delay(str(run.id))
        except Exception:  # noqa: BLE001 — broker outage: leave the run queued
            logger.exception("backtest enqueue failed for run %s", run.id)
        run.refresh_from_db()
        return Response({"run": serialize_run(run)}, status=status.HTTP_202_ACCEPTED)


class BacktestRunDetailView(APIView):
    """`GET /api/backtests/runs/<uuid>/`."""

    permission_classes = [IsAuthenticated]

    def get(self, request, run_id: str) -> Response:
        run = _get_own_run(request, run_id)
        return Response({"run": serialize_run(run)}, status=status.HTTP_200_OK)


class BacktestRunTradesView(APIView):
    """`GET /api/backtests/runs/<uuid>/trades/`."""

    permission_classes = [IsAuthenticated]

    def get(self, request, run_id: str) -> Response:
        run = _get_own_run(request, run_id)
        trades = [serialize_trade(t) for t in run.trades.order_by("index")]
        return Response({"count": len(trades), "trades": trades}, status=status.HTTP_200_OK)


class BacktestRunMetricsView(APIView):
    """`GET /api/backtests/runs/<uuid>/metrics/`."""

    permission_classes = [IsAuthenticated]

    def get(self, request, run_id: str) -> Response:
        run = _get_own_run(request, run_id)
        return Response(
            {"metrics": run.metrics or {}, "status": run.status},
            status=status.HTTP_200_OK,
        )


class BacktestRunEquityView(APIView):
    """`GET /api/backtests/runs/<uuid>/equity/`."""

    permission_classes = [IsAuthenticated]

    def get(self, request, run_id: str) -> Response:
        run = _get_own_run(request, run_id)
        return Response({"points": equity_curve(run)}, status=status.HTTP_200_OK)


class BacktestRunExportView(APIView):
    """`GET /api/backtests/runs/<uuid>/export/?format=csv|json`."""

    permission_classes = [IsAuthenticated]

    def get(self, request, run_id: str) -> HttpResponse | Response:
        run = _get_own_run(request, run_id)
        fmt = str(request.query_params.get("format", "json")).strip().lower()
        if fmt not in ("csv", "json"):
            return Response(
                {"error": "format must be 'csv' or 'json'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        content, content_type, filename = export_run(run, fmt)
        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class BacktestConfigView(APIView):
    """`GET /api/backtests/config/` — the default configuration + valid ranges."""

    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        return Response(default_config_response(), status=status.HTTP_200_OK)


def _data_source_label() -> str:
    """Honest provider label ('mock'/'mt5'/'auto') recorded on every run."""
    try:
        return provider_mode(get_market_data_provider())
    except Exception:  # noqa: BLE001
        return "unknown"
