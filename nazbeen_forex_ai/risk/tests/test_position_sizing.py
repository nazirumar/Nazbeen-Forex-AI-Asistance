"""Position sizing and pip-value tests (Phase 11A workstream 11A.7).

Covers EURUSD (USD-quoted, constant pip value), USDJPY (quote currency ≠
account currency, converted at the current rate), and invalid/unknown symbol
metadata (rejected, never fabricated).
"""

from __future__ import annotations

import pytest

from nazbeen_forex_ai.risk.calculations import (
    get_symbol_spec,
    pip_value_per_lot,
    position_size,
)


def test_eurusd_pip_value_per_lot_is_ten_usd() -> None:
    spec = get_symbol_spec("EURUSD")
    assert spec is not None
    assert spec.quote_currency == "USD"
    assert spec.contract_size == 100000.0
    assert spec.tick_size == 0.00001
    assert spec.pip_size == 0.0001
    # 1 pip = 10 ticks × $1 tick value = $10/pip/lot, independent of price.
    assert pip_value_per_lot(spec, 1.1000) == pytest.approx(10.0)
    assert pip_value_per_lot(spec, 1.2700) == pytest.approx(10.0)


def test_eurusd_position_size_zero_when_spec_unknown_or_zero_risk() -> None:
    spec = get_symbol_spec("EURUSD")
    assert position_size(10000.0, 1.0, 1.1000, 1.1000, spec) == 0.0        # sl == entry
    assert position_size(0.0, 1.0, 1.1000, 1.0990, spec) == 0.0            # no balance
    assert position_size(10000.0, 1.0, 1.1000, 1.0990, None) == 0.0        # no spec


def test_usdjpy_pip_value_converts_quote_to_account() -> None:
    """USDJPY pip value is 1000 JPY/lot → divided by the USDJPY rate."""
    spec = get_symbol_spec("USDJPY")
    assert spec is not None
    assert spec.quote_currency == "JPY"
    assert spec.pip_size == 0.01
    assert spec.tick_size == 0.001
    # 100000 × 0.01 = 1000 JPY/pip/lot; at 150.00 → 6.667 USD/pip/lot.
    assert pip_value_per_lot(spec, 150.00) == pytest.approx(1000.0 / 150.0)
    assert pip_value_per_lot(spec, 150.00) == pytest.approx(6.6667, rel=1e-4)


def test_usdjpy_position_size_uses_rate_adjusted_pip_value() -> None:
    """$100 risk, 10-pip stop at 150.00 → 100 / (10 × 6.6667) = 1.50 lots."""
    spec = get_symbol_spec("USDJPY")
    lots = position_size(
        account_balance=10000.0, risk_percent=1.0, entry=150.00, sl=149.90, symbol_spec=spec
    )
    assert lots == pytest.approx(1.5, abs=0.011)  # 1.50 after lot-step rounding


def test_unknown_symbol_metadata_rejected_not_fabricated() -> None:
    for symbol in ("XAUUSD", "BTCUSD", "FAKEPAIR"):
        assert get_symbol_spec(symbol) is None, f"{symbol} must be rejected"
    assert position_size(10000.0, 1.0, 2000.0, 1990.0, get_symbol_spec("XAUUSD")) == 0.0


def test_known_symbols_all_have_full_metadata() -> None:
    for symbol in ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "USDJPY"):
        spec = get_symbol_spec(symbol)
        assert spec is not None, f"{symbol} missing from registry"
        assert spec.contract_size > 0
        assert spec.tick_size > 0
        assert spec.pip_size > 0
        assert spec.tick_value == pytest.approx(spec.contract_size * spec.tick_size)
        assert spec.quote_currency
