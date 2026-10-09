"""Screenshot analysis API views."""

from __future__ import annotations

import json
from typing import Any

from rest_framework import status, parsers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.exceptions import ValidationError

from nazbeen_forex_ai.analysis.models import ScreenshotAnalysis
from nazbeen_forex_ai.analysis.services import ScreenshotAnalysisService
from nazbeen_forex_ai.analysis.validators import validate_image_upload


class ScreenshotUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request) -> Response:
        file = request.FILES.get("image") or request.FILES.get("file")
        if not file:
            return Response({"error": "No image file provided"}, status=status.HTTP_400_BAD_REQUEST)
        # Strict validation: invalid uploads are rejected with a safe 400 (audit H-01).
        try:
            validate_image_upload(file)
        except ValidationError as e:
            return Response(
                {"error": "Invalid image upload", "details": e.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_hints = {}
        if request.data.get("symbol"):
            user_hints["symbol"] = str(request.data.get("symbol"))
        if request.data.get("timeframe"):
            user_hints["timeframe"] = str(request.data.get("timeframe"))

        service = ScreenshotAnalysisService()
        result = service.analyze(image_file=file, user_hints=user_hints)

        try:
            analysis = ScreenshotAnalysis.objects.create(
                user=request.user,
                image_path=getattr(file, "name", "") or "upload",
                symbol=result.symbol,
                timeframe=result.timeframe,
                ai_summary=result.summary,
                structured_output=result.model_dump(),
                disagreements=result.model_dump().get("disagreements", []),
                mtf_conflicts=result.model_dump().get("mtf_conflicts", []),
                evidence=[e.model_dump() if hasattr(e, "model_dump") else e for e in result.evidence],
                metadata={"model": result.model, "data_synchronized": result.data_synchronized},
            )
        except Exception as e:
            analysis = None

        payload = {
            "result": result.model_dump(),
        }
        if analysis:
            payload["analysis_id"] = str(analysis.id)
        # Return plain dict to avoid DRF encoder issues
        from django.http import JsonResponse
        return JsonResponse(payload, status=status.HTTP_201_CREATED)


class AnalysisDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, analysis_id) -> Response:
        try:
            analysis = ScreenshotAnalysis.objects.get(id=analysis_id, user=request.user)
        except ScreenshotAnalysis.DoesNotExist:
            return Response({"error": "Analysis not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"analysis": analysis.structured_output}, status=status.HTTP_200_OK)
