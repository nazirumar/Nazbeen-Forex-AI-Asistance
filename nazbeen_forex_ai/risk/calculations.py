"""Trading calculations: risk, position sizing, RR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class SymbolSpec:
    symbol: str
    contract_size: float = 100000.0  # standard lot units? usually 100000 for major FX
    tick_size: float = 0.00001
    pip_size: float = 0.00010  # 1 pip = 10 ticks for 5-decimal
    min_lot: float = 0.01
    max_lot: float = 100.0
    lot_step: float = 0.01
    spread_cost_pips: float = 0.0


def get_symbol_spec(symbol: str | None) -> SymbolSpec:
    s = (symbol or "EURUSD").upper()
    # basic defaults; can be extended
    if s in ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF"):
        pip_size = 0.0001 if s != "USDJPY" else 0.01
        tick_size = pip_size / 10
        return SymbolSpec(symbol=s, contract_size=100000.0, tick_size=tick_size, pip_size=pip_size)
    return SymbolSpec(symbol=s)


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
    symbol_spec: SymbolSpec,
    lot_precision: int = 2,
) -> float:
    if account_balance <= 0 or risk_percent <= 0 or sl == entry:
        return 0.0
    risk_amount = account_balance * (risk_percent / 100.0)
    if entry < sl:
        pip_risk = (sl - entry) / symbol_spec.pip_size
    else:
        pip_risk = (entry - sl) / symbol_spec.pip_size
    if pip_risk <= 0:
        return 0.0
    # risk per lot in account currency approx: pip_value_per_lot
    pip_value_per_lot = (symbol_spec.contract_size * symbol_spec.pip_size) / entry if entry > 0 else 0
    lot = risk_amount / (pip_risk * pip_value_per_lot) if (pip_risk * pip_value_per_lot) > 0 else 0
    # clamp and step
    lot = round(lot / symbol_spec.lot_step) * symbol_spec.lot_step
    if lot < symbol_spec.min_lot:
        lot = 0.0
    if lot > symbol_spec.max_lot:
        lot = symbol_spec.max_lot
    return round(lot, lot_precision)
