# RECOMMENDED FIXES — Prioritized Remediation (Phase 10 Audit)

**Rule:** every fix ships with its regression test. The repro tests in
`docs/audits/repro/test_audit_regressions.py` must be **migrated into the app test packages and
made to pass** — they are the acceptance tests for P0/P1 below. Never delete or weaken a failing
test to reach green (AGENTS.md).

## P0 — Correctness & truthfulness (before any feature work)

| # | Fix | Issues | Scope | Acceptance |
|---|---|---|---|---|
| P0.1 | Implement real trade exits (SL/TP/bar-by-bar, chronological, no peeking) and apply commission/slippage/spread to PnL; derive all metrics from real outcomes | CRIT-01 | `backtesting/engine.py` | `test_bug_backtest_outcomes_are_not_dummy`, `test_bug_backtest_applies_cost_parameters` pass; a guaranteed-SL scenario shows `losses ≥ 1` |
| P0.2 | Fix FVG branch labels (gap-up → bullish, gap-down → bearish) and the swapped timestamps | CRIT-02 | `structure/fvg.py` | FVG repros (3) pass |
| P0.3 | Implement `detect_bos_choch_mss` (BOS with-trend, CHOCH first counter-break, MSS ≠ duplicate) and fix `orderblocks.py` `__future__` import + real OB logic (or explicitly downgrade the spec with owner sign-off) | CRIT-03 | `structure/bos.py`, `structure/orderblocks.py` | `test_bug_bos_detects_close_above_swing_high`, `test_bug_orderblocks_module_imports` pass + new CHOCH-classification test |
| P0.4 | Force mock in tests: set `MT5_USE_MOCK=true` in `settings/test.py`; assert `data_source == "mock"` in marketdata tests; document that local `.env` currently runs live | CRIT-04 | `settings/test.py`, `marketdata/tests` | New test: under `settings.test`, factory returns `MockMarketDataProvider`; suite passes with `.env` deleted/renamed |
| P0.5 | Live-timezone correction: configurable `MT5_UTC_OFFSET` (auto-detect vs machine UTC or explicit), applied in `mt5_connector` conversion; reject/log impossible future bars | CRIT-05, H-09 | `marketdata/mt5_connector.py`, settings | Unit test of conversion with a +2/+3h server offset; smoke test asserts no bar > now + tolerance |
| P0.6 | Re-enable upload validation: remove `except ValidationError: pass`; `PIL.Image.verify()`; enforce 5 MB; fix the tests that motivated the bypass | H-01 | `analysis/views.py`, `analysis/validators.py` | Both upload repros pass (400) |
| P0.7 | Fix pip-value math: quote-currency-aware pip value (USD-quoted constant $10/lot etc.); unknown symbol → WAIT (no fabricated specs) | H-06, M-06 | `risk/calculations.py`, `risk/scenarios.py` | `test_bug_position_size_eurusd_exact`, `test_bug_unknown_symbol_yields_wait_not_fabricated_spec` pass + USDJPY case |

## P1 — Safety, honesty & core functionality

