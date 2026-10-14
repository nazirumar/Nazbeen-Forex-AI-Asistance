# PROJECT_PROGRESS — Nazbeen Forex AI Asistance

> Read this file together with `docs/MASTER_SPEC.md` at the start of every phase.
> Update it at the end of every phase.

## Current phase

**Phase 11G - Real MT5 Integration, Advanced Backtesting, AI Analysis Validation & Demo Forward
Testing** — **IMPLEMENTED, AWAITING OWNER APPROVAL** (2026-10-14). All workstreams landed: WS1 (MT5
symbol-metadata endpoint), WS2 (backtest execution/reporting API), WS3 (backtesting dashboard), WS4
(simulated forward-testing engine + dashboard + §10 journal linkage), WS5 (§3/§4 regression
verification), WS6 (journal source typing), WS7 (docs + live-verification recording).

> Delivered this phase: `GET /api/mt5/symbol-info/`; the full backtest execution/reporting surface
> (`/api/backtests/runs/…` create/list/detail/trades/metrics/equity/export + `/api/backtests/config/`)
> with `BacktestTrade` persistence and additive engine portfolio stops; the new `forwardtest` app
> (simulated forward-testing models, service, Celery task, owner-scoped API, `/dashboard/forward`
> console) with typed journal linkage (`source=forward_test`); journal `source`/`source_ref` typing.
> **Backend 468 passed, 0 failed** (was 423); **frontend 140 passed / 15 files** (was 132/14);
> `manage.py check` clean; migrations clean; `tsc` exit 0; `next build` exit 0 (16 routes).
> **Live MT5 and live LLM verification remain NOT VERIFIED** — no MT5 terminal and no provider keys
> exist in this environment, so all MT5/LLM paths are exercised through the labelled mock providers
> only; the live steps must be run manually by the owner.

> Phase 11F closed WS-E (journal spec §3.H fields, full CRUD, performance/export, read-only
> owner-scoped backtest history - audit M-15/P2.5) and WS-F (doc/config errata - H-10, M-12,
> M-14, M-16, L-03, L-04, L-06, L-07). Docker build now **succeeds** (verified 2026-10-14);
> GitHub CI for `4ebbc10` is **green** (run #12). Phase 11E (advanced ICT/SMC intelligence +
> LangGraph) completed 2026-10-14 - see `docs/PHASE_REPORTS/PHASE_11E.md`.

## Completed phases

| Phase | Name | Report | Completed |
|---|---|---|---|
| 1 | Foundation (expanded per owner scope) | `docs/PHASE_REPORTS/PHASE_01.md` | 2026-10-08 |
| 2 | MT5 Market Data Integration | `docs/PHASE_REPORTS/PHASE_02.md` | 2026-10-08 |
| 3 | Deterministic ICT/SMC Market Structure Engine | `docs/PHASE_REPORTS/PHASE_03.md` | 2026-10-08 |
| 4 | AI Screenshot Analysis and LangGraph Orchestration | `docs/PHASE_REPORTS/PHASE_04.md` | 2026-10-08 |
| 5 | Trading Scenario and Risk Management Engine | `docs/PHASE_REPORTS/PHASE_05.md` | 2026-10-08 |
| 6 | Historical Backtesting and Statistical Probability Evaluation | `docs/PHASE_REPORTS/PHASE_06.md` | 2026-10-08 |
| 7 | Trading Journal, Analysis Memory and AI Trading Mentor | `docs/PHASE_REPORTS/PHASE_07.md` | 2026-10-08 |
| 8 | Professional Trading Dashboard and User Experience | `docs/PHASE_REPORTS/PHASE_08.md` | 2026-10-08 |
| 9 | Final Integration, Security Review and Demo Release | `docs/PHASE_REPORTS/PHASE_09.md` + `docs/FINAL_RELEASE_REPORT.md` | 2026-10-09 |
| 10 | Infra & Ops (Roadmap Phase 10) | `docs/PHASE_REPORTS/PHASE_10.md` | 2026-10-09 |
| 11A | Critical Correctness Remediation (audit fixes) | `docs/PHASE_REPORTS/PHASE_11A.md` + `docs/audits/PHASE_11A_FIX_VERIFICATION.md` | 2026-10-09 |
| 11B | Real Vision & Reasoning LLM Providers | `docs/PHASE_REPORTS/PHASE_11B.md` | 2026-10-09 |
| 11C | Remaining Data Integrity and Safety Remediation (WS-B / P1.1-P1.8) | `docs/PHASE_REPORTS/PHASE_11C.md` | 2026-10-10 |
| 11D | Professional Trading Dashboard (frontend + supporting endpoints) | `docs/PHASE_REPORTS/PHASE_11D.md` | 2026-10-10 |
| 11E | Advanced ICT/SMC Intelligence and LangGraph (WS-D) | `docs/PHASE_REPORTS/PHASE_11E.md` | 2026-10-14 |
| 11F | Journal, Analytics & Reporting + Infra Verification & Doc Errata (WS-E/WS-F) | `docs/PHASE_REPORTS/PHASE_11F.md` | 2026-10-14 |
| 11G | Real MT5 Integration, Advanced Backtesting, AI Analysis Validation & Demo Forward Testing | `docs/PHASE_REPORTS/PHASE_11G.md` | 2026-10-14 (awaiting owner approval) |

