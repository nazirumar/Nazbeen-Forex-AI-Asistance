"""Analysis URL routes."""

from django.urls import path

from nazbeen_forex_ai.analysis.views import ScreenshotUploadView, AnalysisDetailView

app_name = "analysis"

urlpatterns = [
    path("analysis/upload/", ScreenshotUploadView.as_view(), name="upload"),
    path("analysis/<uuid:analysis_id>/", AnalysisDetailView.as_view(), name="detail"),
]
