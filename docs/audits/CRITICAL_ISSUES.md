# CRITICAL ISSUES — Nazbeen Forex AI Asistance (Phase 10 Full Audit)

**Audit date:** 2026-10-09 · Every issue below was verified in source or reproduced by execution.
Phase completion reports were treated as claims, not evidence.

**Reproducible tests:** all executed repros live in `docs/audits/repro/test_audit_regressions.py`
(run: `uv run pytest docs/audits/repro -v`). The `R-#` shorthands used in
`FEATURE_VERIFICATION_MATRIX.md` are informal pointers — **the test function names in the table
below are authoritative.**

> **Status at audit time: all 15 executed repro tests FAIL — each failure is one confirmed bug.**
> They sit outside `testpaths = ["nazbeen_forex_ai"]`, so the main suite (78 passed) and CI are
> unaffected. They must be migrated into the app test packages and made to pass as part of
> remediation (see `RECOMMENDED_FIXES.md`).

## Phase 11A remediation status (2026-10-09)

Phase 11A repaired the confirmed defects below. This audit record is preserved verbatim as the
historical finding; per-issue verification with test names and live evidence lives in
`PHASE_11A_FIX_VERIFICATION.md`. The repro tests were migrated into the app test packages
(§ "Repro index" footnote) and the retained artifact copy now runs **15/15 PASS**.

> **Phase 11B update (2026-10-09):** the real-provider half of **H-03** — configurable
> OpenAI/Gemini vision + reasoning adapters with timeouts, retries, rate-limit handling,
> secret redaction and schema-validated structured output — is implemented and covered by
> 55 new mocked-provider tests (`PHASE_11B.md`). The LLM-subordination half of **H-05** is
> also implemented: deterministic MT5/ICT/SMC findings are authoritative over every LLM
> claim, the LLM can never upgrade WAIT to BUY/SELL, and LLM-read price levels can never
> reach `entry_levels`/`sl`/`tp`. LangGraph orchestration remains open as an owner decision
> (ADR-011); H-04's symbol/timeframe defaults are unchanged (still open).

> **Phase 11C update (2026-10-10):** WS-B / `RECOMMENDED_FIXES.md` **P1.1–P1.8** are
> implemented (`PHASE_11C.md`): H-02 screenshots now persist under `MEDIA_ROOT/screenshots`
> with server-generated names + an ownership-scoped retrieval endpoint; H-04's fabrication
> guard no longer defaults to `EURUSD`/`M15` (missing identity → `null` + WAIT) and mock or
> stale data can never satisfy the synchronization check; H-05 emits a real MTF `conflicts`
> list across H1/M15/M5/M1 (auxiliary timeframes actually fetched); H-09 wires the dead
> connector config (credentials, broker symbol suffix) into the factory and adds
> last-bar staleness + weekend market-closure labeling; M-03/M-05/L-02 return **400/503/500
> with generic messages** (validated input, exception text only in server logs); M-04's mode
> label is derived from the provider class hierarchy; M-07/P-02/P-03 (chronology validation,
> non-walk-forward fallback marking, one-signal-per-trade) and M-08 (no fabricated confidence
> intervals) are closed. **H-04's price-level half was already structurally closed in 11B.**

