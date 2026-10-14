# PHASE 11E — Advanced ICT/SMC Intelligence and LangGraph

**Status:** IMPLEMENTED 2026-10-14 — **awaiting owner approval** · **Scope:**
deterministic detectors (MASTER_SPEC §3.C), primary trading model (§3.D), real LangGraph
orchestration (§3.E, resolves ADR-011 per owner order), dashboard integration, golden-fixture
tests. Analysis-only: **no live order execution anywhere**. Phase 11F / remaining audit
remediation not started.

---

## 0. Implementation plan (written before modifying code)

### 0.1 Preparation findings (what exists vs. what 11E adds)

Inspected: `structure/{types,swings,bos,fvg,orderblocks,liquidity,analysis,views}.py`,
`analysis/{services,llm,schemas,views}.py`, `risk/{services,scenarios}.py`,
`docs/{MASTER_SPEC,ARCHITECTURE,DECISIONS}.md`, `audits/RECOMMENDED_FIXES.md`,
existing tests + their monkeypatch targets.

| Area | State after 11C/11D | 11E work |
|---|---|---|
| Swings / BOS / CHOCH / MSS | done (`swings.py`, `bos.py`) | reuse only |
| FVG creation | done (`fvg.py`, CRIT-02 fixed) | + lifecycle: retest / mitigation / invalidation |
| Order blocks | detection done | + validation lifecycle (retested, invalidated) |
| Liquidity | **adjacent equal highs only** (`liquidity.py`, 25 lines) | BSL/SSL swing pools, equal lows, sweeps |
| Displacement | inline inside `orderblocks.py` | dedicated `displacement.py` detector |
| Premium/discount, S/R, S/R flips | **missing** (M-09) | `zones.py` |
| Rejection, engulfing | **missing** (M-09) | `patterns.py` |
| MTF structure alignment | `mtf_bias` (bias + conflicts) | + explicit alignment detector, `null` unavailable preserved |
| Scenario evaluation | `evaluate_scenario` = simple bias+FVG heuristic | primary trading model state machine (`setup.py`) |
| Orchestration | **no LangGraph** (ADR-011 open; no dependency) | real graph, 10 nodes, typed state, Pydantic validation — owner order resolves ADR-011 |
| API | `GET /api/structure/` (11D) | additive: new detector outputs + `setup` checklist |
| Frontend | chart with BOS/CHOCH/MSS, FVG/OB, liquidity (11D) | new overlays + chronological setup checklist |

**Contract constraints discovered (must not break):**

- Tests monkeypatch `services.get_llm_provider` and
  `ScreenshotAnalysisService.retrieve_market_data` → node logic must live in `services.py`
  (module-level name lookup) and call the provider through the service instance.
- `test_llm_levels_never_become_entry_levels` / fabrication-guard tests assert
  `entry_levels == []`, `sl/tp is None` under mock/unsynchronized data → levels are only ever
  emitted when data is synchronized (`source == "mt5"`, fresh) **and** the primary setup is
  complete **and** the risk service accepts the plan.
- `test_structure_api.py` asserts exact `mtf` keys and candle-grid timestamps → all API
  additions must be additive keys; every event timestamp stays on the candle grid.
- `detect_liquidity` must keep emitting `kind == "equal_high"` with a real `level` (API test).

### 0.2 Work packages

**WP1 — Dependency:** `uv add langgraph` (resolves ADR-011: implement, per owner order).

**WP2 — Deterministic detectors** (`nazbeen_forex_ai/structure/`), each with explicit math
rules in the docstring, configurable parameters, bullish+bearish variants, formation and
confirmation timestamps, `[]` on insufficient data, pure functions:

