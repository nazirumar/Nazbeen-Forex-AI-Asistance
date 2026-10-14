---

## ADR-007 — Phase 1 scope expansion (owner-approved)

**Status:** Accepted
**Date:** 2026-10-08

### Context

The owner's Phase 1 request bundled work previously slated for later phases (e.g., token auth, dashboard shell, docker-compose, dev scripts, CI frontend job). The existing ROADMAP/PHASE_01 report described a narrower "backend skeleton" (16 tests). The implementation expanded scope to meet the owner's acceptance criteria without breaking phase boundaries on analysis-only logic (no trading strategies, no AI analysis implemented).

### Decision

- Treat Phase 1 as "Foundation (expanded)" covering: Django backend skeleton, core health, accounts auth (register/login/logout/me), PostgreSQL/Redis/Celery wiring, resilient rate limiting, Next.js dashboard shell, frontend/backend health, dev scripts, docker-compose for Postgres+Redis, Windows 11 run docs, and CI covering backend + frontend.
- Explicitly exclude: trading strategies, market structure, AI pipeline, journal, probability, full frontend workspace — those remain in Phases 3–10.
- Document deviations in PROJECT_PROGRESS.md and this ADR.

### Consequences

- Tests grew from 16 to 38; documentation updated to match repo state.
- Future Phase 2 can focus on the remaining auth/limits hardening (timezone update, rate/limit tuning, object-level authorization, uploads) rather than re-establishing the auth skeleton.

---

## ADR-008 — Resilient rate limiting (degrade on cache outage)

**Status:** Accepted
**Date:** 2026-10-08

### Context

DRF throttles store counters in the Django cache. When Redis is configured but unreachable (broker down), throttle `allow_request` raised an unhandled `ConnectionError` → 500s on throttled endpoints (e.g., register/login). Test settings use LocMemCache so this path wasn't exercised.

### Options

1. Avoid throttling entirely in development. (Weaker, hides the security posture; fails parity.)
2. Fall back to LocMemCache when Redis is unreachable. (Hard to do robustly at runtime; settings-loaded constraints.)
3. Make throttles catch cache failures and allow requests (degrade-gracefully). Log the outage and do not take the API down.

### Decision

Create resilient throttle classes in `nazbeen_forex_ai/core/throttling.py`:
- `ResilientAnonRateThrottle`, `ResilientUserRateThrottle`, `ResilientScopedRateThrottle` — catch any exception from throttle checks (including Redis `ConnectionError`), log a warning with `exc_info`, and return `True` (allow).

Wire into:
- `REST_FRAMEWORK.DEFAULT_THROTTLE_CLASSES` (global defaults)
- `LoginView` / `RegisterView` use `ResilientScopedRateThrottle` with `auth` scope

Add tests: `test_register_degrades_gracefully_when_throttle_cache_down`, `test_login_degrades_gracefully_when_throttle_cache_down`, `test_rate_limit_still_enforced_when_cache_is_healthy`.

### Consequences

- Auth endpoints no longer 500 when Redis/broker is temporarily down (rate limiting is lost in that window — preferred over total outage). 
- Production behavior unchanged when cache is healthy. The health endpoint still truthfully reports cache status.
- This is documented as an operational trade-off in code comments and this ADR.

---

## ADR-009 — Owner-driven phase numbering supersedes ROADMAP labels

**Status:** Accepted
**Date:** 2026-10-09 (recorded during Phase 9 documentation audit)

### Context

The owner instructed phases by their own numbering ("PHASE 2: MT5 Market Data Integration",
"PHASE 3: Market Structure Engine", ... "PHASE 9: Final Integration"), while `docs/ROADMAP.md`
labels the same work differently (Roadmap Phase 3 = MT5 data layer, Phase 4 = market structure,
Phase 6 = screenshot/AI pipeline, Phase 7 = probability, Phase 8 = journal, Phase 9 = frontend,
Phase 10 = infra/ops). Reports and `PROJECT_PROGRESS.md` were produced using the **owner's
numbering**; the ROADMAP file retains its original labels. This discrepancy was implemented but
not previously recorded in DECISIONS.md.