| ID | Status | Notes |
|---|---|---|
| CRIT-01 | ✅ resolved | Real SL/TP simulation, costs, honest metrics, injectable strategy |
| CRIT-02 | ✅ resolved | FVG labels, ordered timestamps, threshold, formation/confirmation |
| CRIT-03 | ✅ resolved | Real BOS/CHOCH/MSS state machine + importable, real order blocks |
| CRIT-04 | ✅ resolved | `MT5_USE_MOCK=True` in test settings; factory-contamination test |
| CRIT-05 | ✅ resolved | Evidence-based UTC offset (live-measured +3.0002 h) + future rejection |
| H-01 | ✅ resolved | Strict Pillow validation; view returns safe 400s |
| H-02 | ✅ resolved | Screenshots persist under `MEDIA_ROOT/screenshots` (server-generated names); ownership-scoped retrieval endpoint; traversal refused (Phase 11C) |
| H-03 | 🟡 partial | Real OpenAI/Gemini vision+reasoning providers implemented & tested (Phase 11B); LangGraph → owner decision (ADR-011) |
| H-04 | ✅ resolved | No fabricated chart identity (missing symbol/timeframe → `null` + WAIT); mock/stale data never synchronized (Phase 11C; LLM price levels structurally barred since 11B) |
| H-05 | ✅ resolved | Bias heuristic fixed (11A); LLM subordination (11B); real `conflicts` across H1/M15/M5/M1 with auxiliary fetches (Phase 11C) |
| H-06 | ✅ resolved | Correct pip value per lot; exact 1.00-lot EURUSD repro |
| H-07 | ⛔ open | Frontend login — 11B+ |
| H-08 | ⛔ open | Dashboard scope — 11B+ |
| H-09 | ✅ resolved | Credentials/suffix wired into factory, staleness + market-closure labeling, mocked-connector tests (Phase 11C; timestamps/symbol_select earlier) |
| H-10 | ⛔ open | Documentation errata pass — 11B |
| M-01 | ✅ resolved | Mock tick uses `datetime.now(timezone.utc)` |
| M-02 | ✅ resolved | Unknown timeframe raises `MarketDataProviderError` |
| M-03 | ✅ resolved | `count`/`symbol`/`timeframe`/`start` validated → 400 (bounded, no DoS) (Phase 11C) |
| M-04 | ✅ resolved | Mode label derived from provider class hierarchy, incl. error paths (Phase 11C) |
| M-05 | ✅ resolved | Trade-plan serializer: finite/bounded/typed input → 400; generic internal errors (Phase 11C) |
| M-06 | ✅ resolved | `get_symbol_spec` returns `None`; never fabricated |
| M-07 | ✅ resolved | `overall` = aggregation (11A); fallback marked non-walk-forward + strict chronology validation (Phase 11C) |
| M-08 | ✅ resolved | No fabricated confidence interval: `[]` whenever uncalibrated (Phase 11C) |
| M-09 | ⛔ open | Missing detectors (incl. P-01) — 11B |
| M-10 | 🟡 partial | `formation_time`/`confirmed_at` on FVG/BOS/OB; liquidity/swings events → 11B |
| M-11 … M-16 | ⛔ open | Not in 11A scope — 11B |
| P-01 | ⛔ open | Equal-high/equal-low detectors (with M-09) — not in 11C scope |
| P-02 / P-03 | ✅ resolved | train==test fallback explicitly marked NOT walk-forward; one signal consumed per trade (Phase 11C) |
| L-01, L-03 … L-07 | ⛔ open | Not in 11C scope |
| L-02 | ✅ resolved | Generic client messages everywhere; exception detail logged server-side only (Phase 11C) |

**Suite after 11A:** `uv run pytest` → 145 passed · `manage.py check` → clean ·
`makemigrations --check --dry-run` → no changes.

**Suite after 11C (2026-10-10):** `uv run pytest` → **286 passed** ·
`uv run pytest docs/audits/repro` → **15 passed** · `manage.py check` → clean ·
`makemigrations --check --dry-run` → no changes.

## Repro index

> **Post-11A note (2026-10-09):** the 15 repros below were migrated into
> `structure|marketdata|risk|analysis|backtesting/tests/test_audit_regressions.py` (all pass as
> permanent regressions); the artifact copy in this folder now passes **15/15** against the fixed
> code. The FAIL column documents the audit-time result (historical).