| Module | Functions |
|---|---|
| `liquidity.py` (extend) | `detect_liquidity` → keep legacy equal-highs + add equal-lows, BSL/SSL swing pools (clustered swing highs/lows, ≥2 touches, tolerance) · `detect_sweeps` → wick-through + close-back pools (SSL sweep bullish / BSL sweep bearish) with `formation_time` = pool, `confirmed_at` = sweep bar |
| `displacement.py` (new) | `detect_displacement` → body ≥ `factor` × ATR(`atr_length`) and body ≥ `body_ratio` × range, close-in-direction |
| `fvg.py` (extend) | `annotate_fvg_lifecycle` → per-gap `retest_time` (first overlap), `mitigated_time` (close enters zone), `invalidated_time` (close beyond far edge); state open→retested→mitigated→invalidated |
| `orderblocks.py` (extend) | `validate_orderblocks` → retest / invalidated lifecycle per OB |
| `zones.py` (new) | `detect_premium_discount` (dealing range over `lookback`, midpoint, zone label) · `detect_support_resistance` (swing clusters, ≥`min_touches`, formation=first touch, confirmed=`min_touches`-th) · `detect_sr_flips` (level broken by close, then retested and held: resistance→support / support→resistance, strictly ordered timestamps) |
| `patterns.py` (new) | `detect_rejection` (dominant wick ≥ `wick_ratio` × body, ≥ 50 % of range, close in rejection half) · `detect_engulfing` (opposite bodies, current body engulfs prior body, close beyond prior open) |
| `analysis.py` (extend) | extract `swing_bias(candles)` (identical math to the current closure) · `mtf_structure_alignment(candles_by_tf)` → per-tf structure with `null` unavailable, `aligned` (`None` when no evidence), `conflicts` |

**No look-ahead rule (tested generically):** for every event-emitting detector, running on
`candles[:k]` must yield exactly the events of the full run whose `confirmed_at` is within the
prefix (prefix-consistency ⇒ no repaint, no future-data leakage).

**WP3 — Primary trading model** (`structure/setup.py`): chronological state machine, bullish
sequence per MASTER_SPEC §3.D + owner checklist:

1. `bias_confirmed` (M15 bullish structure) → 2. `liquidity_swept` (SSL sweep) →
3. `displacement_confirmed` → 4. `mss_confirmed` → 5. `fvg_identified` (bullish, not
invalidated) → 6. `retest_confirmed` (price back into the FVG, still valid) →
7. `m1_confirmed` (M1 bullish structure + M1 pattern after the retest).

- Every step records `confirmed_at`; each step must be **≥ the previous step's timestamp** and
  the whole chain must fit inside `max_chain_span` (default 96 M15 bars) → unrelated historical
  signals can never combine into one setup. Each event used at most once.
- H1 recorded as `context` (non-blocking); M5 decisively opposite → blocks (contradictory
  confirmation ⇒ WAIT). Stale/missing data, missing M1, invalid/missing steps → WAIT with
  `blocked_by`.
- Emits real price levels from structure: entry = FVG midpoint, invalidation = sweep-bar low,
  target = nearest opposing confirmed swing/liquidity beyond entry — only when the chain is
  complete; **never** a price that was not a real candle price (derived levels are documented
  formulas, targets must exist in data or the step stays incomplete → WAIT).

**WP4 — LangGraph orchestration** (`analysis/graph.py` + refactor of `services.py`):

