# PHASE 11A — Critical Correctness Remediation

**Status:** ✅ completed 2026-10-09 — **awaiting owner approval before Phase 11B**
**Scope source:** `docs/audits/RECOMMENDED_FIXES.md` + `docs/audits/PHASE_11_PLAN.md` (Phase 10
audit findings). This phase repairs confirmed defects only; it adds no product features.

## 1. Workstreams delivered

| ID | Workstream | What changed |
|---|---|---|
| 11A.1 | Backtest realism (CRIT-01) | `backtesting/engine.py` rewritten: real bar-by-bar SL/TP simulation, conservative both-touched→SL rule, spread/slippage/commission costs applied to PnL, position-aware (lot-size) PnL, `Trade.result ∈ {WIN, LOSS, BREAK_EVEN}`, injectable `strategy` param, shared `summarize_trades()`. `walkforward.py`: `overall` is now a true aggregation of all out-of-sample window trades (plus optional `strategy` passthrough). |
| 11A.2 | FVG correctness (CRIT-02) | `structure/fvg.py` rewritten: bullish = `c1.high < c3.low`, bearish = `c1.low > c3.high`, zones `[c1.high, c3.low]` / `[c3.high, c1.low]`, `threshold_pips` enforced (pip = 0.0001), timestamps ordered (`start_time ≤ end_time`), `formation_time == confirmed_at == c3.time`. |
| 11A.3 | Market structure (CRIT-03) | `structure/orderblocks.py`: `from __future__ import __annotations__` SyntaxError fixed + real OB detection (last opposite-color candle before a ≥1.5×ATR displacement). `structure/bos.py`: real chronological confirmed-swing state machine emitting BOS/CHOCH/MSS — close-confirmed breaks only (wicks ignored), no look-ahead, broken-level dedup, displacement = MSS subset of CHOCH. `structure/analysis.py`: `mtf_bias` rewritten to HH/LH/HL/LL consecutive-swing comparison (was "type of last swing"). `structure/types.py`: `StructureEvent` gained `formation_time` + `confirmed_at` (in `to_dict`). |
| 11A.4 | Test isolation (CRIT-04) | `settings/test.py`: `MT5_USE_MOCK = True` — the suite is hermetic regardless of any local `.env`; every provider return is asserted `data_source == "mock"`; factory-contamination test proves env override cannot select a live provider. Suite runtime dropped **118 s → 13 s** (no live-terminal I/O). |
| 11A.5 | MT5 timestamps (CRIT-05) | `mt5_connector.py`: evidence-based broker UTC offset — pure helpers `compute_offset_seconds`, `normalize_mt5_epoch`, `reject_future_candles`; env `MT5_UTC_OFFSET_HOURS` (default `auto`) measures offset from a fresh tick epoch vs host UTC clock with a ±12/14 h plausibility guard (fallback 0 + warning); offset applied in `get_candles`/`get_tick`; impossible future timestamps rejected with `MarketDataProviderError`. `mock.py`: `datetime.now(timezone.utc)` (M-01) and unknown-timeframe rejection (M-02). |
| 11A.6 | Upload security (H-01) | `analysis/validators.py` rewritten: presence, size, extension whitelist, MIME whitelist, real Pillow decode (`Image.open` + `verify()` from an in-memory copy so the caller's file handle is never closed), extension↔decoded-format match. `analysis/views.py`: validation errors now return **400** with safe `details` (the `except: pass` bypass is gone). |
| 11A.7 | Position sizing (H-06/M-06) | `risk/calculations.py`: 7-major `_SYMBOL_REGISTRY` with `tick_size`/`tick_value`/`quote_currency`; `get_symbol_spec → Optional[SymbolSpec]` (unknown → `None`, never fabricated); new `pip_value_per_lot()` = `tick_value × pip_size/tick_size`, divided by price **only** when quote ≠ account currency; `position_size` guards `None`/zero risk. `risk/scenarios.py`: non-finite prices → `WAIT`, unknown symbol → `WAIT` (spec `None` guard). |

**In-scope adjacencies** (required for the "all 15 repros must pass" mandate, all documented):
`mtf_bias` fix (H-05 partial), `mock.py` fixes (M-01, M-02), walk-forward aggregation (M-07
partial). H-05's conflicts list, LLM-subordination to the deterministic engine, and M-07's
train==test fallback remain P1 items for 11B.

## 2. Every changed file

**Modified (19):**

| File | Workstream |
|---|---|
| `nazbeen_forex_ai/backtesting/engine.py` | 11A.1 |
| `nazbeen_forex_ai/backtesting/walkforward.py` | 11A.1 / M-07 |
| `nazbeen_forex_ai/backtesting/tests/test_backtesting.py` | test-strength (§4) |
| `nazbeen_forex_ai/structure/fvg.py` | 11A.2 |
| `nazbeen_forex_ai/structure/bos.py` | 11A.3 |
| `nazbeen_forex_ai/structure/orderblocks.py` | 11A.3 |
| `nazbeen_forex_ai/structure/analysis.py` | H-05 (partial) |
| `nazbeen_forex_ai/structure/types.py` | 11A.3 |
| `nazbeen_forex_ai/settings/test.py` | 11A.4 |
| `nazbeen_forex_ai/marketdata/mt5_connector.py` | 11A.5 |
| `nazbeen_forex_ai/marketdata/mock.py` | M-01, M-02 |
| `nazbeen_forex_ai/marketdata/tests/test_marketdata.py` | 11A.4 (strengthened) |
| `nazbeen_forex_ai/analysis/validators.py` | 11A.6 |
| `nazbeen_forex_ai/analysis/views.py` | 11A.6 |
| `nazbeen_forex_ai/analysis/tests/test_analysis.py` | fixture fix (§4) |
| `nazbeen_forex_ai/risk/calculations.py` | 11A.7 |
| `nazbeen_forex_ai/risk/scenarios.py` | 11A.7 / M-05 (partial) |
| `nazbeen_forex_ai/core/tests/test_e2e_workflow.py` | fixture fix + 11A.4 (§4) |
| `docs/audits/repro/test_audit_regressions.py` | migration header + fixed-API adaptations |

**Added (10 test files):**

| File | Tests |
|---|---|
| `structure/tests/test_audit_regressions.py` | 6 migrated repros (OB import, FVG ×3, BOS, mtf_bias) |
| `structure/tests/test_fvg_rules.py` | 7 — gap-up/down, no-gap, sub-threshold, overlapping, mutually-overlapping, timestamps |
| `structure/tests/test_market_structure.py` | 10 — BOS bull/bear, CHOCH, MSS, invalid break, wick-poke, no-look-ahead, OB ×3 |
| `marketdata/tests/test_audit_regressions.py` | 2 migrated repros (tick, timeframe) + 4 isolation tests |
| `marketdata/tests/test_utc_normalization.py` | 13 — 5 parametrized offsets, DST, pinned/auto, future rejection ×4, tick drift |
| `risk/tests/test_audit_regressions.py` | 2 migrated repros (EURUSD sizing, unknown symbol) |
| `risk/tests/test_position_sizing.py` | 6 — EURUSD/USDJPY pip value, zero/None guards, registry completeness |
| `analysis/tests/test_audit_regressions.py` | 2 migrated repros (non-image, oversized) + extension/MIME 400s |
| `backtesting/tests/test_audit_regressions.py` | 3 migrated repros (costs, outcomes, walk-forward aggregation) |
| `backtesting/tests/test_engine_simulation.py` | 10 — WIN/LOSS, both-touched, costs, position PnL, metrics, ordering, end-of-data close |

**Documentation (this phase):** `docs/PHASE_REPORTS/PHASE_11A.md` (this file),
`docs/audits/PHASE_11A_FIX_VERIFICATION.md`, `docs/PROJECT_PROGRESS.md`,
`docs/audits/CRITICAL_ISSUES.md` (status banner added; audit record preserved).

## 3. All 15 audit repros migrated and passing

| # | Repro test | Migrated to | Issue |
|---|---|---|---|
| 1 | `test_bug_orderblocks_module_imports` | `structure/tests/test_audit_regressions.py` | CRIT-03 |
| 2 | `test_bug_fvg_gap_up_is_labelled_bullish` | same | CRIT-02 |
| 3 | `test_bug_fvg_gap_down_is_labelled_bearish` | same | CRIT-02 |
| 4 | `test_bug_fvg_start_time_not_after_end_time` | same | CRIT-02 |
| 5 | `test_bug_bos_detects_close_above_swing_high` | same | CRIT-03 |
| 6 | `test_bug_mtf_bias_bullish_on_rising_structure` | same | H-05 (partial) |
| 7 | `test_bug_mock_tick_works_after_connect` | `marketdata/tests/test_audit_regressions.py` | M-01 |
| 8 | `test_bug_mock_rejects_unknown_timeframe` | same | M-02 |
| 9 | `test_bug_position_size_eurusd_exact` | `risk/tests/test_audit_regressions.py` | H-06 |
| 10 | `test_bug_unknown_symbol_yields_wait_not_fabricated_spec` | same | M-06 |
| 11 | `test_bug_upload_rejects_non_image_content` | `analysis/tests/test_audit_regressions.py` | H-01 |
| 12 | `test_bug_upload_rejects_oversized_file` | same | H-01 |
| 13 | `test_bug_backtest_applies_cost_parameters` | `backtesting/tests/test_audit_regressions.py` | CRIT-01 |
| 14 | `test_bug_backtest_outcomes_are_not_dummy` | same | CRIT-01 |
| 15 | `test_bug_walkforward_overall_is_aggregate_of_windows` | same | M-07 (partial) |

`docs/audits/repro/test_audit_regressions.py` is retained as the historical audit index, updated
with a migration header, and now passes **15/15** against the fixed code.

## 4. Test-strength changes (documented, none weakened)

No assertion was deleted or relaxed anywhere. Four fixture/contract changes, each justified:

1. **`test_metrics_consistent` invariant extended** from `wins + losses == total_trades` to
   `wins + losses + break_evens == total_trades`. The engine now has a third honest outcome
   (BREAK_EVEN) instead of silently dropping flat trades — the new invariant is strictly stronger.
2. **PNG upload fixtures corrected** in `test_analysis.py` (×3) and `test_e2e_workflow.py` (×1):
   stubs like `b"\x89PNG\r\n\x1a\n1234567890"` were only ever valid because validation was
   disabled. They now build real decodable PNGs via PIL (as `SimpleUploadedFile` with
   `image/png`) — **all original assertions unchanged** (still `== 201`).
3. **Backtest repros 13/14/15 inject a deterministic strategy.** The bug under test is the
   engine's cost/outcome/aggregation logic (now strategy-injectable). The corrected structure
   detectors form no FVG setups on smooth sawtooth data — an honest outcome that would leave
   engine mechanics untested without an injected signal source. Assertions (`total_trades > 0`,
   costs > 0, `gross_loss > 0 or win_rate < 100`, `overall == Σ windows`) are unchanged.
4. **Repro 10 asserts the fixed API** (`get_symbol_spec(...) is None` + `WAIT` + `position_size
   == 0`) instead of probing the shape of a spec object that no longer exists by design —
   strictly stronger than the original inequality probe.

Strengthened outright: `test_mt5_candles_endpoint_returns_mock_data` and the e2e candles step now
require `data_source == "mock"` (was `"in" ("mock", "mt5")`).

## 5. Verification results (real counts)

| Check | Result |
|---|---|
| `uv run pytest` (main suite, `testpaths = nazbeen_forex_ai`) | **145 passed** (78 baseline + 67 new), 0 failed, ~13 s |
| `uv run pytest docs/audits/repro` (audit artifact index) | **15 passed** |
| `uv run python manage.py check` | `System check identified no issues (0 silenced)` |
| `uv run python manage.py makemigrations --check --dry-run` | `No changes detected` |
| Baseline reconciliation | 78 + 67 added = 145 — per-file collection verified, nothing dropped |

**Live MT5 validation of 11A.5** (MetaQuotes-Demo, real terminal — external validation, this
machine only): auto-detected offset **+3.0002 h** (tick epoch vs host UTC clock) — matches the
audit's observed ≈+3 h future drift as measured evidence, not assumption. After normalization the
tick stamped `2026-10-09T19:10:18Z` (== host UTC), latest M15 candle `18:59:58Z` with age
**11.6 min in the past**, `any future candles: False`. One live-only issue found and fixed
during this test: `copy_rates` fails with `Call failed` when the symbol is not selected in
MarketWatch → `get_candles` now calls `symbol_select(symbol, True)` first (documented in-code).

## 6. Remaining defects (deferred to Phase 11B / owner)

Still open from the audit (unchanged, see `docs/audits/CRITICAL_ISSUES.md` status banner):
H-02 (screenshots not persisted / `MEDIA_ROOT`), H-03 (LangGraph/real LLMs — owner decision),
H-04 (fabrication guard), H-05 remainder (MTF conflicts list + deterministic authority over
LLM), H-07/H-08 (frontend login + dashboard), H-09 remainder (live-credential wiring, symbol
suffix, staleness/closure), H-10 (doc claims errata), M-03/M-04/M-05 remainder/M-08/M-09/M-11…
M-16, P-01/P-02/P-03, L-01…L-07.

Not verifiable in this environment: Docker builds, live PostgreSQL/Redis, real LLM calls,
`mt5_worker` (scaffold), frontend behaviour (not covered by pytest/CI).

## 7. Stop

Phase 11B is **not started**. Per AGENTS.md the next phase requires explicit owner approval —
never implied.