| # | Test function | Result | Confirms |
|---|---|---|---|
| 1 | `test_bug_orderblocks_module_imports` | FAIL — SyntaxError | CRIT-03 |
| 2 | `test_bug_fvg_gap_up_is_labelled_bullish` | FAIL — got `bearish` | CRIT-02 |
| 3 | `test_bug_fvg_gap_down_is_labelled_bearish` | FAIL — got `bullish` | CRIT-02 |
| 4 | `test_bug_fvg_start_time_not_after_end_time` | FAIL — start > end | CRIT-02 |
| 5 | `test_bug_bos_detects_close_above_swing_high` | FAIL — got `[]` | CRIT-03 |
| 6 | `test_bug_mtf_bias_bullish_on_rising_structure` | FAIL — got `BEARISH` | H-05 |
| 7 | `test_bug_mock_tick_works_after_connect` | FAIL — `NameError: utcnow` | M-01 |
| 8 | `test_bug_mock_rejects_unknown_timeframe` | FAIL — DID NOT RAISE | M-02 |
| 9 | `test_bug_position_size_eurusd_exact` | FAIL — got 1.1 lots | H-06 |
| 10 | `test_bug_unknown_symbol_yields_wait_not_fabricated_spec` | FAIL — EURUSD-like spec | M-06 |
| 11 | `test_bug_upload_rejects_non_image_content` | FAIL — got 201 | H-01 |
| 12 | `test_bug_upload_rejects_oversized_file` | FAIL — got 201 | H-01 |
| 13 | `test_bug_backtest_applies_cost_parameters` | FAIL — costs all 0 | CRIT-01 |
| 14 | `test_bug_backtest_outcomes_are_not_dummy` | FAIL — win_rate 100% | CRIT-01 |
| 15 | `test_bug_walkforward_overall_is_aggregate_of_windows` | FAIL — 49 ≠ 147 | M-07 |

Proposed (not executed — traced in source): **P-01** equal-high duplicates / equal-lows absent,
**P-02** walk-forward fallback runs train == test (leakage), **P-03** stale-signal reuse in the
backtest loop.

---

## CRITICAL

### CRIT-01 — Backtest fabricates performance metrics (dummy outcomes, ignored costs)

- **Severity:** Critical · **Module:** backtesting
- **Location:** `nazbeen_forex_ai/backtesting/engine.py:44-102` — esp. `pnl = 1.0` (line ~85,
  "dummy outcome"), `commission_pips` / `slippage_pips` / `spread_pips` never referenced after
  the signature; exit simulation left as a comment ("simplified demo").
- **Evidence (executed):** `run_backtest` on oscillating data produced **189 trades,
  win_rate = 100.0%, gross_loss = 0.0, net_profit = 189.0, expectancy = 1.0, max_drawdown = 0.0**;
  with `commission_pips=5, slippage_pips=1, spread_pips=2` every trade still had
  `commission == slippage == spread_cost == 0`. Repro: `test_bug_backtest_outcomes_are_not_dummy`,
  `test_bug_backtest_applies_cost_parameters`.
- **Reproduction:** `uv run pytest docs/audits/repro -k backtest -v`
- **Root cause:** trade exit/SL/TP simulation was stubbed out and hardcoded `pnl = 1.0`; win/loss
  and all metrics are then computed from that constant; cost parameters are API-compatible but dead.
- **Impact:** every number the backtester reports (win rate, expectancy, drawdown, profit factor)
  is fabricated — a direct MASTER_SPEC §7 violation ("never fabricate accuracy figures") if surfaced.
- **Recommended fix:** simulate exits chronologically (SL/TP hit, bar-by-bar, no peeking), apply
  spread/slippage/commission to entry/exit prices, derive all metrics from real PnL.
- **Required regression test:** migrate both repro tests; add a SL-hit scenario asserting
  `result.losses >= 1` and `win_rate < 100`.

### CRIT-02 — FVG direction labels are inverted (corrupts BUY/SELL decisions)

- **Severity:** Critical · **Module:** structure
- **Location:** `nazbeen_forex_ai/structure/fvg.py:22` (gap-up branch → `"bearish"`),
  `fvg.py:37` (gap-down branch → `"bullish"`); consumed by
  `nazbeen_forex_ai/structure/analysis.py:39-45` (any FVG + bias → BUY/SELL) and by
  `backtesting/engine.py` via `evaluate_scenario`.
