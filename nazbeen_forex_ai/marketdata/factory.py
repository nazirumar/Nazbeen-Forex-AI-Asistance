"""Factory to select provider based on config (mock for offline testing).

Phase 11C (audit H-09): the MT5 credential/performance settings declared in
:mod:`nazbeen_forex_ai.marketdata.settings` were previously dead configuration —
the factory constructed the provider with no arguments. They are now wired
through, including the broker symbol suffix.
"""

from __future__ import annotations

from django.conf import settings

from nazbeen_forex_ai.config import env_bool
from nazbeen_forex_ai.marketdata import settings as md_settings

from .mock import MockMarketDataProvider
from .mt5_connector import MT5MarketDataProvider
from .providers import MarketDataProvider


def get_market_data_provider() -> MarketDataProvider:
    use_mock = env_bool("MT5_USE_MOCK", True) or getattr(settings, "MT5_USE_MOCK", False)
    if use_mock:
        return MockMarketDataProvider()
    return MT5MarketDataProvider(
        path=md_settings.MT5_PATH or None,
        login=md_settings.MT5_LOGIN or None,
        server=md_settings.MT5_SERVER or None,
        password=md_settings.MT5_PASSWORD or None,
        timeout_sec=md_settings.MT5_TIMEOUT_SEC,
        max_retries=md_settings.MT5_RETRY_MAX,
        retry_backoff=md_settings.MT5_RETRY_BACKOFF,
        symbol_suffix=md_settings.MT5_SYMBOL_SUFFIX,
    )
