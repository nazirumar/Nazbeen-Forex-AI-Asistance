"""Analysis URL routes."""

from django.urls import path

from nazbeen_forex_ai.analysis.views import (
    AnalysisDetailView,
    AnalysisScreenshotView,
    ScreenshotUploadView,
)

app_name = "analysis"

urlpatterns = [
    path("analysis/upload/", ScreenshotUploadView.as_view(), name="upload"),
    path("analysis/<uuid:analysis_id>/", AnalysisDetailView.as_view(), name="detail"),
    path(
        "analysis/<uuid:analysis_id>/screenshot/",
        AnalysisScreenshotView.as_view(),
        name="screenshot",
    ),
]
