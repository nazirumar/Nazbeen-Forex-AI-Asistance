"""MT5 connector + factory tests (Phase 11C — audit H-09, fix P1.8).

Contract (mocked connector — no terminal, no network):
- A configured broker symbol suffix is resolved: bare symbol first, suffixed
  fallback when the broker does not offer the bare name.
- The factory wires the previously-dead `marketdata.settings` configuration
  (path/login/server/password/timeout/retries/suffix) into the provider.
- The test settings still force the mock provider (never a live terminal).
"""

from __future__ import annotations

import time as _time
from types import SimpleNamespace

import pytest
from django.conf import settings

from nazbeen_forex_ai.marketdata import settings as md_settings
from nazbeen_forex_ai.marketdata import mt5_connector
from nazbeen_forex_ai.marketdata.factory import get_market_data_provider
from nazbeen_forex_ai.marketdata.mock import MockMarketDataProvider
from nazbeen_forex_ai.marketdata.mt5_connector import MT5MarketDataProvider
from nazbeen_forex_ai.marketdata.providers import MarketDataProviderError


# ---------------------------------------------------------------------------
# Fake MetaTrader5 module (injected in place of the real `mt5` module)
# ---------------------------------------------------------------------------

class FakeMt5:
    """Minimal stand-in for the MetaTrader5 module, recording every call."""

    TIMEFRAME_M1 = 1
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_H1 = 60

    def __init__(self, available: set[str], rates):
        self.available = available
        self.rates = rates
        self.calls: list[tuple] = []
        self.selected: list[str] = []

    def initialize(self, **kwargs) -> bool:
        self.calls.append(("initialize",))
        return True

    def shutdown(self) -> None:
        self.calls.append(("shutdown",))

    def terminal_info(self):
        return SimpleNamespace(name="FakeTerminal")

    def account_info(self):
        return SimpleNamespace(login=12345, server="FakeServer", name="Trader")

    def symbol_select(self, name: str, force: bool = False) -> bool:
        self.calls.append(("symbol_select", name))
        self.selected.append(name)
        return name in self.available

    def copy_rates_from_pos(self, symbol: str, timeframe, start: int, count: int):
        self.calls.append(("copy_rates_from_pos", symbol, timeframe, start, count))
        return self.rates

    def copy_rates_from(self, symbol: str, timeframe, start, count):
        self.calls.append(("copy_rates_from", symbol, timeframe, start, count))
        return self.rates

    def symbol_info_tick(self, symbol: str):
        self.calls.append(("symbol_info_tick", symbol))
        return SimpleNamespace(time=int(_time.time()) - 60, bid=1.1000, ask=1.1002, volume=1)

    def last_error(self):
        return (0, "ok")


def _rows(n: int = 3) -> list[tuple]:
    now = int(_time.time())
    base = 1.1000
    rows = []
    for i in range(n):
        epoch = now - (n - i) * 60
        o = base + i * 0.0001
        c = o + 0.00005
        rows.append((epoch, o, c + 0.0002, o - 0.0002, c, 10, 2, 1))
    return rows


@pytest.fixture
def fake_mt5(monkeypatch):
    def install(available: set[str], rates=None):
        fake = FakeMt5(available, _rows() if rates is None else rates)
        monkeypatch.setattr(mt5_connector, "mt5", fake)
        # TIMEFRAME_MAP was built at import time from the real module; keep the
        # connector's map populated for the fake.
        monkeypatch.setattr(
            mt5_connector,
            "TIMEFRAME_MAP",
            {
                "M1": FakeMt5.TIMEFRAME_M1,
                "M5": FakeMt5.TIMEFRAME_M5,
                "M15": FakeMt5.TIMEFRAME_M15,
                "H1": FakeMt5.TIMEFRAME_H1,
            },
            raising=False,
        )
        return fake

    return install


# ---------------------------------------------------------------------------
# Symbol-suffix resolution (H-09)
# ---------------------------------------------------------------------------

def test_suffix_used_when_bare_symbol_unavailable(fake_mt5) -> None:
    # Suffix is appended exactly as configured (MT5 symbol names are
    # case-sensitive as the broker defines them).
    fake = fake_mt5({"EURUSD.pro"})
    provider = MT5MarketDataProvider(symbol_suffix=".pro", utc_offset_hours="0")
    assert provider.connect() is True

    candles = provider.get_candles(symbol="EURUSD", timeframe="M1", count=3)

    assert len(candles) == 3
    copy_calls = [c for c in fake.calls if c[0] == "copy_rates_from_pos"]
    assert copy_calls and copy_calls[0][1] == "EURUSD.pro", (
        "configured suffix must be applied when the broker lacks the bare symbol"
    )
    assert candles[0].time.tzinfo is not None  # UTC normalization still applies


