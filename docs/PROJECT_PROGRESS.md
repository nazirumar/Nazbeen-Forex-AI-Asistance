# PROJECT_PROGRESS — Nazbeen Forex AI Asistance

> Read this file together with `docs/MASTER_SPEC.md` at the start of every phase.
> Update it at the end of every phase.

## Current phase

**Phase 11B - Real Vision & Reasoning LLM Providers** - completed 2026-10-09 -
**awaiting owner approval before any further 11B scope**

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
- Test harness: pytest + pytest-django, **145 tests passing** (2026-10-09, full suite; 78 pre-11A + 67 added in 11A).
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

## Incomplete features (not yet implemented)

- Profile/settings update API (`/api/auth/me/profile/`) and object-level authorization hardening.
- Backtest HTTP API, performance analytics endpoints, journal export.
- Interactive candlestick chart with price/time-aligned overlays (frontend placeholder only).
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

- Real-provider LLM behavior is verified only for Google Gemini (`gemini-3.8-flash`, live-tested 2026-10-09); OpenAI adapter paths remain unit-tested only. Google retires models without notice (`gemini-2.5-flash` now → HTTP 404) — keep `*_LLM_MODEL` current.

## Test status

- Live LLM verification (Phase 11B, 2026-10-09): real Gemini reasoning + vision HTTP 200 via `manage.py llm_smoke`; end-to-end `analyze()` with real MT5 data → deterministic SELL retained over a bullish LLM reading (disagreement recorded, `resolved=True`); transient Google 503s surfaced loudly in `errors`, never mocked.

- `uv run pytest` → **200 passed, 0 failed** (2026-10-09, Phase 11B (55 new LLM tests); ~14 s — hermetic mock-only)
- `uv run pytest docs/audits/repro` → **15 passed** (audit repro index, all remediated)
- `manage.py check` → clean; `makemigrations --check --dry-run` → no pending migrations
- Frontend `tsc --noEmit` → exit 0 (2026-10-09)
- Live smoke test: `GET /api/health/` → `200 OK` on runserver (2026-10-08)
- Live MT5 timestamp check (11A.5): auto-measured server offset +3.0002 h; candles normalized
  to UTC in the past; zero future timestamps (2026-10-09, MetaQuotes-Demo, local machine)

## Next phase

- **Phase 11B - real vision/reasoning LLM providers: COMPLETED 2026-10-09**
  (`docs/PHASE_REPORTS/PHASE_11B.md`). Remaining audit remediation (H-02, H-04,
  H-10, M-03/M-04/M-05 remainder, M-08-M-16, P-02, MTF conflicts, frontend
  H-07/H-08) and LangGraph (ADR-011): **NOT started - explicit owner approval
  required. Approval is never implied.**

## Blockers

- None.

## Commit references

- `dbe7fba` — Phase 1–9 baseline (67 tests at the time).
- `5fb5408` — Phase 10 implementation (code, tests, Docker configs).
- Phase 10 docs (`PHASE_10.md`, ADR-010, `OPERATIONS.md`, API.md, this file) — the commit(s)
  following `5fb5408` (see `git log`).
- `15f96ff` - Phase 11A implementation (code, tests, docs).
- Phase 11B LLM providers (`docs/PHASE_REPORTS/PHASE_11B.md`, ADR-011, this file) - the commit(s) following `15f96ff` (see `git log`).
