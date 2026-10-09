"""Journal API views."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nazbeen_forex_ai.journal.services import JournalService, MentorService


class JournalEntryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request) -> Response:
        svc = JournalService()
        entry = svc.save_entry(request.user, request.data)
        return Response({"id": str(entry.id)}, status=status.HTTP_201_CREATED)


class JournalListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        svc = JournalService()
        q = request.query_params.get("q")
        entries = svc.search(request.user, q)
        return Response(
            {
                "entries": [
                    {"id": str(e.id), "symbol": e.symbol, "outcome": e.outcome, "notes": e.notes}
                    for e in entries
                ]
            },
            status=status.HTTP_200_OK,
        )


class MentorView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request) -> Response:
        svc = MentorService()
        q = request.data.get("question", "")
        ans = svc.answer(request.user, q, request.data.get("context"))
        return Response({"answer": ans}, status=status.HTTP_200_OK)