- **Evidence (executed):** textbook bullish gap (`c0.high=1.1002 < c2.low=1.1006`) →
  `[('bearish', [1.1002, 1.1006])]`; textbook bearish gap → `[('bullish', [1.099, 1.1])]`.
  A third repro shows one branch emitting `start_time` two bars **after** `end_time`.
- **Reproduction:** `test_bug_fvg_gap_up_is_labelled_bullish`,
  `test_bug_fvg_gap_down_is_labelled_bearish`, `test_bug_fvg_start_time_not_after_end_time`.
- **Root cause:** the bullish/bearish conditions were written inverted (gap-down checked in the
  bullish branch); timestamp arguments swapped in the same branch.
- **Impact:** scenario direction can be inverted; any backtest inherits the error; FVG timestamps
  can violate `start <= end`.
- **Recommended fix:** swap branch labels to match the gap direction, fix timestamp assignment,
  add gap-size threshold handling.
- **Required regression test:** the three FVG repros (migrate into `structure/tests/`).

### CRIT-03 — Headline structure detectors are non-functional (BOS/CHOCH/MSS stub; order blocks unimportable)

- **Severity:** Critical · **Module:** structure
- **Location:**
  - `nazbeen_forex_ai/structure/bos.py:11-32` — `detect_bos_choch_mss` loops over candles with
    bare `pass` branches and **always returns `[]`**.
  - `nazbeen_forex_ai/structure/orderblocks.py:3` — `from __future__ import __annotations__`
    (invalid future feature) → **`SyntaxError: future feature __annotations__ is not defined`**;
    even fixed, logic is a placeholder emitting `direction="neutral"` events (`orderblocks.py:20`).
- **Evidence (executed):** clear swing-high break (close 1.1060 > confirmed swing 1.1050) → `BOS_STUB_OUTPUT: []`;
  `import nazbeen_forex_ai.structure.orderblocks` → SyntaxError.
  Repro: `test_bug_bos_detects_close_above_swing_high`, `test_bug_orderblocks_module_imports`.
- **Root cause:** scaffolds from Phase 3 were never implemented; MSS shares the same stub.
- **Impact:** MASTER_SPEC §3.C items 3–5 and 13 — BOS, CHOCH, MSS, order blocks — produce no
  valid output anywhere in the product, while `PROJECT_PROGRESS` lists them as delivered. The
  trading-model sequence (step: "MSS confirmation") cannot execute.
- **Recommended fix:** implement all three detectors (confirmation-window semantics, no look-ahead)
  or explicitly downgrade spec/progress claims until implemented.
- **Required regression test:** migrate both repros; add CHOCH-vs-BOS first-break classification case.

---

## HIGH

### H-01 — Upload validation deliberately disabled; image content never verified

- **Severity:** High · **Module:** analysis · **Location:**
  `nazbeen_forex_ai/analysis/views.py:27-32` (`except ValidationError: pass` with comments
  "be permissive for tests" / "don't block tests with strict validation");
  `nazbeen_forex_ai/analysis/validators.py:43` (512-byte magic read discarded, literal `pass`).
- **Evidence (executed):** `b"not an image at all"` named `x.png` → **201 Created** (expected 400);
  6 MB payload → **201** (expected 400). Repro: `test_bug_upload_rejects_non_image_content`,
  `test_bug_upload_rejects_oversized_file`.
- **Root cause:** validation was intentionally bypassed to make tests pass — violates AGENTS.md
  ("never weaken tests").
- **Impact:** bypassed size limit + never-verified content = unauthenticated-content upload to disk
  memory/temp (DoS potential); API.md falsely claims "Validates image".
- **Recommended fix:** remove the `except: pass`, return 400 on `ValidationError`; run
  `PIL.Image.verify()` (+ extension/content-type/size); fix tests, not validators.
- **Required regression test:** migrate both upload repros.

### H-02 — Screenshots are never persisted; `MEDIA_ROOT` undefined

- **Severity:** High · **Module:** analysis / settings · **Location:**
  `analysis/views.py:44-46` stores only `file.name` in `image_path`; `analysis/storage.py` is dead
  code (`screenshots_base_dir()` would raise — no `MEDIA_ROOT` in any settings module).
