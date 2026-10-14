"""Forward-testing API views (Phase 11G §9/§10).

    POST /api/forwardtests/runs/                          create (simulated)
    GET  /api/forwardtests/runs/                          list the caller's runs
    GET  /api/forwardtests/runs/<uuid>/                   detail
    GET  /api/forwardtests/runs/<uuid>/observations/      recorded decisions
    POST /api/forwardtests/runs/<uuid>/observe/           run one cycle
    POST /api/forwardtests/runs/<uuid>/stop/              stop observing
    POST /api/forwardtests/observations/<uuid>/journal/   journal entry (typed)
    GET  /api/forwardtests/config/                        defaults + ranges

Every endpoint is authenticated and owner-scoped: another user's run is a 404.
Nothing here places orders — runs and observations are always labelled simulated.
Validation failures answer **400**; unexpected failures are logged and answered
generically (mirrors ``backtesting/views.py``).
"""

from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from django.http import Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nazbeen_forex_ai.forwardtest.models import ForwardTestObservation, ForwardTestRun
from nazbeen_forex_ai.forwardtest.services import (
    MAX_ACTIVE_RUNS,
    default_config_response,
    journalize_observation,
    serialize_observation,
    serialize_run,
    validate_config,
)
from nazbeen_forex_ai.forwardtest.tasks import observe_run_task
from nazbeen_forex_ai.marketdata.factory import get_market_data_provider
from nazbeen_forex_ai.marketdata.views import provider_mode

logger = logging.getLogger(__name__)

GENERIC_INTERNAL_ERROR = "Internal error while processing the request."


def _data_source_label() -> str:
    try:
        return provider_mode(get_market_data_provider())
    except Exception:  # noqa: BLE001
        return "unknown"


def _get_own_run(request, run_id: str) -> ForwardTestRun:
    try:
        return ForwardTestRun.objects.get(pk=run_id, user=request.user)
    except (ForwardTestRun.DoesNotExist, ValidationError, ValueError):
        raise Http404


class ForwardTestRunListView(APIView):
    """`GET`list · `POST` create."""

    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        runs = ForwardTestRun.objects.filter(user=request.user).order_by("-created_at")[:100]
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

        active = ForwardTestRun.objects.filter(
            user=request.user, status=ForwardTestRun.Status.ACTIVE
        ).count()
        if active >= MAX_ACTIVE_RUNS:
            return Response(
                {"error": "Too many active forward tests. Stop one first."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        run = ForwardTestRun.objects.create(
            user=request.user,
            symbol=config["symbol"],
            timeframe=config["timeframe"],
            config=config,
            strategy_version=config["strategy_version"],
            status=ForwardTestRun.Status.ACTIVE,
            data_source=_data_source_label(),
            started_at=timezone.now(),
            note="Simulated forward test (analysis-only); no orders are placed.",
        )
        return Response({"run": serialize_run(run)}, status=status.HTTP_201_CREATED)


class ForwardTestRunDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, run_id: str) -> Response:
        run = _get_own_run(request, run_id)
        return Response({"run": serialize_run(run)}, status=status.HTTP_200_OK)


class ForwardTestRunObservationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, run_id: str) -> Response:
        run = _get_own_run(request, run_id)
        try:
            limit = int(request.query_params.get("limit", 200))
        except (TypeError, ValueError):
            return Response(
                {"error": "limit must be an integer"}, status=status.HTTP_400_BAD_REQUEST
            )
        limit = max(1, min(limit, 1000))
        rows = run.observations.order_by("-bar_time")[:limit]
        return Response(
            {"count": len(rows), "observations": [serialize_observation(o) for o in rows]},
            status=status.HTTP_200_OK,
        )


class ForwardTestRunObserveView(APIView):
    """`POST` run one observation cycle (queued on the heavy queue)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, run_id: str) -> Response:
        run = _get_own_run(request, run_id)
        if run.status != ForwardTestRun.Status.ACTIVE:
            return Response(
                {"error": "Only active runs can be observed.", "run": serialize_run(run)},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            observe_run_task.delay(str(run.id))
        except Exception:  # noqa: BLE001 — broker outage: leave the run active
            logger.exception("forward test enqueue failed for run %s", run.id)
        run.refresh_from_db()
        return Response({"run": serialize_run(run)}, status=status.HTTP_202_ACCEPTED)


class ForwardTestRunStopView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, run_id: str) -> Response:
        run = _get_own_run(request, run_id)
        if run.status == ForwardTestRun.Status.ACTIVE:
            run.status = ForwardTestRun.Status.STOPPED
            run.stopped_at = timezone.now()
            run.save(update_fields=["status", "stopped_at"])
        return Response({"run": serialize_run(run)}, status=status.HTTP_200_OK)


class ForwardTestObservationJournalView(APIView):
    """`POST` create a typed journal entry (source=forward_test) from an observation."""

    permission_classes = [IsAuthenticated]

    def post(self, request, observation_id: str) -> Response:
        try:
            obs = ForwardTestObservation.objects.get(
                pk=observation_id, run__user=request.user
            )
        except (ForwardTestObservation.DoesNotExist, ValidationError, ValueError):
            raise Http404
        entry = journalize_observation(request.user, obs)
        if entry is None:
            raise Http404
        return Response(
            {"journal_entry_id": str(entry.id), "source": entry.source},
            status=status.HTTP_201_CREATED,
        )


class ForwardTestConfigView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        return Response(default_config_response(), status=status.HTTP_200_OK)
