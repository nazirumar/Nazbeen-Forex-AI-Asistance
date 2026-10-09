"""Trading calculations: risk, position sizing, RR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class SymbolSpec:
    symbol: str
    contract_size: float = 100000.0  # units per standard lot
    tick_size: float = 0.00001
    pip_size: float = 0.00010  # 1 pip = 10 ticks for 5-decimal FX
    tick_value: float = 0.0  # value of one tick move, per lot, in QUOTE currency
    quote_currency: str = "USD"
    min_lot: float = 0.01
    max_lot: float = 100.0
    lot_step: float = 0.01
    spread_cost_pips: float = 0.0


# Known contract specifications. Values reflect standard interbank specs for the
# majors. tick_value is derived as contract_size * tick_size (quote ccy / lot).
def _spec(symbol: str, contract: float, pip: float, tick: float, quote: str) -> SymbolSpec:
    return SymbolSpec(
        symbol=symbol,
        contract_size=contract,
        pip_size=pip,
        tick_size=tick,
        tick_value=contract * tick,
        quote_currency=quote,
    )


_SYMBOL_REGISTRY: dict[str, SymbolSpec] = {
    "EURUSD": _spec("EURUSD", 100000.0, 0.0001, 0.00001, "USD"),
    "GBPUSD": _spec("GBPUSD", 100000.0, 0.0001, 0.00001, "USD"),
    "AUDUSD": _spec("AUDUSD", 100000.0, 0.0001, 0.00001, "USD"),
    "NZDUSD": _spec("NZDUSD", 100000.0, 0.0001, 0.00001, "USD"),
    "USDCAD": _spec("USDCAD", 100000.0, 0.0001, 0.00001, "CAD"),
    "USDCHF": _spec("USDCHF", 100000.0, 0.0001, 0.00001, "CHF"),
    "USDJPY": _spec("USDJPY", 100000.0, 0.01, 0.001, "JPY"),
}


def get_symbol_spec(symbol: str | None) -> Optional[SymbolSpec]:
    """Return the contract spec for a known symbol, or ``None`` for unknown ones.

    Unknown symbols are **rejected**, never silently given fabricated
    EURUSD-like specs (audit H-06 / M-06). Callers must treat ``None`` as WAIT.
    """
    s = (symbol or "EURUSD").upper()
    return _SYMBOL_REGISTRY.get(s)


def pip_value_per_lot(spec: SymbolSpec, price: float, account_currency: str = "USD") -> float:
    """Value of a 1-pip move, per standard lot, in the account currency.

    Uses the symbol's tick_value and tick/pip sizes. When the quote currency
    differs from the account currency (e.g. USDJPY quoted in JPY), the current
    price converts quote→account. For USD-quoted majors the value is constant.
    """
    if spec.pip_size <= 0 or spec.tick_size <= 0:
        return 0.0
    pip_value_quote = spec.tick_value * (spec.pip_size / spec.tick_size)
    if spec.quote_currency == account_currency:
        return pip_value_quote
    if price and price > 0:
        return pip_value_quote / price
    return 0.0


def round_to_tick(price: float, tick_size: float) -> float:
    if tick_size <= 0:
        return price
    steps = round(price / tick_size)
    return round(steps * tick_size, 10)


def calculate_rr(entry: float, sl: float, tp: float) -> float | None:
    if sl == entry:
        return None
    # long: entry > sl and tp > entry
    if sl < entry < tp:
        risk = entry - sl
        reward = tp - entry
    # short: entry < sl and tp < entry
    elif tp < entry < sl:
        risk = sl - entry
        reward = entry - tp
    else:
        return None
    if risk <= 0 or reward <= 0:
        return None
    return round(reward / risk, 2)


def position_size(
    account_balance: float,
    risk_percent: float,
    entry: float,
    sl: float,
    symbol_spec: SymbolSpec | None,
    lot_precision: int = 2,
) -> float:
    if symbol_spec is None:
        # Unknown contract spec — never fabricate a size.
        return 0.0
    if account_balance <= 0 or risk_percent <= 0 or sl == entry:
        return 0.0
    risk_amount = account_balance * (risk_percent / 100.0)
    pip_risk = abs(entry - sl) / symbol_spec.pip_size
    if pip_risk <= 0:
        return 0.0
    # Correct, quote-currency-aware pip value per lot (audit H-06).
    pip_value = pip_value_per_lot(symbol_spec, entry)
    if pip_value <= 0:
        return 0.0
    lot = risk_amount / (pip_risk * pip_value)
    # clamp and step
    lot = round(lot / symbol_spec.lot_step) * symbol_spec.lot_step
    if lot < symbol_spec.min_lot:
        lot = 0.0
    if lot > symbol_spec.max_lot:
        lot = symbol_spec.max_lot
    return round(lot, lot_precision)
