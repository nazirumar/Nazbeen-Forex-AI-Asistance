# PHASE 11A — Fix Verification (issue-by-issue)

**Verified:** 2026-10-09 · Every status below is backed by an executed test (test name given) or
a live measurement. Claims without evidence are marked *not verified*. The Phase 10 audit record
in `CRITICAL_ISSUES.md` is preserved unchanged; this file only reports remediation state.

**Legend:** ✅ resolved · 🟡 partially resolved (remainder tracked for 11B) · ⛔ open (not in 11A scope).

## CRITICAL

| ID | Status | Evidence |
|---|---|---|
| CRIT-01 Backtest dummy outcomes + ignored costs | ✅ | `backtesting/tests/test_engine_simulation.py` (10 tests): real SL/TP simulation (`test_winner_trade_hits_take_profit` pnl 200 = price×100000, `test_loser_trade_hits_stop_loss` −100), both-touched→SL (`test_both_sl_and_tp_in_one_candle_assumes_sl_first`), costs (`test_costs_reduce_pnl_deterministically`: 200→110, exactly 9 pips×$10), position-aware PnL (×2 lots doubles pnl), honest metrics (win_rate 50 %, profit_factor 2.0, expectancy 50, max_drawdown 100). Migrated repros 13/14 pass with an injected deterministic strategy (`test_bug_backtest_applies_cost_parameters`, `test_bug_backtest_outcomes_are_not_dummy`). |
| CRIT-02 FVG labels inverted + timestamps reversed | ✅ | `structure/tests/test_fvg_rules.py` (7 tests): gap-up→`bullish` levels `[1.1002, 1.1006]`, gap-down→`bearish`, no-gap→`[]`, sub-threshold sliver→`[]` (but detected when `threshold_pips` lowered), overlapping ranges still detected, `start ≤ end`, `formation_time == confirmed_at == end_time > start_time`. Migrated repros 2/3/4 pass. |
| CRIT-03 BOS/CHOCH/MSS stub + orderblocks unimportable | ✅ | Module imports (repro 1). `structure/tests/test_market_structure.py` (10 tests): bullish/bearish BOS with level+index, CHOCH after bullish trend (`trend_before/after`), MSS = CHOCH **with** displacement, invalid break→`[]`, wick-only poke→`[]` (close-confirmation), `confirmed_at == breaking-bar time` and `formation_time ≤ confirmed_at` (no look-ahead), OB bullish/bearish zones with `formation < confirmed`, no-OB-without-displacement. Repro 5 passes. |
| CRIT-04 Suite runs against live MT5 when `.env` says so | ✅ | `settings/test.py` pins `MT5_USE_MOCK = True`. `marketdata/tests/test_audit_regressions.py::test_test_settings_force_mock_provider`, `::test_factory_returns_mock_under_test_settings`, `::test_factory_ignores_contaminating_env` (monkeypatches `MT5_USE_MOCK=false`, still mock), `::test_candles_endpoint_never_uses_live_provider`. Endpoint assertions strengthened to `data_source == "mock"` in `test_marketdata.py` and the e2e workflow. Suite runtime 118 s → 13 s (no terminal I/O). |
| CRIT-05 MT5 timestamps stamped as UTC ≈ +3 h in the future | ✅ | Pure helpers + live evidence. `marketdata/tests/test_utc_normalization.py` (13 tests): offset=0/+2/+3/−5/−3.5 parametrized normalization, DST-style +3→+2 switch, `naive > now` symptom reproduced and `fixed ≤ now`, pinned numeric offset, auto-fallback=0 without terminal, future rejection ×3 (raise / forming-bar allowed / tolerance boundary). **Live run:** auto-measured offset `+3.0002 h` from a real tick vs host UTC; tick stamped `…19:10:18Z` == host UTC; latest M15 candle age 11.6 min **in the past**; `any future candles: False`. |

## HIGH

