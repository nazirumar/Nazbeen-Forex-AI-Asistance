# PROJECT_PROGRESS — Nazbeen Forex AI Asistance

> Read this file together with `docs/MASTER_SPEC.md` at the start of every phase.
> Update it at the end of every phase.

## Current phase

**Phase 11D - Professional Trading Dashboard** - completed 2026-10-10 -
**awaiting owner approval before Phase 11E**

> Phase 11C (data integrity remediation) completed 2026-10-10 - see
> `docs/PHASE_REPORTS/PHASE_11C.md`. Phase 11B (real LLM providers) 2026-10-09.

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
- Test harness: pytest + pytest-django, **303 backend tests passing** (2026-10-10, full suite; 78 pre-11A + 67 in 11A + 55 in 11B + 86 in 11C + 17 in 11D); frontend Vitest suite **92 tests** (2026-10-10, 10 files).
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

## Incomplete features (not yet implemented)

- Profile/settings update API (`/api/auth/me/profile/`) and object-level authorization hardening.
- Backtest HTTP API, performance analytics endpoints, journal export.
- Windows MT5 worker live validation (requires Windows terminal + broker credentials; mock only so far).
- Optional LightGBM probability model (probability deliberately returns null today).
- GitHub-hosted CI execution (workflow exists, not yet run on GitHub).
- Docker image build/run verification (Docker unavailable on the dev machine — configs untested).

- LangGraph orchestration (MASTER_SPEC section 2): real provider adapters shipped in Phase 11B; graph orchestration awaits the owner decision (ADR-011).

## Known issues

- PostgreSQL support configured via `DATABASE_URL` but not yet tested against a live server.
- Docker stack (backend/worker/frontend images) written but never built — no Docker on the dev machine.
- Redis channel layer (`USE_REDIS_CHANNELS=true`) configured but only the in-memory layer is tested.
- CI workflow not yet executed on GitHub (runs locally-verified commands).
- MT5 suffix handling, staleness and the weekend market-closure heuristic (Phase 11C) are verified against a mocked connector only; live-broker symbol naming and holiday calendars remain manual/local verification. `MEDIA_ROOT` serving for production (reverse proxy) is not wired — the screenshot API streams files itself.

- Real-provider LLM behavior is verified only for Google Gemini (`gemini-3.8-flash`, live-tested 2026-10-09); OpenAI adapter paths remain unit-tested only. Google retires models without notice (`gemini-2.5-flash` now → HTTP 404) — keep `*_LLM_MODEL` current.
- Phase 11D frontend behavior is covered by the jsdom unit/integration suite (92 tests); no browser-based visual/e2e verification was run — the owner should click through `/dashboard` against the running backend.
- Frontend `npm test` is not yet wired into `.github/workflows/ci.yml` (one-line addition; left for owner confirmation).

## Test status

- Live LLM verification (Phase 11B, 2026-10-09): real Gemini reasoning + vision HTTP 200 via `manage.py llm_smoke`; end-to-end `analyze()` with real MT5 data → deterministic SELL retained over a bullish LLM reading (disagreement recorded, `resolved=True`); transient Google 503s surfaced loudly in `errors`, never mocked.

- `uv run pytest` → **303 passed, 0 failed** (2026-10-10, Phase 11D (17 new tests); 286 at 11C end; hermetic mock-only)
- `uv run pytest docs/audits/repro` → **15 passed** (audit repro index, all remediated; 11C repaired two out-of-order fixture generators, no assertions changed)
- `manage.py check` → clean; `makemigrations --check --dry-run` → no pending migrations (2026-10-10)
- Frontend `npm test` (vitest) → **92 passed, 0 failed**, 10 files (2026-10-10)
- Frontend `tsc --noEmit` → 0 errors; `next build` → clean, all 11 routes compiled + prerendered (2026-10-10)
- Live smoke test: `GET /api/health/` → `200 OK` on runserver (2026-10-08)
- Live MT5 timestamp check (11A.5): auto-measured server offset +3.0002 h; candles normalized
  to UTC in the past; zero future timestamps (2026-10-09, MetaQuotes-Demo, local machine)

## Next phase

- **Phase 11D - professional trading dashboard: COMPLETED 2026-10-10**
  (`docs/PHASE_REPORTS/PHASE_11D.md`). Phase 11E and remaining audit remediation
  (P-01/M-09 detectors, M-10..M-16, H-10 docs pass, L-01/L-03..L-07):
  **NOT started - explicit owner approval required. Approval is never implied.**

## Blockers

- None.

## Commit references

- `dbe7fba` — Phase 1–9 baseline (67 tests at the time).
- `5fb5408` — Phase 10 implementation (code, tests, Docker configs).
- Phase 10 docs (`PHASE_10.md`, ADR-010, `OPERATIONS.md`, API.md, this file) — the commit(s)
  following `5fb5408` (see `git log`).
- `15f96ff` - Phase 11A implementation (code, tests, docs).
- Phase 11B LLM providers (`5b6a518`) and live Gemini verification (`a0f4b89`).
- Phase 11C remediation (`docs/PHASE_REPORTS/PHASE_11C.md`, audit status banners, this file) - the commit following `a0f4b89` (see `git log`).
- Phase 11D dashboard (`959b1ad`) - frontend + supporting backend endpoints, docs.
