"""Journal API views (Phase 11F).

Endpoints:
    POST   /api/journal/entries/            create
    GET    /api/journal/entries/            list / search
    GET    /api/journal/entries/<uuid>/     retrieve
    PATCH  /api/journal/entries/<uuid>/     partial update
    DELETE /api/journal/entries/<uuid>/     delete
    GET    /api/journal/performance/        honest performance aggregate
    GET    /api/journal/export/             CSV/JSON export of recorded rows

Validation failures answer **400** with safe messages; unexpected failures are
logged server-side and answered generically (mirrors ``risk/views.py``).
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nazbeen_forex_ai.journal.models import JournalEntry
from nazbeen_forex_ai.journal.services import JournalService, MentorService

logger = logging.getLogger(__name__)


def _iso(value) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def serialize_entry(entry: JournalEntry) -> dict[str, Any]:
    """Full spec §3.H representation. Recorded-only: nothing is invented."""
    return {
        "id": str(entry.id),
        "symbol": entry.symbol,
        "timeframe": entry.timeframe,
        "analysis_session_id": str(entry.analysis_session_id) if entry.analysis_session_id else None,
        "screenshot_analysis_id": str(entry.screenshot_analysis_id) if entry.screenshot_analysis_id else None,
        "analysis_timestamp": _iso(entry.analysis_timestamp),
        "market_snapshot": entry.market_snapshot,
        "detected_structures": entry.detected_structures,
        "model_version": entry.model_version,
        "strategy_version": entry.strategy_version,
        "scenario_decision": entry.scenario_decision,
        "entry": entry.entry,
        "sl": entry.sl,
        "tp": entry.tp,
        "rr": entry.rr,
        "estimated_probability": entry.estimated_probability,
        "outcome": entry.outcome,
        "pnl": entry.pnl,
        "notes": entry.notes,
        "tags": entry.tags,
        "metrics": entry.metrics,
        "created_at": _iso(entry.created_at),
        "updated_at": _iso(entry.updated_at),
    }


class JournalEntryView(APIView):
    """`/api/journal/entries/` — create + list."""

    permission_classes = [IsAuthenticated]

    def post(self, request) -> Response:
        try:
            entry = JournalService().save_entry(request.user, request.data)
        except ValidationError as exc:
            return Response(
                {"error": "Invalid journal entry", "details": exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception("journal entry creation failed")
            return Response(
                {"error": "Internal error while saving the journal entry"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(serialize_entry(entry), status=status.HTTP_201_CREATED)

    def get(self, request) -> Response:
        svc = JournalService()
        try:
            limit = int(request.query_params.get("limit", 50))
        except (TypeError, ValueError):
            return Response(
                {"error": "limit must be an integer"}, status=status.HTTP_400_BAD_REQUEST
            )
        entries = svc.search(
            request.user,
            query=request.query_params.get("q"),
            symbol=request.query_params.get("symbol"),
            outcome=request.query_params.get("outcome"),
            limit=limit,
        )
        return Response(
            {"count": len(entries), "entries": [serialize_entry(e) for e in entries]},
            status=status.HTTP_200_OK,
        )


class JournalDetailView(APIView):
    """`/api/journal/entries/<uuid>/` — retrieve / update / delete (owner-scoped)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, entry_id) -> Response:
        entry = JournalService().get_entry(request.user, entry_id)
        if entry is None:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(serialize_entry(entry), status=status.HTTP_200_OK)

    def patch(self, request, entry_id) -> Response:
        return self._update(request, entry_id, partial=True)

    def put(self, request, entry_id) -> Response:
        return self._update(request, entry_id, partial=False)

    def _update(self, request, entry_id, partial: bool) -> Response:
        try:
            entry = JournalService().update_entry(request.user, entry_id, request.data)
        except ValidationError as exc:
            return Response(
                {"error": "Invalid journal entry", "details": exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception("journal entry update failed")
            return Response(
                {"error": "Internal error while updating the journal entry"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        if entry is None:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(serialize_entry(entry), status=status.HTTP_200_OK)

    def delete(self, request, entry_id) -> Response:
        deleted = JournalService().delete_entry(request.user, entry_id)
        if not deleted:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class JournalPerformanceView(APIView):
    """`/api/journal/performance/` — aggregate over recorded fields only."""

    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        return Response(JournalService().performance(request.user), status=status.HTTP_200_OK)


class JournalExportView(APIView):
    """`/api/journal/export/?format=csv|json` — export recorded rows."""

    permission_classes = [IsAuthenticated]

    def get(self, request) -> HttpResponse | Response:
        fmt = request.query_params.get("format", "json")
        try:
            content_type, payload = JournalService().export(request.user, fmt)
        except ValidationError as exc:
            return Response(
                {"error": "Invalid export request", "details": exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if isinstance(payload, str):
            response = HttpResponse(payload, content_type=content_type)
            response["Content-Disposition"] = 'attachment; filename="journal_export.csv"'
            return response
        return Response(payload, status=status.HTTP_200_OK)


class MentorView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request) -> Response:
        question = (request.data or {}).get("question", "")
        if not isinstance(question, str) or not question.strip():
            return Response(
                {"error": "question is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        answer = MentorService().answer(request.user, question, request.data.get("context"))
        return Response({"answer": answer}, status=status.HTTP_200_OK)