- **Evidence:** zero `MEDIA_ROOT` matches across `nazbeen_forex_ai/settings/*.py`; no code writes
  the uploaded file.
- **Impact:** the screenshot is discarded after analysis — no audit trail, no journal screenshot
  (MASTER_SPEC §3.H requires it), analysis re-inspection impossible.
- **Recommended fix:** define `MEDIA_ROOT`, save via storage helper with a server-generated name,
  store the relative path; add a retrieval endpoint with ownership checks.
- **Required regression test:** upload → file exists on disk → `image_path` points at it.

### H-03 — LangGraph and real LLM providers are missing while claimed

- **Severity:** High · **Module:** analysis / docs · **Location:**
  `pyproject.toml:10-25` (no `langgraph`, no `httpx`/`openai`/`anthropic`);
  `nazbeen_forex_ai/analysis/llm.py:49-57` (`get_llm_provider()` returns mock in **both** branches;
  `OpenAIProvider` raises "not configured" — dead class); `.env.example:26-32` vision/reasoning
  vars are read by nothing.
- **Evidence:** repo-wide grep for `langgraph` → only docstrings; `PHASE_04` report is titled
  "LangGraph Orchestration" (body hedges "LangGraph-style"); MASTER_SPEC §2 requires LangGraph.
- **Impact:** documentation-vs-reality gap; the "configurable providers" requirement is inert.
- **Recommended fix:** either implement a real provider + LangGraph graph (Phase 11 scope) or
  correct the phase report/title and mark the feature explicitly unimplemented.
- **Required regression test:** a provider-selection test asserting configured-key path is chosen
  when env is set, and mock only when it is not.

### H-04 — Fabrication guard depends on `data_synchronized` that mock satisfies; symbol/timeframe fabricated

- **Severity:** High · **Module:** analysis · **Location:**
  `nazbeen_forex_ai/analysis/services.py:34-36,103-105` (`extract_symbol_timeframe({}, hints)`
  falls back to `EURUSD`/`M15` — fabricated chart identity), `services.py:122,139-149`
  (price-level rejection fires only when `data_synchronized` is False; mock provider counts as
  synchronized).
- **Evidence:** mock is labeled synchronized → fabricated LLM price levels can pass the guard;
  missing symbol/timeframe are filled with defaults instead of `uncertainty`.
- **Impact:** violates "the AI must not invent prices / chart identity".
- **Recommended fix:** treat mock/mock-mismatch as unsynchronized; if symbol/timeframe cannot be
  extracted, mark them unknown and force WAIT; never default.
- **Required regression test:** analysis with LLM-emitted price level + mock data → level rejected
  or flagged; no-symbol extraction → `symbol: null` + WAIT.

### H-05 — Multi-timeframe bias heuristic is inverted; MTF conflicts stubbed; LLM not subordinated to deterministic engine

- **Severity:** High · **Module:** structure / analysis · **Location:**
  `nazbeen_forex_ai/structure/analysis.py` (`mtf_bias` returns the *type of the last confirmed
  swing*, so a rising structure ending on a swing-high reports `BEARISH`; H1 input is ignored —
  returns `[]`; M5/M1 are computed then discarded; `conflicts` hardcoded `[]`);
  `analysis/services.py:151-157` (final `decision` = LLM value; deterministic decision stored
  separately, not enforced).
- **Evidence (executed):** rising highs/lows fixture → `expected BULLISH, got BEARISH`.
  Repro: `test_bug_mtf_bias_bullish_on_rising_structure`.
- **Impact:** spec §3.C item 19 broken; every BUY/SELL/WAIT inherits wrong bias; spec rule
  "deterministic market structure is authoritative over the LLM" is not enforced in code.
- **Recommended fix:** compute bias from HH/HL/LH/LL sequence across H1→M15→M5→M1; emit real
  conflict entries; override/fallback `decision` to deterministic engine when they disagree (or
  force WAIT).
- **Required regression test:** migrate the bias repro; add H1-down/M15-up conflict case expecting
  a real `conflicts` entry; add LLM-vs-deterministic disagreement → WAIT/override case.