### Decision

- The owner's phase numbering is authoritative for reports (`docs/PHASE_REPORTS/PHASE_XX.md`)
  and `PROJECT_PROGRESS.md`.
- `docs/ROADMAP.md` labels are kept as a historical reference only; scope content is what
  matters, not the label number.
- Mapping: Owner 1 = Roadmap 1(+2), Owner 2 = Roadmap 3, Owner 3 = Roadmap 4, Owner 4 = Roadmap 6,
  Owner 5 = Roadmap 5, Owner 6 = Roadmap 7, Owner 7 = Roadmap 8, Owner 8 = Roadmap 9,
  Owner 9 = release review. **Roadmap 10 (Infra & ops) remains open.**

### Consequences

- Documentation is internally consistent with owner instructions; ROADMAP renumbering was not
  performed to avoid rewriting working docs.
- Remaining open scope is explicitly tracked as Roadmap Phase 10 (full Docker app containers,
  Channels WebSockets, production logging/redaction, e2e suite, operational docs).

---

## ADR-010 — Phase 10 infrastructure decisions (Roadmap: Infra & ops)

**Status:** Accepted
**Date:** 2026-10-09 (Roadmap Phase 10 implementation)

### Context

Roadmap Phase 10 covers Docker Compose (backend/worker), Channels WebSockets, Celery queues,
structured logging + redaction, production rate limiting, e2e tests and operational docs. Three
implementation questions had to be answered while building it.

### Decisions

1. **MetaTrader5 gets a PEP 508 platform marker** (`platform_system == 'Windows'` in
   `pyproject.toml`). The package is Windows-only; without the marker `uv sync` fails on Linux and
   no backend Docker image can be built. The MT5 connector already degrades gracefully to
   "unavailable" when the import fails — behavior on Windows is unchanged (still installed).
2. **WebSocket surface is read-only by design.** `ws/status/` mirrors the public health snapshot
   and accepts exactly `{"action": "ping"}`. No command channel exists: live data streams or
   interactive features must justify a future consumer in their own phase — speculative writable
   WS endpoints are explicitly avoided (analysis-only, MASTER_SPEC §7).
3. **Docker configurations are written but unverified.** Docker is not installed on the dev
   machine, so `Dockerfile`, `frontend/Dockerfile` and the compose `app` profile
   (backend/worker/frontend) were **not built or run**. They are documented as Untested in
   `docs/OPERATIONS.md` and the PHASE_10 report; nothing claims container verification.

### Consequences

- Linux images can build and the Windows dev workflow is untouched.
- The WS layer has a tested, honest baseline (`core/tests/test_websocket.py`) that future
  real-time features can extend.
- Someone with Docker must run `docker compose --profile app up -d --build` once before the
  container stack can be considered working.

## ADR-011 — Phase 11B LLM provider implementation (typed adapters, LangGraph deferred)

**Date:** 2026-10-09 (Phase 11B — real vision/reasoning LLM providers)

### Context

The Phase 10 audit (H-03) flagged that "configurable LLM providers" were inert: the factory
returned the mock in both branches, no HTTP client was even a dependency, and `.env.example`
vision/reasoning variables were read by nothing. The owner's instruction for this phase was
explicit: replace the mock-only factory with real OpenAI + Google Gemini adapters for the
existing `VISION_LLM_*` / `REASONING_LLM_*` variables, with structured JSON outputs,
timeouts/retries, no silent mock fallback, and deterministic findings staying authoritative.
MASTER_SPEC §2 additionally lists LangGraph for orchestration — but LangGraph was **not** part
of the owner's instruction for this phase, and LangGraph is still not a dependency.

### Decisions

1. **Thin typed provider adapters over `httpx`, not SDK packages.** `OpenAIProvider` and
   `GeminiProvider` speak the documented HTTP APIs directly (Chat Completions /
   `generateContent`) through a shared `HTTPTransport` that owns timeout, bounded retries,
   `Retry-After` rate-limit handling and secret-stripped errors. One dependency (`httpx`,
   added via `uv add`) instead of two vendor SDKs; the transport layer is unit-testable with
   injected fake sessions, so the suite needs no network or keys.