## Completed features

- Standalone-repository decision (ADR-001); TradeMaster explicitly out of scope.
- Full documentation set: `MASTER_SPEC`, `ARCHITECTURE`, `ROADMAP`, `DECISIONS`, `TESTING`,
  `API`, `AGENTS.md`, `.env.example`, `README.md`.
- Django 6.1 + DRF project package `nazbeen_forex_ai` with split settings
  (base/development/test/production), env-based config helpers, UTC defaults, structured
  key=value logging.
- `core` app with `GET /api/health/` (200/503 with database/cache/celery checks; truthful, no secrets).
- `accounts` app: token-based auth (register/login/logout/me), `UserProfile` model with UTC display_timezone,
  signal-based profile creation, password validation; full per-app tests.
- Redis + Celery configuration with dev defaults (eager in dev/test), `verify_infra` management command,
  resilient rate limiting (ADR-008) so throttled endpoints don't 500 when Redis is down.
- Next.js 15 frontend (TypeScript + Tailwind): dashboard shell, auth panel, health/status cards,
  direct-backend API helper (CORS), frontend `/api/health` probe. Builds/typechecks clean.
- Test harness: pytest + pytest-django, **468 backend tests passing** (2026-10-14, full suite; 423 at 11G WS2, 394 at 11F, 303 at 11D); frontend Vitest suite **140 tests** (2026-10-14, 15 files; 132/14 at 11G WS3, 111/11 at 11E, 92/10 at 11D).
- CI workflow (`.github/workflows/ci.yml`): backend (`check`, `makemigrations --check --dry-run`, `pytest`) + frontend (`npm ci`, `typecheck`, `build`).
- Dev tooling: `docker-compose.yml` (Postgres + Redis, plus an `app` profile adding
  backend/worker/frontend containers), PowerShell scripts (`scripts/start-infra.ps1`,
  `scripts/dev-backend.ps1`, `scripts/dev-frontend.ps1`, `scripts/test-all.ps1`), Windows 11 run guidance.
- uv dependency management with committed `uv.lock`.
- **Phase 2 — MT5 data layer**: `marketdata` app with `MarketDataProvider` interface, labeled mock
  provider (`mode: "mock"`), Windows MT5 connector (retry/backoff), authenticated `/api/mt5/*`
  endpoints, UTC normalization, OHLC validation. `mt5_worker/` scaffold (Windows-only).
- **Phase 3 — Market structure engine**: `structure` app — swings (HH/HL/LH/LL), BOS/CHOCH/MSS,
  FVG, liquidity zones, order blocks, MTF bias (H1/M15/M5/M1), BUY/SELL/WAIT evaluation
  (limitations documented in `PHASE_REPORTS/PHASE_03.md`).
- **Phase 4 — Screenshot analysis**: `analysis` app — secure upload/validation, mock LLM provider,
  Pydantic structured schema, MT5 reconciliation with explicit disagreement reporting, safety
  enforcement (no fabricated price levels, no false sync claims), persisted analyses.
- **Phase 5 — Risk engine**: `risk` app — RR, position sizing (contract/tick-aware), SL/TP
  consistency, spread filter, WAIT on invalid setups, `/api/risk/trade-plan/` (never places orders).
- **Phase 6 — Backtesting**: `backtesting` app — chronological event-driven engine, walk-forward
  splits, probability evaluation returning **null** without sufficient evidence.
- **Phase 7 — Journal + mentor**: `journal` app — per-user entries/search, context-aware mentor
  with per-user memory isolation, `/api/mentor/ask/`.
