"""Backtesting URL routes.

Phase 11F exposed ``GET /api/backtests/`` (read-only history). Phase 11G adds the
``/api/backtests/runs/…`` execution/reporting surface. The original route and its
name (``backtesting:runs``) are preserved for compatibility.
"""

from django.urls import path

from nazbeen_forex_ai.backtesting.views import (
    BacktestConfigView,
    BacktestRunDetailView,
    BacktestRunEquityView,
    BacktestRunExportView,
    BacktestRunListView,
    BacktestRunMetricsView,
    BacktestRunTradesView,
)

app_name = "backtesting"

urlpatterns = [
    # Phase 11F read-only history (unchanged contract).
    path("backtests/", BacktestRunListView.as_view(), name="runs"),
    # Phase 11G execution/reporting.
    path("backtests/config/", BacktestConfigView.as_view(), name="config"),
    path("backtests/runs/", BacktestRunListView.as_view(), name="run-list"),
    path("backtests/runs/<uuid:run_id>/", BacktestRunDetailView.as_view(), name="run-detail"),
    path(
        "backtests/runs/<uuid:run_id>/trades/",
        BacktestRunTradesView.as_view(),
        name="run-trades",
    ),
    path(
        "backtests/runs/<uuid:run_id>/metrics/",
        BacktestRunMetricsView.as_view(),
        name="run-metrics",
    ),
    path(
        "backtests/runs/<uuid:run_id>/equity/",
        BacktestRunEquityView.as_view(),
        name="run-equity",
    ),
    path(
        "backtests/runs/<uuid:run_id>/export/",
        BacktestRunExportView.as_view(),
        name="run-export",
    ),
]