2. **The LLM returns claims, never decisions.** `LLMChartAssessment` / `LLMReasoningOutput`
   deliberately contain no `decision` field; `apply_deterministic_authority()` in the service
   computes BUY/SELL/WAIT from deterministic findings alone (audit H-05 half). Candidate price
   levels read from a screenshot stay tagged `source="ai"` evidence and can never become
   `entry_levels`/`sl`/`tp`.
3. **Explicit mock switch, hard failure otherwise.** `USE_MOCK_LLM=true` selects the labeled
   mock; with it `false`, missing/unknown configuration raises `LLMConfigurationError` and
   runtime failures raise `LLMError` — there is no code path that silently substitutes the
   mock for a failed real provider (MASTER_SPEC §4). Test settings force `USE_MOCK_LLM = True`
   for hermeticity (same pattern as `MT5_USE_MOCK`).
4. **LangGraph orchestration is deferred, not dropped.** The spec requirement stands; the
   workflow remains the service-layer "LangGraph-style" pipeline, and this ADR records that
   the owner must decide implement-vs-amend before any phase claims LangGraph. When approved,
   the providers are already structured to become graph nodes/tools unchanged.

### Consequences

- H-03 becomes "partial" (real providers done, LangGraph open); H-05's LLM-subordination
  requirement is satisfied and test-covered.
- Real-provider behavior remains **unverified in this environment** (no API keys here); the
  `manage.py llm_smoke` command plus `docs/TESTING.md` document exactly how the owner runs
  one real call per role. No doc claims live-provider verification.
- API-key exposure is prevented by construction (header auth, redacted `__repr__`, secret
  stripping in errors) rather than by convention.
- **Update (2026-10-14, Phase 11E):** decision 4's deferred item is resolved by **ADR-012** —
  LangGraph orchestration is now implemented and wired as the single analysis pipeline.

---

## ADR-012 — Phase 11E LangGraph orchestration implemented and wired (resolves ADR-011)

**Status:** Accepted
**Date:** 2026-10-14

### Context

ADR-011 deferred LangGraph and required an explicit owner decision before any phase could
claim LangGraph orchestration. The Phase 11E brief (MASTER_SPEC §2/§3.E and
`docs/audits/PHASE_11_PLAN.md` WS-D) authorised resolving it, so this ADR records the
implement-vs-defer outcome: **implement and wire**.

### Decision

1. **LangGraph is a real runtime dependency and the single analysis pipeline.**
   `langgraph` (added via `uv add`) drives `ScreenshotAnalysisService.analyze()`, which is now
   a façade over a compiled `StateGraph`.
2. **The ten nodes are bound methods of `ScreenshotAnalysisService` (defined in
   `services.py`).** `analysis/graph.py` only declares the typed `GraphState` and wires the
   nodes in order: `inspect_screenshot → retrieve_market_data → validate_market_data →
   detect_structure → multi_timeframe_bias → reconcile_evidence → evaluate_scenario →
   assess_risk → validate_output → persist_analysis`. Keeping the logic in the service
   preserves the existing monkeypatch targets (`services.get_llm_provider`,
   `ScreenshotAnalysisService.retrieve_market_data`) and keeps `analyze()`'s output contract
   (`ScreenshotAnalysisOutput`) unchanged.
3. **Deterministic authority is unchanged (audit H-05).** `evaluate_scenario` runs
   `apply_deterministic_authority`; the LLM can never upgrade WAIT into BUY/SELL.
   `assess_risk` produces entry/SL/TP **only** for a synchronized, complete seven-step setup
   that the risk service accepts — otherwise the analysis carries no price levels
   (MASTER_SPEC §3.A fabrication guard).
4. **Failures stay loud (MASTER_SPEC §4).** A failed provider is recorded in
   `errors`/`uncertainty` and the run continues deterministic-only; the mock is never silently
   substituted. Output validation retries once with a forced WAIT; a second failure raises
   visibly.
5. **Persistence stays in the view; the graph exposes an optional `persist_hook`.** Absent
   hook = no-op, so the existing upload view (which owns `ScreenshotAnalysis` rows and
   server-side screenshot storage) is unchanged.

