"""Risk URL routes."""

from django.urls import path

from nazbeen_forex_ai.risk.views import TradePlanView

app_name = "risk"

urlpatterns = [
    path("risk/trade-plan/", TradePlanView.as_view(), name="trade_plan"),
]
