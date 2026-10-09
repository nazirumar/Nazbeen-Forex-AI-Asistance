"""Migrated audit regression tests — risk subsystem (Phase 11A).

Source: docs/audits/repro/test_audit_regressions.py (EURUSD pip-value math,
unknown-symbol fabrication). The unknown-symbol assertion is expressed against
the fixed API: unregistered symbols return None and force WAIT.
"""

from __future__ import annotations

from nazbeen_forex_ai.risk.calculations import get_symbol_spec, position_size
from nazbeen_forex_ai.risk.scenarios import evaluate_trade_plan


def test_bug_position_size_eurusd_exact() -> None:
    """H-06: pip value divided by entry for USD-quoted pairs (over-risking).

    $10,000 balance, 1% risk (= $100), 10-pip stop on EURUSD must be exactly
    1.00 lot: 100 / (10 pips × $10/pip/lot). Actual before fix: 1.1 lots
    (+10% over-risk; +27% at entry 1.27).
    """
    spec = get_symbol_spec("EURUSD")
    lots = position_size(
        account_balance=10000.0, risk_percent=1.0, entry=1.1000, sl=1.0990, symbol_spec=spec
    )
    assert lots == 1.0, f"expected 1.0 lots, got {lots}"


def test_bug_unknown_symbol_yields_wait_not_fabricated_spec() -> None:
    """M-06: symbols outside the registry silently received EURUSD-like specs.

    Actual before fix: XAUUSD (contract 100, pip 0.1) was sized with
    contract_size=100000 / pip 0.0001. Correct behavior: reject the symbol and
    return WAIT — never fabricate contract data.
    """
    spec = get_symbol_spec("XAUUSD")
    assert spec is None, (
        f"XAUUSD must be rejected (None), got fabricated spec: {spec!r}"
    )

    # position sizing refuses to fabricate a lot size for unknown specs.
    assert position_size(10000.0, 1.0, 2000.0, 1999.0, spec) == 0.0

    # and the trade plan degrades to WAIT instead of sizing a position.
    res = evaluate_trade_plan(
        bias="BULLISH",
        entry=2000.0,
        sl=1990.0,
        tp=2030.0,
        spread_pips=0.5,
        symbol="XAUUSD",
        account_balance=10000.0,
    )
    assert res.decision == "WAIT"
    assert any("Unknown symbol" in r for r in res.reasons)
