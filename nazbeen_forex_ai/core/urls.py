"""Core app URL routes (mounted under ``/api/``)."""

from django.urls import path

from nazbeen_forex_ai.core.views import HealthView

app_name = "core"

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
]
