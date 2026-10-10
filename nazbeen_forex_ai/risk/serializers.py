"""Trade-plan request validation (audit M-05, fix P1.6).

Strict, fail-fast checks so malformed input returns **400** with safe messages
instead of a 500 (NaN/inf propagation, ``float("abc")`` crashes) — and never a
BUY with fabricated/invalid numbers. Semantic ordering checks (SL/TP side)
belong to the scenario engine, which answers WAIT with reasons.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, Optional

from django.core.exceptions import ValidationError

# Bounds: analysis-only sanity limits, documented in the API error messages.
MAX_RISK_PERCENT = 10.0
MAX_SPREAD_PIPS = 100.0
MAX_MIN_RR = 100.0
MAX_BALANCE = 1e12
MAX_PRICE = 1e12
SYMBOL_RE = re.compile(r"^[A-Za-z0-9._/]{1,32}$")
BIAS_VALUES = {"bullish", "bearish", "neutral"}


def _finite_float(value: Any, field: str, default: Optional[float] = None) -> Optional[float]:
    if value == "":
        raise ValidationError(f"{field} must be a number.")
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be a number.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a number.")
    if not math.isfinite(number):
        raise ValidationError(f"{field} must be a finite number.")
    return number


def _bounded(number: Optional[float], field: str, low: float, high: float, default: float) -> float:
    value = default if number is None else number
    if not (low < value <= high):
        raise ValidationError(f"{field} must be > {low} and <= {high}.")
    return value


def validate_trade_plan_request(data: Any) -> Dict[str, Any]:
    """Return a cleaned payload or raise ``ValidationError`` (400-safe)."""
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object.")

    cleaned: Dict[str, Any] = {}

    risk_percent = _finite_float(data.get("risk_percent"), "risk_percent", default=1.0)
    cleaned["risk_percent"] = _bounded(risk_percent, "risk_percent", 0.0, MAX_RISK_PERCENT, 1.0)

    max_spread = _finite_float(data.get("max_spread_pips"), "max_spread_pips", default=2.0)
    if max_spread is None or not (0.0 <= max_spread <= MAX_SPREAD_PIPS):
        raise ValidationError(f"max_spread_pips must be >= 0 and <= {MAX_SPREAD_PIPS}.")
    cleaned["max_spread_pips"] = max_spread

    min_rr = _finite_float(data.get("min_rr"), "min_rr", default=0.5)
    cleaned["min_rr"] = _bounded(min_rr, "min_rr", 0.0, MAX_MIN_RR, 0.5)

    balance = _finite_float(data.get("account_balance"), "account_balance", default=10000.0)
    cleaned["account_balance"] = _bounded(balance, "account_balance", 0.0, MAX_BALANCE, 10000.0)

    spread = _finite_float(data.get("spread_pips"), "spread_pips", default=None)
    if spread is not None and not (0.0 <= spread <= 10000.0):
        raise ValidationError("spread_pips must be >= 0 and <= 10000.")
    cleaned["spread_pips"] = spread

    # Price levels: optional here (missing levels answer WAIT downstream), but
    # when present they must be finite positive numbers.
    for field in ("entry", "sl", "tp"):
        number = _finite_float(data.get(field), field, default=None)
        if number is not None and not (0.0 < number <= MAX_PRICE):
            raise ValidationError(f"{field} must be a positive price <= {MAX_PRICE}.")
        cleaned[field] = number

    bias = data.get("bias")
    if bias is not None and bias != "":
        if not isinstance(bias, str) or bias.strip().lower() not in BIAS_VALUES:
            raise ValidationError(
                f"bias must be one of {', '.join(sorted(BIAS_VALUES))} (case-insensitive)."
            )
        cleaned["bias"] = bias.strip().lower()

    symbol = data.get("symbol")
    if symbol is not None and symbol != "":
        if not isinstance(symbol, str) or not SYMBOL_RE.match(symbol.strip()):
            raise ValidationError(
                "symbol must be 1-32 characters of letters, digits, '.', '_' or '/'."
            )
        cleaned["symbol"] = symbol.strip().upper()

    evidence = data.get("evidence")
    if evidence is not None:
        if not isinstance(evidence, list):
            raise ValidationError("evidence must be a list.")
        cleaned["evidence"] = evidence[:50]

    return cleaned
