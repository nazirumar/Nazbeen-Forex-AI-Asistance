"""Structure URL routes (Phase 11D)."""

from django.urls import path

from nazbeen_forex_ai.structure.views import StructureView

app_name = "structure"

urlpatterns = [
    path("structure/", StructureView.as_view(), name="structure"),
]
