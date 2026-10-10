"""Root URL configuration for Nazbeen Forex AI Asistance."""

from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("nazbeen_forex_ai.core.urls")),
    path("api/auth/", include("nazbeen_forex_ai.accounts.urls")),
    path("api/", include("nazbeen_forex_ai.marketdata.urls")),
    path("api/", include("nazbeen_forex_ai.structure.urls")),
    path("api/", include("nazbeen_forex_ai.analysis.urls")),
    path("api/", include("nazbeen_forex_ai.risk.urls")),
    path("api/", include("nazbeen_forex_ai.journal.urls")),
]
