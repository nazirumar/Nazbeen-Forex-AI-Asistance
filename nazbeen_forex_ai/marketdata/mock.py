"""Mock market data adapter for offline testing.

Mock data is ALWAYS labeled as mock in any API response.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from nazbeen_forex_ai.marketdata.providers import (
    Candle,
    MarketDataProvider,
    MarketDataProviderError,
    ensure_utc,
)


class MockMarketDataProvider(MarketDataProvider):
    """Deterministic mock provider - clearly labeled as mock."""

    def __init__(self) -> None:
        self._connected = False

    def connect(self) -> bool:
        self._connected = True
        return True

    def is_connected(self) -> bool:
        return self._connected

    def get_connection_info(self) -> dict[str, Any]:
        return {
            "connected": self._connected,
            "mode": "mock",
            "label": "Mock (offline testing)",
            "broker": "MOCK",
            "server": "MOCK",
            "terminal_name": "MockTerminal",
        }

    def get_symbols(self, search: str | None = None) -> list[dict[str, Any]]:
        symbols = [
            {"symbol": "EURUSD", "description": "Euro vs US Dollar (MOCK)", "path": "Forex\\Major"},
            {"symbol": "GBPUSD", "description": "GBP vs USD (MOCK)", "path": "Forex\\Major"},
        ]
        if search:
            s = search.upper()
            symbols = [x for x in symbols if s in x["symbol"]]
        return symbols

    def _base_price(self) -> float:
        return 1.1050

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        start: datetime | None = None,
        count: int | None = None,
    ) -> list[Candle]:
        if not self._connected:
            raise MarketDataProviderError("not connected")
        tf_map = {"M1": 1, "M5": 5, "M15": 15, "M1S": 1, "M5S": 5, "M15S": 15, "H1": 60}
        mins = tf_map.get(timeframe, 15)
        end = start or datetime.now(timezone.utc)
        end = ensure_utc(end)
        count = count or 100
        candles: list[Candle] = []
        price = self._base_price()
        for i in range(count - 1, -1, -1):
            t = end - timedelta(minutes=mins * i)
            # simple oscillation
            delta = 0.0001 * ((i % 5) - 2)
            o = price + delta
            c = o + 0.00005 * ((i % 3) - 1)
            h = max(o, c) + 0.00002
            l = min(o, c) - 0.00002
            candles.append(Candle(time=t, open=o, high=h, low=l, close=c, tick_volume=100))
            price = c
        return candles

    def get_tick(self, symbol: str) -> dict[str, Any]:
        if not self._connected:
            raise MarketDataProviderError("not connected")
        return {
            "symbol": symbol,
            "bid": 1.10500,
            "ask": 1.10502,
            "spread": 0.00002,
            "time": utcnow().isoformat().replace("+00:00", "Z"),
            "mode": "mock",
        }