| ID | Status | Evidence |
|---|---|---|
| H-01 Upload validation disabled | ✅ | `analysis/tests/test_audit_regressions.py` (4): non-image content→400 (was 201), 6 MB→400 (was 201), `.svg` extension→400, wrong content-type→400. Validators decode real bytes via Pillow (`verify()`) and match decoded format to extension; the view returns 400 with `details` instead of `except: pass`. |
| H-02 Screenshots never persisted / `MEDIA_ROOT` undefined | ⛔ | Not in 11A scope. |
| H-03 LangGraph & real LLM providers missing while claimed | ⛔ | Owner decision pending (implement vs amend spec). |
| H-04 Fabrication guard depends on `data_synchronized` | ⛔ | 11B (analysis-services authority). |
| H-05 mtf_bias inverted; conflicts stubbed; LLM not subordinated | 🟡 | Bias heuristic fixed: `structure/analysis.py` compares consecutive confirmed swings (HH/LH/HL/LL); repro 6 passes (`M15 == BULLISH` on rising fixture). **Remainder open:** empty `mtf_conflicts` list and deterministic-engine authority over the LLM → 11B. |
| H-06 Pip value wrong for USD-quoted pairs (10 % over-risk) | ✅ | Repro 9: EURUSD 1 % of $10 000 / 10-pip stop = **1.00 lot** exactly (was 1.1). `test_position_sizing.py`: EURUSD $10/pip/lot constant across prices; USDJPY `1000 JPY ÷ rate` (6.667 at 150.00) and sizing 1.50 lots; `None`-spec/zero-risk→0; all 7 registry symbols have complete metadata. |
| H-07 Frontend login token discarded before `/me` | ⛔ | Frontend (11B+), not covered by pytest/CI. |
| H-08 Required dashboard missing | ⛔ | 11B+. |
| H-09 Live MT5 path: dead credentials, no suffix, no staleness | 🟡 | Timestamps + future rejection + `symbol_select` guard added (live-tested); 13 pure-function connector tests now exist. **Remainder open:** env-credential wiring in factory, symbol-suffix handling, closure/staleness checks. |
| H-10 Docs claims contradicted by code | ⛔ | Errata pass scheduled for 11B doc updates (audit artifacts stay untouched). |

## MEDIUM

| ID | Status | Evidence |
|---|---|---|
| M-01 Mock tick `NameError: utcnow` → 500 | ✅ | `datetime.now(timezone.utc)`; repro 7 passes; covered by mock endpoint tests. |
| M-02 Unknown timeframe silently returns M15 | ✅ | `MockMarketDataProvider.get_candles` raises `MarketDataProviderError`; repro 8 passes (`pytest.raises`). |
| M-03 `count` unbounded / `count=abc` → 500 | ⛔ | Serializer validation → 11B. |
| M-04 Inverted provider-mode label in error path | ⛔ | 11B. |
| M-05 trade-plan NaN → 500, exception text leak | 🟡 | `evaluate_trade_plan` now rejects non-finite entry/sl/tp and unknown symbols with `WAIT` (`scenarios.py`). **Remainder open:** request serializer, negative-risk bounds, provider-exception redaction → 11B. |
| M-06 Unknown symbols get fabricated specs | ✅ | `get_symbol_spec → None` for unregistered symbols; `position_size(None) == 0`; plan → `WAIT` with reason. Repro 10 passes (fixed-API form); `test_unknown_symbol_metadata_rejected_not_fabricated`. |
| M-07 Walk-forward `overall` not an aggregation (+ P-02 leakage, stale signals) | 🟡 | `overall = summarize_trades(all_trades)`; repro 15 passes (`overall == Σ windows` and net_profit == Σ pnl, with injected strategy so the check is non-vacuous); stale-signal reuse impossible (loop jumps past exit). **Remainder open:** train==test fallback (P-02), chronological-sort validation → 11B. |
| M-08 `run_backtest` default params (future spawn) | ⛔ | 11B. |
| M-09 9+ spec detectors missing (equal highs/lows, liquidity, sweep…) | ⛔ | 11B — out of 11A scope (11A repairs existing detectors only). Equal-highs/equal-lows P-01 also 11B. |
| M-10 No `confirmed_at` distinction on structure events | 🟡 | `StructureEvent.formation_time`/`confirmed_at` added and stamped for FVG, BOS/CHOCH/MSS, order blocks (tests assert `formation ≤ confirmed`, `confirmed == breaking/confirming bar`). **Remainder open:** `liquidity.py` and `swings.py` events. |
| M-11…M-16 (per-item API/error/UX defects) | ⛔ | Not in 11A scope. |

## LOW

L-01…L-07 — ⛔ open, none in 11A scope.

## Repro artifact suite (docs/audits/repro)

| At audit time | After Phase 11A |
|---|---|
| **15/15 FAIL** (15 confirmed bugs) | **15/15 PASS** (run: `uv run pytest docs/audits/repro -q`) |

Migration adaptations (documented in both files): repro 10 asserts the fixed API
(`spec is None` + `WAIT`); repros 13/14/15 inject a deterministic strategy because the corrected
detectors form no FVG setups on smooth sawtooth data — the assertions themselves are unchanged.

## Main suite

`uv run pytest` → **145 passed** (78 pre-11A baseline + 67 new) ·
`manage.py check` → 0 issues · `makemigrations --check --dry-run` → no changes ·
CI parity maintained.

## Not verified in this environment

Docker image builds, live PostgreSQL/Redis, real LLM calls, `mt5_worker` (scaffold), frontend
behaviour. Live-MT5 evidence above is from this machine only (MetaQuotes-Demo); the offset
re-measures itself per session, so a different broker/timezone is handled without code changes —
but only the +3 h server case was empirically confirmed.