### Consequences

- Audit H-03's "LangGraph missing" item is closed with implementation + tests
  (`analysis/tests/test_graph.py` covers node inventory, wiring, deterministic authority,
  loud provider failures, validation retry and the persistence hook).
- The orchestrator is unit-testable with scripted providers; no network or keys are required.
- Any future node must be added to both `AnalysisGraph.NODE_NAMES` and the service, with a
  test in `test_graph.py`.

---

## ADR-013 — Phase 11F journal/analytics surface, backtest ownership, and the `?format=` override

**Status:** Accepted
**Date:** 2026-10-14

### Context

MASTER_SPEC §3.H requires the trading journal to record the full analysis context (screenshot,
market snapshot, detected structures, model/strategy version, estimated probability, scenario,
levels, outcome) and to support historical review and performance reports. Audit M-15 found the
journal stored only a subset with create+search and no performance/export surface. Audit L-07
found login answered `400` on bad credentials. WS-E also asked for backtest-history surfacing.

### Decision

1. **Journal fields are additive only.** `JournalEntry` gains `screenshot_analysis` (FK →
   `analysis.ScreenshotAnalysis`, `SET_NULL`), `analysis_timestamp`, `market_snapshot`,
   `detected_structures`, `model_version`, `strategy_version`, `estimated_probability`. Existing
   columns and rows are untouched; migration is additive.
2. **No fabrication in the journal or analytics.** A value that was never recorded stays
   `null`/`[]`/`{}`; `performance()` returns `null` for any statistic the recorded data cannot
   support and always reports the `pnl_sample`/`rr_sample` sizes used. `estimated_probability`
   is only ever the caller-supplied/recorded figure — never invented (consistent with M-08).
3. **All journal and backtest reads/writes are owner-scoped**, enforced in the service/queryset,
   not just the view. Another user's entry or analysis id is an opaque `404`/unlinked reference.
4. **Backtest history is owner-scoped.** `BacktestRun` gains a nullable `user` FK; `GET
   /api/backtests/` returns only the caller's runs. Runs recorded without an owner are **not**
   returned, so history is never exposed across accounts.
5. **`journal/export?format=csv|json` is an application parameter.** DRF reserves `?format=` for
   content negotiation and 404s on `csv` when only the JSON renderer is configured, so
   `REST_FRAMEWORK["URL_FORMAT_OVERRIDE"]` is set to `None` globally (no other endpoint used it).
6. **Login bad credentials answer `401`** (uniform message), not `400` (audit L-07). Logout
   already revokes the token; password reset is documented out of scope.

### Consequences

- Audit M-15 / P2.5 closed with service + API + tests (`journal/tests/test_journal_11f.py`,
  `backtesting/tests/test_backtest_history_api.py`).
- WS-F: `.env.example` is mock-first (M-12), production HSTS defaults on (L-04), redaction covers
  URL userinfo + structured extras (L-03), README/API.md/ROADMAP corrected (H-10/M-14/M-16).
- Docker build/run and GitHub-CI execution (M-11/M-13) remain blocked in this environment and are
  recorded as blocked, never claimed as verified.
- `URL_FORMAT_OVERRIDE = None` is a deliberate global change; any future endpoint wanting DRF
  format negotiation must re-enable it explicitly.

---

## ADR-014 — Phase 11G dashboard pages consume existing endpoints; frontend build-context fix

**Status:** Accepted
**Date:** 2026-10-14

### Context

Phase 11 P2.5 listed dashboard surfaces that were still missing after 11D: backtest results,
journal analytics, the AI-mentor chat and account settings. The owner also asked to attempt the
long-blocked Docker build/run and GitHub-CI verification (audit M-11/M-13).

### Decision

1. **No new backend endpoints.** Every Phase 11G page reads an endpoint that already exists and is
   owner-scoped server-side: `GET /api/backtests/`, `GET /api/journal/performance/`,
   `GET /api/journal/export/?format=csv|json`, `POST /api/mentor/ask/`, `GET /api/auth/me/`. The
   frontend adds no derived statistics and invents no fields.
