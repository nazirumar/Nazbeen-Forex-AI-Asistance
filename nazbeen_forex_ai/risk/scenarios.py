"""Scenario evaluation: BUY/SELL/WAIT with evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal

from nazbeen_forex_ai.risk.calculations import (
    calculate_rr,
    get_symbol_spec,
    position_size,
    round_to_tick,
)


@dataclass
class ScenarioConfig:
    risk_percent: float = 1.0
    max_spread_pips: float = 2.0
    min_rr: float = 0.5
    confluence_weight: float = 0.0


@dataclass
class ScenarioResult:
    decision: Literal["BUY", "SELL", "WAIT"]
    direction: Literal["bullish", "bearish", "neutral"]
    entry_levels: List[float] = field(default_factory=list)
    sl: float | None = None
    tp: float | None = None
    rr: float | None = None
    lot_size: float = 0.0
    risk_percent: float = 0.0
    confluence_score: float = 0.0
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def evaluate_trade_plan(
    bias: str | None = None,
    entry: float | None = None,
    sl: float | None = None,
    tp: float | None = None,
    spread_pips: float | None = None,
    symbol: str | None = "EURUSD",
    account_balance: float = 10000.0,
    config: ScenarioConfig | None = None,
    evidence: List[Dict[str, Any]] | None = None,
) -> ScenarioResult:
    config = config or ScenarioConfig()
    evidence = evidence or []
    reasons: List[str] = []
    warnings: List[str] = []

    if not entry or not sl or not tp:
        reasons.append("Missing entry/sl/tp")
        return ScenarioResult(
            decision="WAIT",
            direction="neutral",
            entry_levels=[entry] if entry else [],
            sl=sl,
            tp=tp,
            reasons=reasons,
            evidence=evidence,
        )

    if sl == entry or tp == entry:
        reasons.append("Invalid price levels")
        return ScenarioResult(decision="WAIT", direction="neutral", reasons=reasons)

    spec = get_symbol_spec(symbol)
    entry_r = round_to_tick(entry, spec.tick_size)
    sl_r = round_to_tick(sl, spec.tick_size)
    tp_r = round_to_tick(tp, spec.tick_size)

    # determine direction
    if bias and "bull" in bias.lower():
        direction = "bullish"
    elif bias and "bear" in bias.lower():
        direction = "bearish"
    else:
        direction = "neutral"

    # basic consistency
    # for bearish, TP below entry, SL above entry
    if direction == "bullish" and not (sl_r < entry_r < tp_r):
        reasons.append("Bullish setup requires SL < Entry < TP")
    if direction == "bearish" and not (tp_r < entry_r < sl_r):
        reasons.append("Bearish setup requires TP < Entry < SL")
    if direction == "neutral" and not reasons:
        reasons.append("Neutral bias cannot form directional trade")

    if reasons:
        return ScenarioResult(
            decision="WAIT",
            direction=direction,
            entry_levels=[entry_r],
            sl=sl_r,
            tp=tp_r,
            reasons=reasons,
            evidence=evidence,
        )

    rr = calculate_rr(entry_r, sl_r, tp_r)
    if rr is None or rr < config.min_rr:
        reasons.append(f"RR below minimum ({rr} < {config.min_rr})")
        return ScenarioResult(
            decision="WAIT",
            direction=direction,
            entry_levels=[entry_r],
            sl=sl_r,
            tp=tp_r,
            rr=rr,
            reasons=reasons,
            evidence=evidence,
        )

    # spread check
    if spread_pips is not None and spread_pips > config.max_spread_pips:
        reasons.append(f"Spread too high ({spread_pips} > {config.max_spread_pips})")
        return ScenarioResult(
            decision="WAIT",
            direction=direction,
            entry_levels=[entry_r],
            sl=sl_r,
            tp=tp_r,
            rr=rr,
            reasons=reasons,
            evidence=evidence,
        )

    lot = position_size(account_balance, config.risk_percent, entry_r, sl_r, spec)
    if lot <= 0:
        warnings.append("Lot size computed as 0 (check balance/risk)")

    decision = "BUY" if direction == "bullish" else "SELL" if direction == "bearish" else "WAIT"
    if direction == "neutral":
        decision = "WAIT"

    return ScenarioResult(
        decision=decision,
        direction=direction,
        entry_levels=[entry_r],
        sl=sl_r,
        tp=tp_r,
        rr=rr,
        lot_size=lot,
        risk_percent=config.risk_percent,
        confluence_score=0.0,  # keep separate from probability
        evidence=evidence,
        reasons=reasons,
        warnings=warnings,
    )
