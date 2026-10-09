"""Risk service combining filters and scenarios."""

from __future__ import annotations

from typing import Any, Dict

from nazbeen_forex_ai.risk.scenarios import (
    ScenarioConfig,
    ScenarioResult,
    evaluate_trade_plan,
)
from nazbeen_forex_ai.risk.filters import check_spread, is_market_hours


def create_trade_plan(plan_data: Dict[str, Any]) -> Dict[str, Any]:
    config = ScenarioConfig(
        risk_percent=float(plan_data.get("risk_percent", 1.0)),
        max_spread_pips=float(plan_data.get("max_spread_pips", 2.0)),
        min_rr=float(plan_data.get("min_rr", 0.5)),
    )
    res = evaluate_trade_plan(
        bias=plan_data.get("bias"),
        entry=plan_data.get("entry"),
        sl=plan_data.get("sl"),
        tp=plan_data.get("tp"),
        spread_pips=plan_data.get("spread_pips"),
        symbol=plan_data.get("symbol", "EURUSD"),
        account_balance=float(plan_data.get("account_balance", 10000.0)),
        config=config,
        evidence=plan_data.get("evidence", []),
    )
    return {
        "decision": res.decision,
        "direction": res.direction,
        "entry_levels": res.entry_levels,
        "sl": res.sl,
        "tp": res.tp,
        "rr": res.rr,
        "lot_size": res.lot_size,
        "confluence_score": res.confluence_score,
        "reasons": res.reasons,
        "warnings": res.warnings,
    }