2. **Honesty rules carried into the UI.** A `null` metric renders as "—", never as 0; the
   performance `note` and the sample sizes (`pnl_sample`/`rr_sample`) are shown with the figures;
   the mentor renders the backend answer verbatim and never fabricates one.
3. **The settings page is read-only by design.** There is no account-update endpoint, so no fake
   "save" control is shown — the page states plainly that editing is unavailable.
4. **`frontend/.dockerignore` is required.** The compose `frontend` service builds with
   `context: ./frontend`, so the repository-root `.dockerignore` does not apply; without a
   `frontend/.dockerignore` the build context shipped `node_modules`/`.next` (536 MB) and stalled.
   The file now excludes those (audit M-11: "frontend missing `.dockerignore` entries").
5. **Container verification is attempted, and reported honestly.** Starting the daemon and running
   a build is not the same as a passing, deployable stack: whatever the environment permits is
   recorded with its real outcome, and anything that cannot be run stays marked **blocked**.

### Consequences

- P2.5 dashboard surfaces are complete; `next build` compiles 15 routes (was 11).
- Docker/CI status is evidence-based (see `docs/PHASE_REPORTS/PHASE_11G.md`): the GitHub Actions
  run for the 11F push is checked directly; the image build is attempted against a live daemon.
- No live-trading, MT5 or LLM behaviour is enabled by this phase.
## ADR-015 - Phase 11G backtest execution, MT5 symbol metadata, and simulated forward testing

### Context

Phase 11G had to add, without breaking Phase 11A–11F contracts: (a) an MT5 symbol-metadata
endpoint, (b) an HTTP surface to *run* a backtest and inspect its trades/metrics/equity/export,
(c) a **simulated** forward-testing engine + dashboard, and (d) a typed journal origin so manual,
screenshot, backtest and forward-test rows are never conflated. The platform must stay
analysis-only (no order execution) and must never fabricate market data or metrics.

### Decision

1. **All additions are additive/backward-compatible.** `BacktestRun` gains `status`, `error`,
   `config`, `strategy_version`, `is_walk_forward`, `note`, `data_source`, `started_at`,
   `finished_at` **with `status` defaulting to `completed`**, so Phase 11F rows keep their meaning
   and `GET /api/backtests/` keeps its contract. New `BacktestTrade` rows persist each simulated
   trade so metrics are recomputed from stored data only. Engine portfolio stops and
   `walk_forward(**run_kwargs)` are added with defaults that preserve prior behaviour.
2. **The provider interface is extended without breaking subclasses.**
   `MarketDataProvider.get_symbol_info` is a **concrete** base method that raises
   `MarketDataProviderError`; a provider that cannot supply metadata yields **503**, never a
   fabricated digits/point/tick value. Mock metadata is explicitly labelled `source: mock`.
3. **Forward testing is a first-class *simulated* app** (`nazbeen_forex_ai.forwardtest`): the
   deterministic engine is observed bar-by-bar on fetched candles, one row per `(run, bar_time)`
   (dedupe), with a checkpoint, conservative **stop-first** outcome tracking, and a Celery `heavy`
   task that records a safe failure instead of fabricating a decision. Nothing places, routes or
   simulates a broker order.
4. **The journal gains typed origin** (`source` + opaque `source_ref`) rather than a hard FK, to
   avoid a dependency on the forward-testing app; journal rows from an observation are labelled
   `source="forward_test"` and tagged `simulated`.
5. **Honesty conventions are unchanged**: metrics that cannot be computed are `null` (with sample
   sizes / notes), mock vs live is always labelled, and forward-test results are always labelled
   simulated.

### Consequences

- `POST/GET /api/backtests/runs/…` and `/api/forwardtests/…` are new; `GET /api/backtests/`
  and all 11A–11F endpoints are unchanged.
- Migrations: `backtesting/0003_…`, `journal/0003_…`, `forwardtest/0001_initial.py`.
- Live MT5 symbol metadata and live LLM behaviour remain owner-manual and **NOT VERIFIED** here;
  all automated coverage runs against labelled mock providers.
