"""MT5 UTC normalization tests (Phase 11A workstream 11A.5).

Pure-function coverage of the evidence-based broker offset handling — no MT5
terminal required. Covers multiple timezone/broker-offset scenarios, pinned
vs auto offset resolution, and rejection of impossible future timestamps.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from nazbeen_forex_ai.marketdata.mt5_connector import (
    MT5MarketDataProvider,
    compute_offset_seconds,
    normalize_mt5_epoch,
    reject_future_candles,
)
from nazbeen_forex_ai.marketdata.providers import Candle, MarketDataProviderError

UTC = timezone.utc


def test_compute_offset_seconds_is_evidence_based() -> None:
    """Offset = server epoch − true UTC epoch (measured, never assumed)."""
    utc_now = datetime(2026, 10, 9, 17, 30, tzinfo=UTC)
    server_ahead = utc_now + timedelta(hours=3)
    assert compute_offset_seconds(server_ahead.timestamp(), utc_now.timestamp()) == pytest.approx(3 * 3600)
    assert compute_offset_seconds(utc_now.timestamp(), utc_now.timestamp()) == pytest.approx(0.0)


@pytest.mark.parametrize("offset_hours", [0, 2, 3, -5, -3.5])
def test_normalize_mt5_epoch_multiple_broker_offsets(offset_hours: float) -> None:
    """Server-local epochs map back to the same true UTC instant for any offset."""
    true_utc = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
    server_epoch = true_utc.timestamp() + offset_hours * 3600
    assert normalize_mt5_epoch(server_epoch, offset_hours * 3600) == true_utc


def test_dst_style_offset_change_is_honoured() -> None:
    """A broker switching UTC+3 → UTC+2 (DST) is handled by re-measuring."""
    true_utc = datetime(2026, 10, 9, 17, 45, tzinfo=UTC)
    winter_server = true_utc.timestamp() + 2 * 3600   # UTC+2 (winter)
    summer_server = true_utc.timestamp() + 3 * 3600   # UTC+3 (summer/DST)
    assert normalize_mt5_epoch(summer_server, 3 * 3600) == true_utc
    assert normalize_mt5_epoch(winter_server, 2 * 3600) == true_utc
    # Applying the wrong seasonal offset leaves the candle wrong — this is why
    # the default mode re-measures rather than pinning a fixed value.
    assert normalize_mt5_epoch(summer_server, 2 * 3600) != true_utc


def test_unapplied_offset_shows_future_drift() -> None:
    """Demonstrates the CRIT-05 symptom: +3h server stamped as UTC is in the future."""
    now = datetime(2026, 10, 9, 17, 33, tzinfo=UTC)
    server_bar = (now + timedelta(hours=3)).timestamp()
    naive = normalize_mt5_epoch(server_bar, offset_seconds=0.0)
    assert naive > now  # future candle — the audit's observed bug
    fixed = normalize_mt5_epoch(server_bar, 3 * 3600)
    assert fixed <= now


def test_pinned_numeric_offset_used_directly() -> None:
    p = MT5MarketDataProvider(utc_offset_hours="2")
    assert p._resolve_offset_seconds() == pytest.approx(2 * 3600)
    p2 = MT5MarketDataProvider(utc_offset_hours=-3.5)
    assert p2._resolve_offset_seconds() == pytest.approx(-3.5 * 3600)


def test_auto_offset_without_terminal_falls_back_to_zero() -> None:
    """No MT5 module/symbol evidence → offset 0 with no crash (CI-safe)."""
    p = MT5MarketDataProvider(utc_offset_hours="auto")
    assert p._resolve_offset_seconds("EURUSD") == 0.0


def test_reject_future_candles_raises() -> None:
    now = datetime(2026, 10, 9, 17, 0, tzinfo=UTC)
    future = Candle(time=now + timedelta(hours=3), open=1.1, high=1.11, low=1.09, close=1.1)
    with pytest.raises(MarketDataProviderError, match="impossible future candle"):
        reject_future_candles([future], now=now)


def test_reject_future_candles_allows_current_forming_bar() -> None:
    now = datetime(2026, 10, 9, 17, 0, tzinfo=UTC)
    forming = Candle(time=now - timedelta(minutes=10), open=1.1, high=1.11, low=1.09, close=1.1)
    past = Candle(time=now - timedelta(hours=2), open=1.1, high=1.11, low=1.09, close=1.1)
    reject_future_candles([past, forming], now=now)  # must not raise


def test_reject_future_candles_boundary_tolerance() -> None:
    """Within-tolerance future timestamps pass; beyond tolerance are rejected."""
    now = datetime(2026, 10, 9, 17, 0, tzinfo=UTC)
    just_inside = Candle(time=now + timedelta(minutes=4), open=1.1, high=1.11, low=1.09, close=1.1)
    reject_future_candles([just_inside], now=now, tolerance_sec=300)
    just_outside = Candle(time=now + timedelta(minutes=6), open=1.1, high=1.11, low=1.09, close=1.1)
    with pytest.raises(MarketDataProviderError):
        reject_future_candles([just_outside], now=now, tolerance_sec=300)
