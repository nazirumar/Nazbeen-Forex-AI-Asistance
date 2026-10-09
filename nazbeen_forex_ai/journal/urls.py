"""Journal URL routes."""

from django.urls import path

from nazbeen_forex_ai.journal.views import JournalEntryView, JournalListView, MentorView

app_name = "journal"

urlpatterns = [
    path("journal/entries/", JournalEntryView.as_view(), name="entries"),
    path("journal/search/", JournalListView.as_view(), name="search"),
    path("mentor/ask/", MentorView.as_view(), name="mentor_ask"),
]
