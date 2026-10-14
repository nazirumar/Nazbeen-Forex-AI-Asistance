"""Journal URL routes (Phase 11F)."""

from django.urls import path

from nazbeen_forex_ai.journal.views import (
    JournalDetailView,
    JournalEntryView,
    JournalExportView,
    JournalPerformanceView,
    MentorView,
)

app_name = "journal"

urlpatterns = [
    path("journal/entries/", JournalEntryView.as_view(), name="entries"),
    # Retained for backward compatibility with the original search endpoint.
    path("journal/search/", JournalEntryView.as_view(), name="search"),
    path("journal/entries/<uuid:entry_id>/", JournalDetailView.as_view(), name="entry_detail"),
    path("journal/performance/", JournalPerformanceView.as_view(), name="performance"),
    path("journal/export/", JournalExportView.as_view(), name="export"),
    path("mentor/ask/", MentorView.as_view(), name="mentor_ask"),
]