- **Phase 8 — Dashboard**: existing Next.js dashboard validated (typecheck/build OK); dark-theme
  shell with auth, health and status cards wired to backend.
- **Phase 9 — Final review**: security/reliability/migration review, documentation audit
  (report series normalized, API.md refreshed, ADR-009 recorded).
- **Phase 10 — Infra & ops**: JSON logging option + secret-redaction filter, Channels
  `ws/status/` WebSocket (read-only), Celery named queues, full Docker stack configs
  (backend/worker/frontend), production settings hardening, e2e workflow + isolation tests,
  `docs/OPERATIONS.md`, ADR-010.
- **Phase 11A — Critical correctness remediation**: real backtest SL/TP simulation with
  costs and honest metrics (CRIT-01), corrected FVG labels/timestamps/threshold (CRIT-02),
  real BOS/CHOCH/MSS + order blocks + fixed mtf_bias (CRIT-03, H-05 partial), hermetic
  mock-only tests (CRIT-04), evidence-based MT5 UTC offset + future-timestamp rejection
  (CRIT-05, live-validated ≈+3 h), strict Pillow upload validation with safe 400s (H-01),
  correct pip-value/position sizing with unknown-symbol rejection (H-06/M-06), walk-forward
  aggregation fix (M-07 partial); all 15 audit repro tests migrated into app test packages
  and passing.
- **Phase 11B - real vision/reasoning LLM providers**: configurable OpenAI + Gemini adapters (`analysis/llm_providers.py`) with typed Pydantic claim schemas (no decision field), hardened HTTP transport (timeout, retries, 429/Retry-After, secret redaction), deterministic authority over every LLM claim, loud non-mock failure handling, and `manage.py llm_smoke` (H-03 real-provider half; H-05 LLM subordination; ADR-011).
- **Phase 11C - remaining data integrity & safety remediation (WS-B / P1.1-P1.8)**: screenshots persisted under `MEDIA_ROOT/screenshots` with server-generated names + ownership-scoped retrieval endpoint (H-02); fabrication guard without `EURUSD`/`M15` defaults - missing identity yields `null` + WAIT, mock/stale data can never synchronize or authorize price levels (H-04); real MTF `conflicts` across H1/M15/M5/M1 with auxiliary timeframe fetches (H-05); walk-forward chronology validation + explicit not-walk-forward fallback marking (M-07/P-02) and one-signal-per-trade tests (P-03); no fabricated confidence intervals (`[]` whenever uncalibrated, M-08); strict 400 validation for candle queries and trade-plan requests with generic, log-only error details (M-03/M-05/L-02); provider mode derived from the class hierarchy (M-04); MT5 credentials/suffix wired into the factory, last-bar staleness + weekend market-closure labeling (H-09). 86 new tests.
- **Phase 11D - professional trading dashboard (frontend + supporting backend)**: repaired login/register token flow (persistent token, boot re-validation via `/api/auth/me/`, logout, protected routes, session-expiry banner, verbatim DRF/Django field errors); dark responsive shell (collapsible sidebar, symbol/timeframe selectors, MT5 connection + real data-freshness indicators, profile menu, mobile drawer, loading/empty/error states everywhere); TradingView Lightweight Charts v5 chart with real OHLC, BOS/CHOCH/MSS markers anchored to confirmation bars, FVG/order-block zones via a custom series primitive, liquidity + validated entry/SL/TP price lines (backend numbers only, missing levels never drawn); screenshot-analysis workspace (PNG/JPEG upload, preview, full structured result with evidence/disagreements/uncertainty, save & reopen); MTF panel with real conflicts and honest Unavailable states; analysis-only risk panel (no execution controls - enforced by test); journal + owner-scoped analysis history. Backend additions: `GET /api/structure/` (detectors + MTF + freshness), `GET /api/analysis/` (history), freshness labels on `/api/mt5/candles/`, enriched journal search fields. Frontend Vitest suite 92 tests; 17 new backend tests.

