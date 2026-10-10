"""Screenshot analysis API views."""

from __future__ import annotations

import logging
from typing import Any

from rest_framework import status, parsers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404

from nazbeen_forex_ai.analysis.models import ScreenshotAnalysis
from nazbeen_forex_ai.analysis.services import ScreenshotAnalysisService
from nazbeen_forex_ai.analysis.storage import resolve_screenshot_path, save_screenshot
from nazbeen_forex_ai.analysis.validators import validate_image_upload

logger = logging.getLogger(__name__)

_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}


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

        # Persist the screenshot server-side (audit H-02): the analysis record
        # keeps only the storage-relative path of a server-named file, so the
        # upload can be re-inspected later. Persistence failure never fabricates
        # a path — it is logged and the record is kept with an empty path.
        stored_path = ""
        try:
            file.seek(0)
            screenshot_bytes = file.read()
            if screenshot_bytes:
                stored_path = save_screenshot(screenshot_bytes, getattr(file, "name", "upload"))
        except Exception:
            logger.exception(
                "screenshot persistence failed for user=%s (analysis continues)",
                request.user.pk,
            )
            stored_path = ""

        try:
            analysis = ScreenshotAnalysis.objects.create(
                user=request.user,
                image_path=stored_path,
                symbol=result.symbol,
                timeframe=result.timeframe,
                ai_summary=result.summary,
                structured_output=result.model_dump(),
                disagreements=result.model_dump().get("disagreements", []),
                mtf_conflicts=result.model_dump().get("mtf_conflicts", []),
                evidence=[e.model_dump() if hasattr(e, "model_dump") else e for e in result.evidence],
                metadata={
                    "model": result.model,
                    "data_synchronized": result.data_synchronized,
                    "screenshot_stored": bool(stored_path),
                },
            )
        except Exception:
            logger.exception("failed to persist analysis record for user=%s", request.user.pk)
            analysis = None

        payload = {
            "result": result.model_dump(),
            "screenshot_stored": bool(stored_path),
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


class AnalysisScreenshotView(APIView):
    """Ownership-scoped screenshot retrieval (audit H-02)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, analysis_id) -> Response:
        try:
            analysis = ScreenshotAnalysis.objects.get(id=analysis_id, user=request.user)
        except ScreenshotAnalysis.DoesNotExist:
            # Not found for everyone who does not own it — no existence leak.
            raise Http404("Analysis not found")
        path = resolve_screenshot_path(analysis.image_path or "")
        if path is None or not path.is_file():
            raise Http404("Screenshot not stored")
        content_type = _CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")
        return FileResponse(path.open("rb"), content_type=content_type, as_attachment=False)