def test_bare_symbol_preferred_when_available(fake_mt5) -> None:
    fake = fake_mt5({"EURUSD", "EURUSD.pro"})
    provider = MT5MarketDataProvider(symbol_suffix=".pro", utc_offset_hours="0")
    provider.connect()

    provider.get_candles(symbol="EURUSD", timeframe="M1", count=2)

    copy_calls = [c for c in fake.calls if c[0] == "copy_rates_from_pos"]
    assert copy_calls[0][1] == "EURUSD", "bare symbol must be tried first"


def test_no_suffix_configured_uses_requested_name(fake_mt5) -> None:
    fake = fake_mt5({"EURUSD"})
    provider = MT5MarketDataProvider(symbol_suffix="", utc_offset_hours="0")
    provider.connect()

    provider.get_candles(symbol="EURUSD", timeframe="M1", count=2)

    copy_calls = [c for c in fake.calls if c[0] == "copy_rates_from_pos"]
    assert copy_calls[0][1] == "EURUSD"


def test_unresolvable_symbol_falls_back_to_requested_name(fake_mt5) -> None:
    """No candidate confirmed → the requested name is used so the caller
    surfaces the underlying provider error — never a fabricated symbol."""
    fake = fake_mt5(set())
    provider = MT5MarketDataProvider(symbol_suffix=".pro", utc_offset_hours="0")
    provider.connect()

    provider.get_candles(symbol="EURUSD", timeframe="M1", count=2)

    copy_calls = [c for c in fake.calls if c[0] == "copy_rates_from_pos"]
    assert copy_calls[0][1] == "EURUSD"
    # suffix candidate was attempted (appended exactly as configured)
    assert "EURUSD.pro" in fake.selected


def test_suffix_applied_to_tick_lookup(fake_mt5) -> None:
    fake = fake_mt5({"EURUSD.pro"})
    provider = MT5MarketDataProvider(symbol_suffix=".pro", utc_offset_hours="0")
    provider.connect()

    tick = provider.get_tick(symbol="EURUSD")

    assert tick["symbol"] == "EURUSD.pro"
    assert isinstance(tick["bid"], float)
    assert tick["time"].endswith("Z")  # UTC normalization applied


# ---------------------------------------------------------------------------
# Connector guards
# ---------------------------------------------------------------------------

def test_unsupported_timeframe_raises(fake_mt5) -> None:
    fake_mt5({"EURUSD"})
    provider = MT5MarketDataProvider(utc_offset_hours="0")
    provider.connect()
    with pytest.raises(MarketDataProviderError, match="unsupported timeframe"):
        provider.get_candles(symbol="EURUSD", timeframe="M30", count=5)


def test_not_connected_raises() -> None:
    provider = MT5MarketDataProvider()
    with pytest.raises(MarketDataProviderError, match="not connected"):
        provider.get_candles(symbol="EURUSD", timeframe="M1", count=5)


def test_connection_info_reports_mt5_mode(fake_mt5) -> None:
    fake_mt5({"EURUSD"})
    provider = MT5MarketDataProvider(utc_offset_hours="0")
    provider.connect()
    info = provider.get_connection_info()
    assert info["mode"] == "mt5"
    assert info["connected"] is True


# ---------------------------------------------------------------------------
# Factory wiring (H-09: env config was dead)
# ---------------------------------------------------------------------------

def test_factory_wires_env_config_into_mt5_provider(monkeypatch) -> None:
    monkeypatch.setenv("MT5_USE_MOCK", "false")
    monkeypatch.setattr(settings, "MT5_USE_MOCK", False)
    monkeypatch.setattr(md_settings, "MT5_PATH", "C:/mt5/terminal64.exe")
    monkeypatch.setattr(md_settings, "MT5_LOGIN", 12345)
    monkeypatch.setattr(md_settings, "MT5_SERVER", "Broker-Demo")
    monkeypatch.setattr(md_settings, "MT5_PASSWORD", "not-a-real-password")
    monkeypatch.setattr(md_settings, "MT5_TIMEOUT_SEC", 42)
    monkeypatch.setattr(md_settings, "MT5_RETRY_MAX", 7)
    monkeypatch.setattr(md_settings, "MT5_RETRY_BACKOFF", 1.5)
    monkeypatch.setattr(md_settings, "MT5_SYMBOL_SUFFIX", ".pro")

    provider = get_market_data_provider()

    assert isinstance(provider, MT5MarketDataProvider)
    assert provider._path == "C:/mt5/terminal64.exe"
    assert provider._login == 12345
    assert provider._server == "Broker-Demo"
    assert provider._password == "not-a-real-password"
    assert provider._timeout_sec == 42
    assert provider._max_retries == 7
    assert provider._retry_backoff == 1.5
    assert provider._symbol_suffix == ".pro"


def test_factory_still_returns_mock_under_test_settings(monkeypatch) -> None:
    """settings.MT5_USE_MOCK=True (test) wins over a false env value — the
    suite never constructs a live-terminal provider."""
    monkeypatch.setenv("MT5_USE_MOCK", "false")
    assert isinstance(get_market_data_provider(), MockMarketDataProvider)
    assert settings.MT5_USE_MOCK is True
