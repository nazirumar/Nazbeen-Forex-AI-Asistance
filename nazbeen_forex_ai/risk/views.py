"""Risk API endpoints (analysis-only)."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nazbeen_forex_ai.risk.services import create_trade_plan


class TradePlanView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request) -> Response:
        data = request.data
        try:
            plan = create_trade_plan(data)
        except Exception as e:
            return Response({"error": str(e), "decision": "WAIT"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(plan, status=status.HTTP_200_OK)
