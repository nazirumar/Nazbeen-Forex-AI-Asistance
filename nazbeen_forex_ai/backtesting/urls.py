"""Backtesting URL routes (Phase 11F)."""

from django.urls import path

from nazbeen_forex_ai.backtesting.views import BacktestRunListView

app_name = "backtesting"

urlpatterns = [
    path("backtests/", BacktestRunListView.as_view(), name="runs"),
]
