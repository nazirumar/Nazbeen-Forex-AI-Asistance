"""Market data providers: interface, mock adapter, and MT5 connector wrapper."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import pandas as pd


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class CandleValidationError(Exception):
    """Raised when candle data fails validation."""


class MarketDataProviderError(Exception):
    """Base error for market data provider failures."""


class Candle:
    """Normalized OHLCV candle in UTC."""

    def __init__(
        self,
        time: datetime,
        open: float,
        high: float,
        low: float,
        close: float,
        tick_volume: int | float | None = None,
        spread: float | None = None,
        real_volume: int | float | None = None,
    ) -> None:
        self.time = ensure_utc(time)
        self.open = float(open)
        self.high = float(high)
        self.low = float(low)
        self.close = float(close)
        self.tick_volume = int(tick_volume) if tick_volume is not None else None
        self.spread = float(spread) if spread is not None else None
        self.real_volume = int(real_volume) if real_volume is not None else None
        self._validate()

    def _validate(self) -> None:
        if self.high < self.low:
            raise CandleValidationError("high < low")
        if self.high < self.open or self.high < self.close:
            pass  # allow some cases? but generally unusual
        if self.low > self.open or self.low > self.close:
            pass
        # basic sanity
        if any(v < 0 for v in [self.open, self.high, self.low, self.close]):
            raise CandleValidationError("negative price")
        if self.tick_volume is not None and self.tick_volume < 0:
            raise CandleValidationError("negative volume")

    def to_dict(self) -> dict[str, Any]:
        return {
            "time": self.time.isoformat().replace("+00:00", "Z"),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "tick_volume": self.tick_volume,
            "spread": self.spread,
            "real_volume": self.real_volume,
        }


class MarketDataProvider(ABC):
    """Abstract provider for market data access."""

    @abstractmethod
    def connect(self) -> bool:
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        ...

    @abstractmethod
    def get_connection_info(self) -> dict[str, Any]:
        ...

    @abstractmethod
    def get_symbols(self, search: str | None = None) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        start: datetime | None = None,
        count: int | None = None,
    ) -> list[Candle]:
        ...

    @abstractmethod
    def get_tick(self, symbol: str) -> dict[str, Any]:
        ...