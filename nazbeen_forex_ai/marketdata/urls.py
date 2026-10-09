"""Market data URL routes."""

from django.urls import path

from nazbeen_forex_ai.marketdata.views import (
    MT5CandlesView,
    MT5StatusView,
    MT5SymbolsView,
    MT5TickView,
)

app_name = "marketdata"

urlpatterns = [
    path("mt5/status/", MT5StatusView.as_view(), name="mt5_status"),
    path("mt5/symbols/", MT5SymbolsView.as_view(), name="mt5_symbols"),
    path("mt5/candles/", MT5CandlesView.as_view(), name="mt5_candles"),
    path("mt5/tick/", MT5TickView.as_view(), name="mt5_tick"),
]