- **Phase 11E - advanced ICT/SMC intelligence + LangGraph**: see `PHASE_11E.md`.
- **Phase 11F - journal, analytics & reporting + infra/doc errata (WS-E/WS-F)**: journal now records every MASTER_SPEC §3.H field (screenshot link via FK, analysis timestamp, market snapshot, detected structures, model/strategy version, estimated probability when available) with full owner-scoped CRUD, an honest performance aggregate (`win_rate`/`average_rr`/`total_pnl`/`expectancy`/`profit_factor`/`max_drawdown` - each `null` when unrecorded, with sample sizes), and CSV/JSON export; read-only `GET /api/backtests/` surfaces the caller's recorded runs (owner FK added; unowned runs never exposed). Validation errors answer 400; DRF's `?format=` override disabled so `?format=csv` works. Doc/config errata: README claim corrected, `docs/API.md` regenerated against routes, `ROADMAP.md` status table refreshed, phase-report errata addenda (PHASE_02/04/06/08), `.env.example` mock-first (`MT5_USE_MOCK=true`), production HSTS on by default, `redact_text`/`JsonFormatter` redact URL userinfo + structured extras, login bad-credentials → 401. 29 new backend tests (394 total).

- **Phase 11G - real MT5 integration, advanced backtesting, AI analysis validation & demo forward testing**: `GET /api/mt5/symbol-info/` exposes real MT5 symbol metadata (or labelled mock), **503** when a provider cannot supply it (never fabricated); the full backtest execution/reporting surface (`POST/GET /api/backtests/runs/`, detail/trades/metrics/equity/export, `GET /api/backtests/config/`) persists every simulated trade (`BacktestTrade`) and computes §6 metrics from stored trades only (`null` when not computable, `profit_factor` null+note when there are no losing trades); additive engine portfolio stops (max daily loss / max drawdown) and `walk_forward(**run_kwargs)`; the new `forwardtest` app runs a **simulated** forward test (deterministic engine observed bar-by-bar, per-bar dedupe, checkpointing, conservative SL-first outcome tracking, Celery failure capture) with an owner-scoped API and `/dashboard/forward` console; journal rows gained typed `source`/`source_ref` (manual/screenshot_analysis/backtest/forward_test) with a typed linkage from observations. 45 new backend tests (468 total); 8 new frontend tests (140/15). Live MT5 + live LLM verification remain **NOT VERIFIED** (no terminal/keys here).

## Incomplete features (not yet implemented)

- Profile/settings update API (`/api/auth/me/profile/`) and object-level authorization hardening.
- Password reset (documented out of scope - audit L-07).
- Windows MT5 worker live validation (requires Windows terminal + broker credentials; mock only so far).
- Live LLM provider verification (OpenAI adapter unit-tested only; Gemini live-tested 2026-10-09).
- Optional LightGBM probability model (probability deliberately returns null today).
- Optional Celery-beat schedule for automatic forward-test observation (observation is currently manual via the API/console).

- LangGraph orchestration (MASTER_SPEC section 2): **implemented and wired in Phase 11E** (ADR-012) — `analyze()` is a façade over a 10-node LangGraph `StateGraph` whose nodes are bound `ScreenshotAnalysisService` methods (the deterministic engine stays authoritative).

## Known issues

- PostgreSQL support configured via `DATABASE_URL` but not yet tested against a live server.
- Docker stack (backend/worker/frontend images) **builds successfully** — `docker compose --profile app build` verified 2026-10-14. A full compose **run** of the app profile has not been exercised here.
- Redis channel layer (`USE_REDIS_CHANNELS=true`) configured but only the in-memory layer is tested.
- GitHub Actions CI workflow **executed**: run #12 for `4ebbc10` → `conclusion: success` (2026-10-14). The Phase 11G increment (`f1394bd` + working tree) has not been pushed, so no CI run covers it yet.
- MT5 suffix handling, staleness and the weekend market-closure heuristic (Phase 11C) are verified against a mocked connector only; live-broker symbol naming and holiday calendars remain manual/local verification. `MEDIA_ROOT` serving for production (reverse proxy) is not wired — the screenshot API streams files itself. The Phase 11G `GET /api/mt5/symbol-info/` real-MT5 path is likewise verified against the mock provider only.
- **Live MT5 + live LLM verification for Phase 11G is NOT VERIFIED** — no MetaTrader5 terminal and no provider API keys exist in this environment. All MT5/LLM code paths in 11G are exercised through the labelled mock providers only; the live steps must be run manually by the owner.