### H-06 — Position sizing pip value wrong for USD-quoted pairs

- **Severity:** High · **Module:** risk · **Location:**
  `nazbeen_forex_ai/risk/calculations.py:74` — `contract_size * pip_size / entry`.
- **Evidence (executed):** $10,000 balance, 1% risk, 10-pip stop at entry 1.1000 →
  **1.1 lots, expected 1.00** (+10% over-risk; error grows with price level — ~27% on GBPUSD at
  1.27). Repro: `test_bug_position_size_eurusd_exact`.
- **Root cause:** pip value for USD-quoted pairs is a constant ($10/standard lot); dividing by
  `entry` treats it as a conversion from quote to base.
- **Impact:** risk engine over-sizes every trade — core safety function wrong.
- **Recommended fix:** quote-currency-aware pip-value table (USD-quoted constant, JPY-specific,
  non-USD → conversion); clamp unknown symbols to WAIT (see M-06).
- **Required regression test:** migrate the repro; add USDJPY and GBPUSD sizing cases.

### H-07 — Frontend login never works (token discarded before `/me`)

- **Severity:** High · **Module:** frontend · **Location:**
  `frontend/components/auth-panel.tsx:68-81` — login/register response is ignored; `GET
  /api/auth/me/` is issued **before** `setToken(...)` (line 80) and `me.token` does not exist in
  the user serializer anyway.
- **Evidence:** code read; flow cannot complete — unauthenticated `/me` → 401 → `alert`.
- **Impact:** dashboard auth is dead; `localStorage` token never set; every authenticated feature
  (all of which are missing anyway — H-08) would fail even if implemented.
- **Recommended fix:** parse `token` from the login/register response, persist, attach
  `Authorization` in `lib/api.ts` for `/me`; backend: return token on login (it already does per
  accounts serializer — verify) and use 401 semantics.
- **Required regression test:** frontend unit/e2e test of login → `/me` success.

### H-08 — Most of the required dashboard (MASTER_SPEC §3.I) is missing

- **Severity:** High · **Module:** frontend · **Location:** full inventory —
  `frontend/app/page.tsx`, `components/status-cards.tsx`, `components/auth-panel.tsx`,
  `lib/api.ts` only. Missing: upload, analysis workspace, MT5 status, MTF bias, candlestick chart
  with overlays, scenarios, R/R, probability explanations, history, journal, backtests,
  analytics, mentor chat, settings. No frontend WebSocket consumer.
- **Evidence:** frontend build route table shows only `/`, `/_not-found`, `/api/health`;
  grep of `frontend/` for `confidence|probability|win rate` → zero (no misleading display exists —
  verified absent); `page.tsx:8` comment still says charts "arrive in Phases 9+"; `PHASE_08`
  claims a chart placeholder exists — it does not.
- **Impact:** the product's user-facing surface is a status page + broken auth.
- **Recommended fix:** see `PHASE_11_PLAN.md` (frontend workstream) — prioritize analysis
  workspace + chart + MT5 status over secondary pages.
- **Required regression test:** component/integration tests per feature as built.

### H-09 — MT5 live path: dead credential config, no suffix handling, no closure/staleness, zero connector tests

- **Severity:** High · **Module:** marketdata / mt5_worker · **Location:**
  `nazbeen_forex_ai/marketdata/settings.py` (never imported — `MT5_PATH/LOGIN/SERVER/PASSWORD`
  dead; `factory.py:18` constructs provider with no args); no `suffix` code repo-wide (spec §3.B
  requires `EURUSD.pro`-style handling); `analysis/services.py:50` hardcodes
  `"stale": False`; zero weekend/market-closure code; `mt5_worker/app.py` is a 14-line scaffold
  with `MT5_WORKER_*` unread by anything; **no test exercises `MT5MarketDataProvider`.**
- **Evidence:** greps + code reads across `marketdata/`, `mt5_worker/`, settings.
- **Impact:** broker-symbol resolution will fail on suffix brokers; freshness is always "true"
  (stale data silently accepted); connector regressions are undetectable.
