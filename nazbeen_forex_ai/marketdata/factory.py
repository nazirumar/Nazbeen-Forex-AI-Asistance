"""Factory to select provider based on config (mock for offline testing)."""

from __future__ import annotations

from django.conf import settings

from nazbeen_forex_ai.config import env_bool

from .mock import MockMarketDataProvider
from .mt5_connector import MT5MarketDataProvider
from .providers import MarketDataProvider


def get_market_data_provider() -> MarketDataProvider:
    use_mock = env_bool("MT5_USE_MOCK", True) or getattr(settings, "MT5_USE_MOCK", False)
    if use_mock:
        return MockMarketDataProvider()
    return MT5MarketDataProvider()