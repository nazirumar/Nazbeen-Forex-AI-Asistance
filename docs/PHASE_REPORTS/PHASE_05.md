# PHASE 05 — Trading Scenario and Risk Management Engine: Completion Report

**Phase:** 5 (Trading Scenario and Risk Management Engine)  
**Date:** 2026-10-08  
**Status:** ✅ Complete — awaiting approval before next phase

## 1. Goal

Implement scenario evaluation (bullish/bearish/WAIT), MTF-aware logic hooks, entry zones, SL/TP, RR, position sizing, spread/volatility/session filters, confluence scoring kept separate from statistical probability, explanations for rejections, analysis-only.

## 2. What was built

### Risk app (`nazbeen_forex_ai/risk/`)
- `calculations.py`: Symbol specs, tick rounding, RR (math consistent for long/short), position sizing with lot clamping/steps.
- `filters.py`: Spread check, basic session/volatility helpers.
- `scenarios.py`: `evaluate_trade_plan` — validates levels, enforces SL/Entry/TP consistency per direction, checks RR, spread, computes lot size, tracks evidence/reasons/warnings; confluence_score separate.
- `services.py`: `create_trade_plan` wrapper.
- `views.py`: `TradePlanView` (POST, auth) returns structured plan; never places orders.
- `urls.py`: `/api/risk/trade-plan/`.
- `tests/test_risk.py`: Calculations, valid/invalid plans, edge cases.

### Integration
- Added to INSTALLED_APPS, mounted URLs.

### Safety
- Invalid setups -> WAIT with reasons; missing data -> WAIT; excessive spread -> WAIT; neutral -> WAIT.
- Confluence scores not presented as calibrated probabilities.

### Tests
- 9 risk tests; full suite **59 passed**.

## 3. Verification
| Check | Result |
|---|---|
| `uv run pytest` | 59 passed |

## 4. Next phase
Await approval.
