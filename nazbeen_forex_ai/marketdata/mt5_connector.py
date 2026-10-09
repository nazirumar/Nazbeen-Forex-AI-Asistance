"""MT5 connector wrapper (Windows-only runtime)."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from nazbeen_forex_ai.marketdata.providers import (
    Candle,
    MarketDataProvider,
    MarketDataProviderError,
    ensure_utc,
)

logger = logging.getLogger(__name__)

try:
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover
    mt5 = None


TIMEFRAME_MAP: dict[str, Any] = {}
if mt5 is not None:
    try:
        TIMEFRAME_MAP = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "H1": mt5.TIMEFRAME_H1,
        }
    except Exception:
        TIMEFRAME_MAP = {}


class MT5MarketDataProvider(MarketDataProvider):
    """MT5 provider - only functional when MetaTrader5 terminal is installed on Windows."""

    def __init__(
        self,
        path: str | None = None,
        login: int | None = None,
        server: str | None = None,
        password: str | None = None,
        timeout_sec: int = 30,
        max_retries: int = 3,
        retry_backoff: float = 0.5,
    ) -> None:
        self._path = path
        self._login = login
        self._server = server
        self._password = password
        self._timeout_sec = timeout_sec
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._connected = False

    def _call_with_retry(self, fn, *args, **kwargs):
        last_err: Exception | None = None
        for i in range(self._max_retries):
            try:
                return fn(*args, **kwargs)
            except Exception as e:  # pragma: no cover - MT5 runtime
                last_err = e
                logger.warning("MT5 call failed (attempt %s/%s): %s", i + 1, self._max_retries, e)
                if i < self._max_retries - 1:
                    time.sleep(self._retry_backoff * (i + 1))
        raise MarketDataProviderError(f"MT5 operation failed: {last_err}")

    def connect(self) -> bool:
        if mt5 is None:
            raise MarketDataProviderError("MetaTrader5 not installed")
        if self._connected and mt5.terminal_info() is not None:
            return True

        def _init():
            if self._path:
                return mt5.initialize(path=self._path, login=self._login or 0, password=self._password or "", server=self._server or "", timeout=self._timeout_sec)
            return mt5.initialize()

        ok = self._call_with_retry(_init)
        self._connected = bool(ok)
        if not self._connected:
            err = mt5.last_error() if hasattr(mt5, "last_error") else "unknown"
            logger.error("MT5 initialize failed: %s", err)
            raise MarketDataProviderError(f"MT5 initialize failed: {err}")
        return True

    def is_connected(self) -> bool:
        if not self._connected or mt5 is None:
            return False
        try:
            return mt5.terminal_info() is not None
        except Exception:
            self._connected = False
            return False

    def get_connection_info(self) -> dict[str, Any]:
        try:
            if not self.is_connected():
                return {"connected": False, "mode": "mt5"}
            ti = mt5.terminal_info()
            ai = mt5.account_info()
            info: dict[str, Any] = {
                "connected": True,
                "mode": "mt5",
                "broker": getattr(ai, "company", None) if ai else None,
                "server": getattr(ai, "server", None) if ai else None,
                "login": getattr(ai, "login", None) if ai else None,
                "terminal_name": getattr(ti, "name", None) if ti else None,
                "path": getattr(ti, "path", None) if ti else None,
                "data_path": getattr(ti, "data_path", None) if ti else None,
                "build": getattr(ti, "build", None) if ti else None,
                "trade_allowed": getattr(ti, "trade_allowed", None) if ti else None,
            }
            return info
        except Exception as e:
            raise MarketDataProviderError(str(e))

    def get_symbols(self, search: str | None = None) -> list[dict[str, Any]]:
        if not self.is_connected():
            raise MarketDataProviderError("not connected")
        if search:
            res = mt5.symbols_get(search.upper()) if hasattr(mt5, "symbols_get") else mt5.symbols_get()
        else:
            res = mt5.symbols_get()
        symbols: list[dict[str, Any]] = []
        for s in res or []:
            symbols.append(
                {
                    "symbol": getattr(s, "name", ""),
                    "description": getattr(s, "description", ""),
                    "path": getattr(s, "path", ""),
                    "currency_base": getattr(s, "currency_base", ""),
                    "currency_profit": getattr(s, "currency_profit", ""),
                }
            )
        return symbols

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        start: datetime | None = None,
        count: int | None = None,
    ) -> list[Candle]:
        if not self.is_connected():
            raise MarketDataProviderError("not connected")
        tf = TIMEFRAME_MAP.get(timeframe)
        if tf is None:
            raise MarketDataProviderError(f"unsupported timeframe {timeframe}")

        if count is not None:
            if start is not None:
                rates = mt5.copy_rates_from(symbol.upper(), tf, start, count)
            else:
                rates = mt5.copy_rates_from_pos(symbol.upper(), tf, 0, count)
        else:
            if start is None:
                raise MarketDataProviderError("either start+count or count from now required")
            # count from start? approximate by large count not ideal; require count
            rates = mt5.copy_rates_from(symbol.upper(), tf, start, 1000)

        if rates is None:
            err = mt5.last_error()
            raise MarketDataProviderError(f"copy_rates failed: {err}")
        candles: list[Candle] = []
        for r in rates:
            t = datetime.fromtimestamp(r[0], tz=timezone.utc)
            candles.append(
                Candle(
                    time=t,
                    open=float(r[1]),
                    high=float(r[2]),
                    low=float(r[3]),
                    close=float(r[4]),
                    tick_volume=r[5] if len(r) > 5 else None,
                    spread=r[6] if len(r) > 6 else None,
                    real_volume=r[7] if len(r) > 7 else None,
                )
            )
        return candles

    def get_tick(self, symbol: str) -> dict[str, Any]:
        if not self.is_connected():
            raise MarketDataProviderError("not connected")
        info = mt5.symbol_info_tick(symbol.upper())
        if info is None:
            err = mt5.last_error()
            raise MarketDataProviderError(f"symbol_info_tick failed: {err}")
        return {
            "symbol": symbol.upper(),
            "bid": float(info.bid),
            "ask": float(info.ask),
            "spread": float(info.ask - info.bid) if info.ask and info.bid else None,
            "time": datetime.fromtimestamp(info.time, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
            "volume": getattr(info, "volume", None),
        }