- Typed `GraphState` (TypedDict); nodes (execution order matches the brief's list):
  `inspect_screenshot` (bytes/mime) → `retrieve_market_data` → `validate_market_data`
  (freshness + sync + fabrication labels) → `detect_structure` → `multi_timeframe_bias` →
  `reconcile_evidence` (vision + reasoning calls, AI evidence, disagreements — deterministic
  authority) → `evaluate_scenario` (primary model + `apply_deterministic_authority`) →
  `assess_risk` (`create_trade_plan`, only when synchronized + complete) → `validate_output`
  (compose `ScreenshotAnalysisOutput`, Pydantic validate, retry-once with forced WAIT, then
  fail visibly) → `persist_analysis` (injected hook; no-op when absent).
- Node functions are **bound methods of `ScreenshotAnalysisService`** defined in `services.py`
  so every existing monkeypatch target keeps working; `analyze()` becomes the façade that
  invokes the compiled graph — same signature, same output contract.
- Provider failure → `errors` + `uncertainty`, never silent mock substitution;
  LLM disagreement → explicit `disagreements` row, deterministic retained.

**WP5 — API:** extend `GET /api/structure/` with additive keys: `displacement`, `sweeps`,
`rejections`, `engulfings`, `sr_levels`, `sr_flips`, `premium_discount`, `mtf_alignment`,
`setup` (checklist + decision + context), and lifecycle details inside existing
`fvgs` / `order_blocks` items. Same validation, freshness labels, generic 503 pattern.

**WP6 — Frontend:** `lib/types.ts` additions · `lib/chart-data.ts` mappings for sweeps/
displacement/pattern markers, S/R price lines, premium/discount midpoint ·
`components/setup/setup-checklist.tsx` (7 chronological steps: satisfied / missing / invalid /
unavailable, timestamps, blocked reasons, analysis-only disclaimer, no execution controls) ·
wired into chart + dashboard + analysis result · vitest tests for mapping and rendering.

**WP7 — Tests (backend):** `structure/tests/golden.py` deterministic candle fixtures —
`golden_bullish`, `golden_bearish` (mirrored), `golden_ranging`, `golden_invalid`
(chronology-broken, FVG-invalidated, M1-opposite, M5-opposite, chain-span-exceeded) + M1/M5/H1
companions. Per-detector tests (documented rules, both directions, timestamps on grid,
insufficient data), generic no-look-ahead/no-repaint suite, setup-model tests, LangGraph tests
(node inventory, flow, provider failure, disagreement, WAIT fallback, validation retry,
persistence hook, deterministic authority), API tests for the additive keys, existing suites
untouched (no test weakened).

**WP8 — Verification:** `uv run pytest` · `manage.py check` · `makemigrations --check
--dry-run` · `npm test` · `npx tsc --noEmit` · `npm run build`.

**WP9 — Documentation:** this file (results), `PROJECT_PROGRESS.md`, `ARCHITECTURE.md` (§5
graph now real), `API.md`, `TESTING.md`, `DECISIONS.md` (ADR-011 resolved; new ADRs for the
setup-model authority and analysis-output price levels).

Then **STOP** and request owner approval.

### 0.3 Explicit non-actions

- No live trading, no execution controls, no fabricated probability/confidence.
- No changes to backtesting, journal-spec-fields (M-15), Docker (M-11/13), docs errata
  (H-10/M-14/M-16), L-01..L-07 — those remain open outside 11E's scope.
- No existing test modified except where 11E adds new assertions alongside (none removed).

---

## 1. Results

### 1.1 Work packages delivered

| WP | Status | Delivered |
|---|---|---|
| WP1 — Dependency | Done | `langgraph` added via `uv add`; `StateGraph(TypedDict)` build/compile/`invoke` verified. ADR-011 resolved by **ADR-012** (`docs/DECISIONS.md`). |
| WP2 — Deterministic detectors | Done | New `structure/displacement.py`, `structure/patterns.py` (`detect_rejection`, `detect_engulfing`), `structure/zones.py` (`detect_support_resistance`, `detect_sr_flips`, `detect_premium_discount`); extended `structure/liquidity.py` (`detect_sweeps`) and lifecycle annotations in `fvg.py` (`annotate_fvg_lifecycle`) / `orderblocks.py` (`validate_orderblocks`). Pure functions, `[]` on insufficient data, formation/confirmation timestamps kept on the candle grid. |
| WP3 — Primary trading model | Done | `structure/setup.py::evaluate_primary_setup(m15, m1, m5, h1)` — chronological 7-step chain (sweep → displacement → FVG → M1 confirmation …), returns `complete` / `decision` / `blocked_by` / `levels`, no look-ahead. |
| WP4 — LangGraph orchestration | Done | `ScreenshotAnalysisService.analyze()` is now a façade over a compiled 10-node `StateGraph`. Nodes are bound `node_*` methods on the service (in `services.py`), so the monkeypatch targets `services.get_llm_provider` and `ScreenshotAnalysisService.retrieve_market_data` keep working unchanged. `analysis/graph.py` declares `GraphState` (TypedDict) + `AnalysisGraph` (`NODE_NAMES`, `build`, `run`) + `run_analysis_graph`/`analyze_graph`. Deterministic authority, loud provider failure, one validation retry forced to WAIT, optional `persist_hook`. |
| WP5 — API | Done | Additive keys on `GET /api/structure/`: `sweeps`, `displacement`, `rejections`, `engulfings`, `support_resistance`, `sr_flips`, `premium_discount`, `mtf_alignment`, `setup`, plus `details.lifecycle` inside `fvgs`/`order_blocks`. 11D contract unchanged. |
| WP6 — Frontend | Done | `lib/types.ts` + `lib/chart-data.ts` mappings (sweep/displacement markers, S/R + premium/discount lines, setup entry/SL/TP lines), `components/analysis/setup-checklist.tsx`, wired into the chart + dashboard; vitest tests (see §1.2). |
| WP7 — Backend tests | Done | **58 new tests** (see §1.2). |
| WP8 — Verification | Done | `manage.py check` clean · `makemigrations --check --dry-run` → "No changes detected" · `pytest` → **361 passed, 0 failed, 0 skipped** · frontend `vitest` → **111 passed / 11 files**, `typecheck` → exit 0, `build` → exit 0 (11/11 routes). |
| WP9 — Documentation | Done | This report, `PROJECT_PROGRESS.md`, `ARCHITECTURE.md` §5, `API.md`, `TESTING.md`, `DECISIONS.md` (ADR-012). |

### 1.2 Test evidence (actual runs)

**Backend** — `uv run pytest`: **361 passed, 0 failed, 0 skipped** (303 at Phase 11D; **+58 in 11E**). New/changed test files:

| File | Tests |
|---|---|
| `structure/tests/test_detectors_11e.py` | 17 |
| `structure/tests/test_setup_model.py` | 15 |
| `analysis/tests/test_graph.py` | 12 |
| `structure/tests/test_no_lookahead_11e.py` | 9 |
| `structure/tests/test_structure_api.py` (5 new cases) | 16 total (+5) |

CI parity: `uv run python manage.py check` → *System check identified no issues (0 silenced).* · `uv run python manage.py makemigrations --check --dry-run` → *No changes detected* · `uv run pytest` → exit 0, all green.

**Frontend** — `npx.cmd vitest run --maxWorkers=1` → **111 passed / 11 files** (baseline 92/10; **+19 in 11E**); `npm.cmd run typecheck` → exit 0; `npm.cmd run build` → exit 0 (11/11 routes). New file `test/setup-checklist.test.tsx` (8 tests, including an explicit no-execution-controls check) plus added cases in `test/chart-data.test.ts` and `test/trading-chart.test.tsx`; no existing test weakened or removed. (One early vitest run hit the known Windows worker-spawn flake and exited 1 with all tests green; a clean re-run exited 0.)

### 1.3 Files added / changed

Backend: `analysis/{services.py, graph.py, tests/test_graph.py}`, `structure/{analysis.py, displacement.py, patterns.py, zones.py, setup.py, fvg.py, liquidity.py, orderblocks.py, views.py, tests/test_structure_api.py, tests/test_detectors_11e.py, tests/test_no_lookahead_11e.py, tests/test_setup_model.py, tests/candles.py, tests/golden.py}`, `pyproject.toml`, `uv.lock`.
Frontend: `lib/{types.ts, chart-data.ts}`, `components/analysis/setup-checklist.tsx`, `components/chart/trading-chart.tsx`, `app/dashboard/{page.tsx, chart/page.tsx}`, `test/{helpers.ts, setup-checklist.test.tsx, chart-data.test.ts, trading-chart.test.tsx}`.
Docs: `docs/PHASE_REPORTS/PHASE_11E.md`, `docs/{DECISIONS, ARCHITECTURE, API, PROJECT_PROGRESS, TESTING}.md`.

### 1.4 Honest limitations (not verified)

- **No live-environment verification.** The automated suite is hermetic (mock LLM providers, mock market data); real Windows-MT5 and real OpenAI/Gemini paths remain **manual/local only** and were **not** exercised here.
- **No browser click-through.** Frontend correctness rests on the jsdom unit/integration suite — no visual/e2e run against a live backend.
- No live trading, execution controls, or fabricated probability/confidence anywhere (analysis-only preserved).

### 1.5 Remaining work (outside 11E)

Phase 11F (WS-E journal/analytics/export, WS-F infra verification + doc errata) and the residual audit items M-10..M-16, H-10, L-01/L-03..L-07 remain **not started**. **Awaiting explicit owner approval before 11F.**

