"""Forward-testing URL routes (Phase 11G §9)."""

from django.urls import path

from nazbeen_forex_ai.forwardtest.views import (
    ForwardTestConfigView,
    ForwardTestObservationJournalView,
    ForwardTestRunDetailView,
    ForwardTestRunListView,
    ForwardTestRunObservationsView,
    ForwardTestRunObserveView,
    ForwardTestRunStopView,
)

app_name = "forwardtest"

urlpatterns = [
    path("forwardtests/config/", ForwardTestConfigView.as_view(), name="config"),
    path("forwardtests/runs/", ForwardTestRunListView.as_view(), name="run-list"),
    path("forwardtests/runs/<uuid:run_id>/", ForwardTestRunDetailView.as_view(), name="run-detail"),
    path(
        "forwardtests/runs/<uuid:run_id>/observations/",
        ForwardTestRunObservationsView.as_view(),
        name="run-observations",
    ),
    path(
        "forwardtests/runs/<uuid:run_id>/observe/",
        ForwardTestRunObserveView.as_view(),
        name="run-observe",
    ),
    path(
        "forwardtests/runs/<uuid:run_id>/stop/",
        ForwardTestRunStopView.as_view(),
        name="run-stop",
    ),
    path(
        "forwardtests/observations/<uuid:observation_id>/journal/",
        ForwardTestObservationJournalView.as_view(),
        name="observation-journal",
    ),
]