- **Recommended fix:** wire env config into the factory; suffix resolution + symbol discovery;
  staleness check (last-bar age); market-closure state; closed/weekend → labeled "closed" status;
  Windows-marked live smoke test (manual) + mocked connector unit tests.
- **Required regression test:** suffix resolution unit test; staleness unit test; connector unit
  tests against a mocked `MetaTrader5` module.

### H-10 — Phase reports / README / API.md make claims contradicted by code

- **Severity:** High · **Module:** documentation · **Location & claims:**
  - `PHASE_04.md` title "LangGraph Orchestration" (H-03).
  - `PHASE_06.md` "basic trade simulation / metrics" — dummy outcomes (CRIT-01).
  - `PHASE_08.md` "all core workflows accessible / chart placeholder" — no chart exists (H-08).
  - `PHASE_02.md` "OHLC validation / staleness helpers / configurable retry" — dead checks, no
    staleness code, retry env vars dead (H-09, M-series).
  - `README.md` "live MetaTrader 5 data" in present tense; `API.md` "Validates image" (H-01).
  - `PROJECT_PROGRESS.md` lists BOS/CHOCH/OB as delivered (CRIT-03).
- **Impact:** the verification record itself is unreliable — exactly what this audit was asked to test.
- **Recommended fix:** issue errata addenda to each report (do not rewrite history), correct
  README/API.md claims, and align `PROJECT_PROGRESS` with the matrix in this audit.
- **Required regression test:** n/a (doc corrections); add a docs-consistency checklist item to
  the phase-closure process.

---

## MEDIUM

