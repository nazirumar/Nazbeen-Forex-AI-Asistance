"""Analysis URL routes."""

from django.urls import path

from nazbeen_forex_ai.analysis.views import (
    AnalysisDetailView,
    AnalysisListView,
    AnalysisScreenshotView,
    ScreenshotUploadView,
)

app_name = "analysis"

urlpatterns = [
    path("analysis/upload/", ScreenshotUploadView.as_view(), name="upload"),
    path("analysis/", AnalysisListView.as_view(), name="list"),
    path("analysis/<uuid:analysis_id>/", AnalysisDetailView.as_view(), name="detail"),
    path(
        "analysis/<uuid:analysis_id>/screenshot/",
        AnalysisScreenshotView.as_view(),
        name="screenshot",
    ),
]