| # | Fix | Issues | Scope |
|---|---|---|---|
| P1.1 | Rebuild `mtf_bias` from HH/HL/LH/LL across H1→M15→M5→M1; real `conflicts` list; enforce **deterministic decision authoritative over LLM** (disagreement → WAIT/override) | H-05, CRIT-03 dependency | `structure/analysis.py`, `analysis/services.py` |
| P1.2 | Fabrication guard hardening: mock counts as *unsynchronized* for price-level checks; missing symbol/timeframe → `null` + WAIT (never `EURUSD`/`M15` defaults) | H-04 | `analysis/services.py` |
| P1.3 | Persist screenshots: define `MEDIA_ROOT`, save file via storage helper with server-side name, store relative path, ownership-scoped retrieval endpoint | H-02 | settings + `analysis/` |
| P1.4 | Walk-forward: aggregate `overall` from window results; mark insufficient-data fallback as non-walk-forward (train==test never reported as OOS); validate input chronology; consume each signal once | M-07, P-02, P-03 | `backtesting/walkforward.py`, `engine.py` |
| P1.5 | Probability: `confidence_interval: []` when uncalibrated (remove fabricated `[0.3,0.7]`); keep `probability: null` <30 unchanged | M-08 | `backtesting/probability.py` |
| P1.6 | Input validation: trade-plan serializer (finite, ordered, bounded); candles `count` bounded + numeric → 400 not 500; generic client errors, details to logs | M-03, M-05, L-02 | `risk/`, `marketdata/views.py` |
| P1.7 | Mock tick `utcnow` NameError; unknown-timeframe rejection; error-path mode label | M-01, M-02, M-04 | `marketdata/mock.py`, `views.py` |
| P1.8 | MT5 connector: wire dead env config into factory; broker symbol **suffix handling**; staleness (last-bar age); market-closure state; mocked-connector unit tests | H-09 | `marketdata/` |

> **P1 status (2026-10-10) — all of P1.1–P1.8 implemented and verified (Phase 11C, except
> M-01/M-02 which landed in 11A).** Per-fix regression tests were added:
> `structure/tests/test_mtf_conflicts.py` (P1.1), `analysis/tests/test_fabrication_guard.py`
> (P1.2), `analysis/tests/test_screenshot_storage.py` (P1.3), `backtesting/tests/test_walkforward_integrity.py`
> (P1.4), CI assertions in `test_walkforward_integrity.py` (P1.5), `marketdata/tests/test_validation_11c.py`
> + `risk/tests/test_trade_plan_validation.py` (P1.6), existing M-01/M-02 tests + mode-label
> tests in `test_validation_11c.py` (P1.7), `marketdata/tests/test_mt5_connector.py` (P1.8).
> Suite: **286 passed**; repro artifact **15/15**. Details: `docs/PHASE_REPORTS/PHASE_11C.md`.

## P2 — Frontend & UX (spec §3.I)

| # | Fix | Issues |
|---|---|---|
| P2.1 | Fix login flow: persist token from login/register response; attach `Authorization` in `lib/api.ts`; then `/me` works | H-07 |
| P2.2 | Analysis workspace: screenshot upload → analysis result view (decision, evidence, disagreements, uncertainty) | H-08 |
| P2.3 | MT5 status + candles + MTF bias pages (live/mock labeling everywhere) | H-08 |
| P2.4 | Candlestick chart with structure overlays (lightweight-charts), scenarios/RR display | H-08 |
| P2.5 | History, journal, backtest results, analytics, mentor chat, settings — in that priority order | H-08, M-15 |
| P2.6 | Consume `ws/status/` for live updates; label static header elements as static (L-06) | H-08, L-06 |

## P3 — AI/LangGraph, spec detectors, infra (see PHASE_11_PLAN)

- Real vision + reasoning providers behind env config, with LangGraph orchestration **or** a
  formal spec amendment removing LangGraph (owner decision) — H-03.
- Missing detectors: sweeps, equal lows, displacement, FVG mitigation, premium/discount, S/R,
  flips, rejection, engulfing — M-09; add `confirmed_at` to all events (M-10).
- Journal spec fields (screenshot, snapshot, structures, model/strategy version) + performance
 /export endpoints — M-15.
- Docker verification run on a Docker host; fix compose WSGI/WS, frontend env var, secrets —
  M-11, M-13.
- Documentation errata: PHASE_02/04/06/08 claims, README "live MT5 data", API.md "Validates
  image", `PROJECT_PROGRESS` detector claims, ROADMAP status — H-10, M-14, M-16.
- Low-severity cleanups L-01..L-07.

## Explicit non-actions

- Do **not** surface any backtest metric in API/frontend until P0.1 lands.
- Do **not** claim LangGraph, live-MT5 correctness, or container readiness in docs until the
  corresponding fixes/verifications are executed.
- Do **not** enable live trading (unchanged: analysis-only).
