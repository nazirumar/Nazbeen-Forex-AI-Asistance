# ARCHITECTURE — Nazbeen Forex AI Asistance

> Status: living document. Changes to architecture must be justified in `docs/DECISIONS.md`.

## 1. High-level overview

The platform is an **analysis-only decision-support system**. It combines screenshot-based chart
analysis with live MetaTrader 5 market data to produce evidence-based Forex trading scenarios.

```
                        ┌──────────────────────────────────────────────┐
                        │                Frontend (Next.js)            │
                        │  dashboard · upload · charts · journal · chat │
                        └───────────────┬──────────────────────────────┘
                                        │ HTTPS / REST + WebSocket
                        ┌───────────────▼──────────────────────────────┐
                        │           Django backend (Linux/Docker)      │
                        │  ┌────────────────────────────────────────┐  │
                        │  │ REST API (DRF)  ·  Channels (WS)       │  │
                        │  ├────────────────────────────────────────┤  │
                        │  │ Service layer (no ORM in views)        │  │
                        │  ├───────┬──────────┬──────────┬──────────┤  │
                        │  │ Screenshot│ Market │ Structure │ Risk / │  │
                        │  │ service │ data svc│ engine    │ Prob.   │  │
                        │  ├───────┴──────────┴──────────┴──────────┤  │
                        │  │ LangGraph orchestration (AI pipeline)  │  │
                        │  └────────────────────────────────────────┘  │
                        │   Celery workers · Redis broker · Postgres   │
                        └───────┬──────────────────────────────────────┘
                                │ authenticated HTTP (token/HMAC)
                    ┌───────────▼────────────┐
                    │  MT5 Connector Worker  │   ← runs on Windows 11 host
                    │  (MetaTrader5 package, │     next to MT5 desktop terminal
                    │   MT5 terminal open)   │
                    └────────────────────────┘
```

## 2. Why a separate Windows MT5 worker

The `MetaTrader5` Python package depends on the MT5 terminal installed on Windows. It does not run
inside a Linux Docker container. Therefore:

- The Django backend, database, Redis, Celery and frontend run in Docker Compose (Linux).
- A small **Windows MT5 connector worker** runs on the host, owns the `MetaTrader5` package, and
  exposes a narrow authenticated API (REST over HTTP, JSON) consumed by the backend.
- Credentials never leave the Windows host; the worker is configured via environment variables and
- never logs secrets.
- Backend defines an abstract `MarketDataProvider` interface with two implementations:
  - `MT5MarketDataProvider` → calls the Windows worker (production).
  - `MockMarketDataProvider` → deterministic synthetic/canned candles (development only), always
    **clearly labeled** (`data_source: "mock"`) in API responses, snapshots and UI. Mock data is
    never silently substituted for live data.

## 3. Repository layout

```
nazbeen-forex-ai/                  # this repository (standalone; see DECISIONS.md ADR-001)
├── manage.py
├── pyproject.toml                 # uv-managed dependencies, pytest config
├── .env.example                   # documented environment variables
├── AGENTS.md                      # instructions for AI coding agents
├── docs/
│   ├── MASTER_SPEC.md             # canonical specification
│   ├── ARCHITECTURE.md            # this file
│   ├── ROADMAP.md                 # phase plan
│   ├── PROJECT_PROGRESS.md        # live progress tracker
│   ├── DECISIONS.md               # ADRs
│   ├── TESTING.md                 # test strategy
│   ├── API.md                     # API documentation
│   └── PHASE_REPORTS/             # one report per completed phase
├── nazbeen_forex_ai/              # Django project package (settings, urls, asgi, celery)
│   ├── settings/                  # base / development / test / production split
│   ├── core/                      # core app (health, shared utilities, throttling)
│   ├── accounts/                  # token auth + user profiles
│   ├── config.py                  # env helpers + homegrown .env loader
│   ├── urls.py                    # root URL routing
│   └── celery.py                   # Celery app
├── frontend/                      # Next.js 15 app (dashboard shell, Phase 1)
│   ├── app/                        # App Router (layout, page, api/health)
│   ├── components/                 # AuthPanel, StatusCards
│   ├── lib/api.ts                  # backend API helper (direct CORS calls)
│   └── .env.example                 # frontend env vars
├── scripts/                        # PowerShell dev scripts (Windows 11)
│   ├── start-infra.ps1             # start Postgres+Redis via docker compose
│   ├── dev-backend.ps1             # migrate + runserver
│   ├── dev-frontend.ps1             # npm dev (install deps if needed)
│   └── test-all.ps1                 # run backend + frontend checks
├── docker-compose.yml             # Postgres + Redis (dev services only)
└── .github/workflows/ci.yml       # CI pipeline (backend + frontend)
```

## 4. Backend design rules

- **Modular Django apps** per bounded context, e.g. `core`, `marketdata`, `structure`,
  `analysis`, `journal`, `risk`, `probability`, `users` (apps added as their phase arrives).
- **Service layer**: Django views/serializers stay thin. Business logic lives in
  `services.py`-style modules with typed function signatures, so it can be unit-tested without the
  HTTP layer.
- **Typed Python**: type hints on public functions, Pydantic models for AI structured outputs and
  cross-service DTOs.
- **Background jobs**: screenshot analysis, model evaluation and walk-forward testing run in Celery,
  never in the request/response cycle.
- **Time**: all storage and computation in UTC (`USE_TZ = True`); user-facing display timezone is a
  per-user setting.
- **Determinism**: market-structure detectors are pure functions of candle data + parameters, so
  identical inputs always produce identical, reproducible outputs.

## 5. AI pipeline (LangGraph)

The AI layer explains deterministic findings; it does not invent market facts. Orchestration graph
(nodes are services, state is a typed Pydantic state object):

```
inspect_screenshot → retrieve_market_data → validate_market_data → detect_structure
        → multi_timeframe_analysis → reconcile_evidence → generate_scenarios
        → assess_risk → validate_response (Pydantic) → persist_analysis
```

- Screenshot bytes, external text and model outputs are treated as **untrusted input**.
- The final structured response is validated by Pydantic before persistence; invalid output is
  retried or the run fails visibly.
- LLM output is text/explanation only. It can never directly execute a trading command.

## 6. Data model sketch (grows per phase)

- `MarketSnapshot` — candle/tick snapshot tied to an analysis (symbol, timeframe, source).
- `Analysis` — screenshot, timestamp, model/strategy version, decisions, scenarios, probability.
- `DetectedStructure` — detector name, params hash, index range, metadata (reproducibility).
- `JournalEntry` — user notes + outcome evaluation against an `Analysis`.
- `SetupOutcome` — labeled outcome rows consumed by the probability engine.

## 7. Security posture

- Environment-based configuration only; no secrets in source; `.env` is git-ignored.
- Auth (session/JWT) and object-level authorization on all analysis/journal endpoints.
- Rate limiting on API and upload endpoints; upload size limits; image-only content-type
  validation; stored uploads served with safe headers and outside executable paths.
- Windows worker reachable only over a private channel with a shared token; not exposed publicly.
- Structured logs with secret redaction; health endpoints for every service.

## 8. Quality gates

Every phase must pass: unit tests, migration checks, and CI (lint + tests). Features without
tests are never reported as complete.
