# ROADMAP — Nazbeen Forex AI Asistance

> **Phase rule:** implement only the current phase scope, run tests, write a report in
> `docs/PHASE_REPORTS/`, update `docs/PROJECT_PROGRESS.md`, then **stop and wait for explicit
> approval** before starting the next phase.

## Phase overview

| Phase | Name | Scope summary | Status |
|-------|------|---------------|--------|
| 1 | Foundation | Docs, Django scaffold, env config, health endpoint, test harness, CI | see `PROJECT_PROGRESS.md` |
| 2 | Accounts & API base | Auth, user settings/timezones, rate limiting, upload groundwork | not started |
| 3 | MT5 data layer | Windows MT5 worker, provider interface, mock adapter, candle storage, freshness | not started |
| 4 | Market structure engine | All 19 detectors, config, unit tests, no look-ahead | not started |
| 5 | Trading model & risk | Bullish/bearish sequences, WAIT logic, risk mgmt, position sizing | not started |
| 6 | Screenshot & AI pipeline | Upload pipeline, LangGraph orchestration, vision LLM, structured outputs | not started |
| 7 | Probability engine | Outcomes, chronological splits, walk-forward, calibration, drift | not started |
| 8 | Journal & analytics | Journal records, outcome evaluation, performance reports | not started |
| 9 | Frontend | Next.js dashboard, charts, WS updates, all screens | not started |
| 10 | Infra & ops | Docker Compose, Channels, Celery/Redis, structured logging, e2e, hardening | not started |

## Phase 1 — Foundation (current)

**Goal:** a runnable, tested, documented backend skeleton that later phases build on, with basic auth and a dashboard shell. (Expanded beyond the original narrow skeleton per the Phase 1 owner's acceptance scope.)

In scope:

1. Required tracking docs (`docs/*`, `AGENTS.md`, `.env.example`).
2. Django project package `nazbeen_forex_ai` with split settings (base/development/test),
   environment-based configuration, UTC defaults, structured logging groundwork.
3. `core` app with a `GET /api/health/` endpoint (app status + database check).
4. pytest + pytest-django harness with passing tests.
5. CI workflow running the test suite.

Out of scope: auth, MT5, market structure, AI, frontend, Docker, Celery/Channels.

## Phase 2 — Accounts & API base

User registration/login, per-user timezone display setting, DRF authentication policy, object
level authorization on all analysis endpoints, API rate limiting, upload size/content-type limits,
CORS policy for the future frontend.

## Phase 3 — MT5 data layer

- `MarketDataProvider` interface + `MockMarketDataProvider` (clearly labeled).
- Windows `mt5_worker` service: connection status, broker metadata, symbol discovery, suffix
  handling, OHLCV for M1/M5/M15/H1, bid/ask, spread, tick volume, freshness checks, reconnect.
- Candle storage + UTC normalization + provider labeling in API responses.
- Backend integration tests against the mock provider.

## Phase 4 — Market structure engine

All 19 detectors from MASTER_SPEC §3.C as deterministic, parameter-configurable, pure functions
with documented definitions, unit tests, and look-ahead-free confirmation rules.

## Phase 5 — Trading model & risk

Bullish/bearish 10-step sequences, BUY/SELL/WAIT decision object, confluence assembly (never a
single-indicator signal), risk module: SL/TP planning, RR, position sizing, spread/volatility/
session filters, daily/weekly limits (analysis-only).

## Phase 6 — Screenshot & AI pipeline

Secure image upload/storage, vision LLM provider abstraction (configurable), LangGraph graph with
all nodes from MASTER_SPEC §3.E, Pydantic structured output validation, evidence reconciliation
against MT5 data, persistence of analyses, explicit uncertainty/missing-evidence reporting.

## Phase 7 — Probability engine

Precise outcome definitions, labeled setup history, chronological train/val/test splits,
walk-forward testing, leakage guards, cost modeling (spread/commission/slippage), win rate,
expectancy, drawdown, profit factor, calibration, sample sizes + confidence intervals, drift
detection, **null probability when evidence is insufficient**.

## Phase 8 — Journal & analytics

Full journal CRUD, outcome evaluation workflow, historical review, performance reporting endpoints.

## Phase 9 — Frontend

Next.js + TypeScript + Tailwind dashboard: overview, upload, analysis workspace, MT5 status,
multi-timeframe bias, candlestick chart with structure overlays, scenarios, R/R, probability
explanations, history, journal, backtests, analytics, AI mentor chat, settings. Dark professional
theme.

## Phase 10 — Infra & ops

Docker Compose (Postgres, Redis, backend, worker), Channels WebSockets, Celery queues, structured
logging + redaction, health checks, rate limiting in production config, e2e tests, operational docs.

## Approval checkpoints

After each phase: run tests → fix failures → update docs → write `docs/PHASE_REPORTS/PHASE_XX.md`
→ update `docs/PROJECT_PROGRESS.md` → **stop and request approval**.
