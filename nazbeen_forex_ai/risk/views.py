"""Risk API endpoints (analysis-only).

Phase 11C hardening (audits M-05/L-02): requests are validated by a strict
serializer (finite/bounded numbers) so malformed input returns **400** with
safe messages; unexpected failures are logged server-side and answered with a
generic message — provider/internal exception text never reaches clients.
"""

from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nazbeen_forex_ai.risk.serializers import validate_trade_plan_request
from nazbeen_forex_ai.risk.services import create_trade_plan

logger = logging.getLogger(__name__)


class TradePlanView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request) -> Response:
        try:
            payload = validate_trade_plan_request(request.data)
        except ValidationError as e:
            return Response(
                {"error": "Invalid trade plan input", "details": e.messages, "decision": "WAIT"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            plan = create_trade_plan(payload)
        except ValidationError as e:
            return Response(
                {"error": "Invalid trade plan input", "details": e.messages, "decision": "WAIT"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception("trade plan evaluation failed")
            return Response(
                {"error": "Internal error while evaluating the trade plan", "decision": "WAIT"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(plan, status=status.HTTP_200_OK)