| ID | Issue | Location | Evidence / Repro | Fix |
|---|---|---|---|---|
| M-01 | `MockMarketDataProvider.get_tick` raises `NameError: utcnow` → **500 on `/api/mt5/tick/` in default mock mode** (the CI/no-MT5 configuration) | `marketdata/mock.py:91` (`utcnow` never imported) | Executed: `NameError: name 'utcnow' is not defined`; `test_bug_mock_tick_works_after_connect` | Import/use `datetime.now(timezone.utc)`; add a mock-tick endpoint test |
| M-02 | Unknown timeframe silently returns M15 candles while echoing the requested label | `marketdata/mock.py` | `test_bug_mock_rejects_unknown_timeframe` (DID NOT RAISE) | Raise `MarketDataProviderError` for unknown TFs |
| M-03 | `count` unbounded (DoS) and `count=abc` → 500 on `/api/mt5/candles/` | `marketdata/views.py` (no serializer validation) | Source-traced by security audit | Validate `1 ≤ count ≤ N` via serializer; return 400 |
| M-04 | Error-path provider label inverted (`"mode": "mt5" if "MetaTrader" not in str(type(provider)) else "auto"`) | `marketdata/views.py:28` | Code read | Derive mode from `get_connection_info()["mode"]` |
| M-05 | `/api/risk/trade-plan/` has no input serializer: NaN → 500, negative risk → BUY with 0 lots, provider exception text leaks to client | `risk/views.py` + `scenarios.py` | Security-audit trace | Add serializer with finite/bounds validation; catch provider errors |
| M-06 | Unknown symbols silently receive fabricated EURUSD-like contract specs | `risk/calculations.py:21-28` | `test_bug_unknown_symbol_yields_wait_not_fabricated_spec` | Unknown-spec registry → WAIT, never fabricate |
| M-07 | Walk-forward `overall` re-runs the engine on the last window instead of aggregating (`all_trades` dead); insufficient-data fallback runs train == test (leakage); no chronological-sort validation; stale-signal reuse across bars | `backtesting/walkforward.py:24-36`; `engine.py:59-61` | `test_bug_walkforward_overall_is_aggregate_of_windows` (49 ≠ 147); proposed P-02, P-03 | Aggregate window results; fallback marked as non-walk-forward; assert sorted input; consume signals once |
| M-08 | Probability model hardcodes `confidence_interval=[0.3, 0.7]` (a fabricated figure) even though probability itself correctly stays `null`; drift detection missing | `backtesting/probability.py:29-36` | Code read | Return `[]` CI when uncalibrated; implement or document drift detection |
| M-09 | Spec §3.C: sweeps, equal lows, displacement, FVG mitigation, premium/discount, S/R, S/R flips, rejection candles, engulfing — **9+ of 19 required detectors missing**; equal highs duplicate on runs | `structure/liquidity.py`, `fvg.py`, `orderblocks.py`; no modules for the rest | Grep verification (zero matches) | Implement per PHASE_11_PLAN, or scope-down spec with owner approval |
| M-10 | Events stamped at their formation bar with no `confirmed_at` — latent repainting for any future consumer (backtest indexes raw list by bar, so no active look-ahead today) | `structure/swings.py`, `fvg.py`, `liquidity.py` | Source trace | Add `confirmed_at` to every event type; stamp at confirmation bar |
| M-11 | Docker stack defects (static review, **never built**): gunicorn WSGI means `/ws/status/` unreachable in containers; frontend env var `NEXT_PUBLIC_API_URL` vs code's `NEXT_PUBLIC_BACKEND_URL`; default DB creds committed in compose; ports exposed; frontend missing `.dockerignore` entries | `docker-compose.yml`, `Dockerfile`, `frontend/Dockerfile` | Code read | Run on a Docker host (BLOCKED here), fix env/WSGI→daphne-or-drop-WS claim, use `${...}` secrets |
| M-12 | `.env.example` ships `MT5_USE_MOCK=false` (contradicts mock-first docs and feeds CRIT-04); several env vars dead (`MT5_*` retry, `MT5_WORKER_*`), others undocumented | `.env.example:40`, `marketdata/settings.py` | Grep + code read | Default to `true`; remove or wire dead vars; document real ones |
| M-13 | Container configs written but **never built/run** (no Docker on dev machine) | `Dockerfile*`, `docker-compose.yml` | Environment fact | Verification run on a Docker host before any "deployable" claim |
| M-14 | `docs/API.md` contract mismatches: health "fail" codes ≠ handler behavior, generic `{"error"}` vs actual detail shapes, "Validates image" false (H-01), `analysis_id` naming | `docs/API.md` vs `urls.py`/views | Route-by-route comparison | Regenerate API.md from routes |
| M-15 | Journal (spec §3.H) missing: screenshot link, market snapshot, detected structures, model/strategy version, estimated probability; CRUD is create+search only; no performance/export endpoints | `journal/models.py:11-31` | Code read | Phase 11 journal workstream |
| M-16 | `ROADMAP.md` status table stale; README claims overstated (H-10) | `docs/ROADMAP.md`, `README.md` | Doc comparison | Update in Phase 11 docs pass |

## LOW

| ID | Issue | Location | Fix |
|---|---|---|---|
| L-01 | `/api/health/` and `ws/status/` unauthenticated & unthrottled (availability) | `core/views.py`, `core/consumers.py` | Optional: throttle WS connects |
| L-02 | Exception text (incl. provider errors) leaks to API clients | `marketdata/views.py:43,78,94`, `risk/views.py` | Generic client message + log detail server-side |
| L-03 | `JsonFormatter` doesn't redact `extra` fields; URL userinfo (`user:pass@host`) not redacted | `core/logging_extras.py` | Extend `redact_text` to extras + URL patterns |
| L-04 | HSTS defaults off in production settings | `settings/production.py` | Default on (document override) |
| L-05 | Stub `tests.py` files shadow nothing but add noise; dead params (`threshold_pips`, `min_strength`, `lookback`); swing equality asymmetry (`>` high / `>=` low) | `structure/*`, app `tests.py` | Clean up in structure rebuild |
| L-06 | Frontend header shows a static clock/EURUSD label **unlabeled as static** (mock-labeling rule) | `app/page.tsx:62,66` | Label "static" or make live |
| L-07 | Login returns 400 (not 401) on bad credentials; no logout token invalidation; no password reset | `accounts/views.py` | Standardize status codes; document reset as out-of-scope |
