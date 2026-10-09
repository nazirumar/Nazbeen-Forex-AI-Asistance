# Nazbeen Forex AI Asistance

AI-powered Forex market analysis and decision-support platform. Combines screenshot-based chart
analysis with live MetaTrader 5 data to produce **evidence-based** trading scenarios (BUY SCENARIO
/ SELL SCENARIO / WAIT) — analysis-only, no trade execution.

> Initial market: **EURUSD** · Primary timeframe: **M15** · Entry confirmation: **M1**
> Methodology: ICT / Smart Money Concepts / price action
## Documentation

| Document | Purpose |
|---|---|
| [`docs/MASTER_SPEC.md`](docs/MASTER_SPEC.md) | Canonical specification |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System architecture |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Phase plan |
| [`docs/PROJECT_PROGRESS.md`](docs/PROJECT_PROGRESS.md) | Live progress tracker |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Architecture decision records |
| [`docs/TESTING.md`](docs/TESTING.md) | Test strategy |
| [`docs/API.md`](docs/API.md) | API documentation |
| [`AGENTS.md`](AGENTS.md) | Rules for AI coding agents |

This project is built **phase by phase** — each phase requires explicit approval before the next
one starts. See `docs/ROADMAP.md`.

## Quickstart (development, Windows 11)

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), [Node.js 22+](https://nodejs.org/), [npm](https://docs.npmjs.com/).

Options for backend services (Postgres + Redis):

- **Docker Compose (recommended)**: run the dev services only — backend/frontend run natively.
- **Native Windows services**: use your existing PostgreSQL/Redis and set `DATABASE_URL` / `REDIS_URL` in `.env`.

### Backend

```powershell
# From repository root
uv sync                        # install dependencies
cp .env.example .env           # local configuration (git-ignored)
```

**Start services (if using Docker Compose):**

```powershell
.\scripts\start-infra.ps1
```

**Apply migrations and run the backend:**

```powershell
.\scripts\dev-backend.ps1      # migrate + runserver at http://127.0.0.1:8000
# Or: uv run python manage.py migrate && uv run python manage.py runserver 127.0.0.1:8000
curl http://127.0.0.1:8000/api/health/
```

### Frontend

The frontend calls the backend directly (CORS enabled for `http://localhost:3000`/`http://127.0.0.1:3000`). Copy `.env.example` to `.env.local` if needed (defaults work for local dev).

```powershell
.\scripts\dev-frontend.ps1     # npm install (if needed) + npm run dev at http://localhost:3000
```

### Smoke test

- Dashboard: [http://localhost:3000](http://localhost:3000)
- Backend health: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
- Frontend health: [http://127.0.0.1:3000/api/health](http://127.0.0.1:3000/api/health)

## Tests

```bash
# Backend + frontend checks (CI parity)
.\scripts\test-all.ps1

# Or just backend
uv run pytest
```

## Safety rules

- Analysis-only: this system never places trades without separate explicit authorization.
- No secrets in source; configuration comes from environment variables (`.env.example`).
- Mock market data is always labeled as mock — never silently substituted for live data.