- Real-provider LLM behavior is verified only for Google Gemini (`gemini-3.8-flash`, live-tested 2026-10-09); OpenAI adapter paths remain unit-tested only. Google retires models without notice (`gemini-2.5-flash` now → HTTP 404) — keep `*_LLM_MODEL` current.
- Frontend behavior is covered by the jsdom unit/integration suite (140 tests, 15 files); no browser-based visual/e2e verification was run — the owner should click through `/dashboard` and `/dashboard/chart` against the running backend.
- Frontend `npm test` is not yet wired into `.github/workflows/ci.yml` (one-line addition; left for owner confirmation).
- Phase 11F deferrals (recorded, not silently dropped): **L-01** (health endpoints stay open by design; WS-connect throttling optional) and **L-05** (swing equality asymmetry is a behavioural change deferred to avoid unverified golden-fixture churn; stub `tests.py` cleanup done where safe).

## Test status

- Live LLM verification (Phase 11B, 2026-10-09): real Gemini reasoning + vision HTTP 200 via `manage.py llm_smoke`; end-to-end `analyze()` with real MT5 data → deterministic SELL retained over a bullish LLM reading (disagreement recorded, `resolved=True`); transient Google 503s surfaced loudly in `errors`, never mocked.

- `uv run pytest` → **468 passed, 0 failed, 0 skipped** (2026-10-14, Phase 11G complete; 423 at 11G WS2, 394 at 11F; hermetic mock-only)
- `uv run pytest docs/audits/repro` → **15 passed** (audit repro index, all remediated; 11C repaired two out-of-order fixture generators, no assertions changed)
- `manage.py check` → clean; `makemigrations --check --dry-run` → no pending migrations (2026-10-14, Phase 11G complete)
- Frontend `npm test` (vitest) → **140 passed, 0 failed**, 15 files (2026-10-14, Phase 11G; 132/14 at WS3, 111/11 at 11E). On Windows the runner occasionally fails to spawn a worker (workspace path has spaces) — run with `--no-file-parallelism`.
- Frontend `tsc --noEmit` → 0 errors; `next build` → clean, all 16 routes compiled + prerendered (2026-10-14, Phase 11G; 15 routes before `/dashboard/forward`)
- Live smoke test: `GET /api/health/` → `200 OK` on runserver (2026-10-08)
- Live MT5 timestamp check (11A.5): auto-measured server offset +3.0002 h; candles normalized
  to UTC in the past; zero future timestamps (2026-10-09, MetaQuotes-Demo, local machine)

## Next phase

- **Phase 11G — real MT5 integration, advanced backtesting, AI analysis validation & demo forward
  testing: IMPLEMENTED 2026-10-14** (`docs/PHASE_REPORTS/PHASE_11G.md`), **awaiting owner approval**.
  Live MT5/live LLM steps must be run manually by the owner (no MT5 terminal / no live provider keys
  in this environment). Phase 11H (recommended plan in `PHASE_11G.md` §6: scheduled forward-test
  observation, live-verification harness, per-source journal analytics, full compose run) is
  **NOT started — explicit owner approval required. Approval is never implied.**

## Blockers

- Live MT5 terminal verification (symbol-info + candle sync) and live LLM provider verification are
  **blocked in this environment** (no terminal, no provider keys) — owner-manual steps.
- Full `docker compose --profile app up` end-to-end run remains **unverified** here (images build;
  full-stack run not exercised). Recorded as blocked, not done.

## Commit references

- `dbe7fba` — Phase 1–9 baseline (67 tests at the time).
- `5fb5408` — Phase 10 implementation (code, tests, Docker configs).
- Phase 10 docs (`PHASE_10.md`, ADR-010, `OPERATIONS.md`, API.md, this file) — the commit(s)
  following `5fb5408` (see `git log`).
- `15f96ff` - Phase 11A implementation (code, tests, docs).
- Phase 11B LLM providers (`5b6a518`) and live Gemini verification (`a0f4b89`).
- Phase 11C remediation (`docs/PHASE_REPORTS/PHASE_11C.md`, audit status banners, this file) - the commit following `a0f4b89` (see `git log`).
- Phase 11D dashboard (`959b1ad`) - frontend + supporting backend endpoints, docs.
- Phase 11E (`f8c5565`) - advanced ICT/SMC intelligence + LangGraph; pushed to `origin/main`.
- Phase 11F (`4ebbc10`) - journal/analytics (WS-E) + doc/config errata (WS-F); pushed to `origin/main`; GitHub CI run #12 green.
- Phase 11G WS2/WS3 (`f1394bd`) - backtest execution + reporting API and dashboard (committed locally, **not pushed**).
- Phase 11G WS1/WS4/WS5/WS6/WS7 - MT5 symbol-info, forward testing, §3/§4 regression, journal source typing, docs - the commit following `f1394bd` (see `git log`); **not pushed** pending owner approval.
