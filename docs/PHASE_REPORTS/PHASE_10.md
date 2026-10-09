# PHASE 10 — Infra & Ops (Roadmap Phase 10)

**Status:** ✅ completed 2026-10-09 — **awaiting owner approval before any further work**
**Scope source:** `docs/ROADMAP.md` § Phase 10 (the final open roadmap phase; owner numbering
per ADR-009 — this is both owner Phase 10 and Roadmap Phase 10).

## 1. Scope delivered

| Roadmap item | Delivered |
|---|---|
| Docker Compose (Postgres, Redis, backend, worker) | `docker-compose.yml` keeps Postgres + Redis and adds a `app` profile: `backend` (migrate → gunicorn), `worker` (Celery, queues `default,heavy`), `frontend` (Next.js). New `Dockerfile`, `frontend/Dockerfile`, `.dockerignore`. |
| Channels WebSockets | `channels` + `channels-redis` + `daphne` added. `asgi.py` now routes HTTP + WS; `ws/status/` pushes the public health snapshot on connect, answers `ping` with `pong`, rejects every other action. Read-only by design (ADR-010). |
| Celery queues | Named queues `default`/`heavy`; `backtesting.*` tasks route to `heavy`; prefetch multiplier 1 so long backtests don't starve lightweight tasks. |
| Structured logging + redaction | `LOG_FORMAT=text|json` (JSON line formatter), `SecretRedactionFilter` on every handler masking `password=`, `secret*`, `token`, `api_key`, `Authorization: Token …` in messages **and** exception traces. |
| Health checks | HTTP `GET /api/health/` unchanged (Phase 1); WS mirror added. |
| Rate limiting in production config | DRF resilient throttles confirmed global (base settings apply to production unchanged); production settings hardened: TLS/HSTS env knobs, `X-Frame-Options: DENY`, nosniff, referrer policy, eager Celery forced off. |
| e2e tests | Full-user-workflow test (register → me → MT5 status → candles → screenshot analysis → analysis detail → trade plan → journal create/search → mentor → logout) + cross-user isolation test. |
| Operational docs | `docs/OPERATIONS.md` — service table, dev/compose runbooks, health/monitoring, logging/redaction, backups, rate limits, deploy steps, incident runbook, security reminders. |

## 2. Additional changes required by the scope

- **`pyproject.toml`:** `MetaTrader5` now carries `platform_system == 'Windows'` — Linux Docker
  builds otherwise fail on the Windows-only wheel. Windows behavior unchanged (still installed).
  Recorded in ADR-010.
- **`.env.example`:** `LOG_FORMAT` and `USE_REDIS_CHANNELS` documented.
- **`docs/API.md`:** `ws/status/` documented; stale "no git commits" note removed.
- **`docs/DECISIONS.md`:** ADR-010 added.

## 3. Verification (real results, 2026-10-09)

| Check | Result |
|---|---|
| `uv run pytest` | **78 passed, 0 failed** (was 67 → +11 new: 6 logging, 3 WebSocket, 2 e2e) |
| `uv run python manage.py check` | clean (0 issues) |
| `uv run python manage.py makemigrations --check --dry-run` | No changes detected |
| `uv sync` | resolves; MetaTrader5 still installed on Windows via marker |

## 4. NOT verified (explicitly)

- **Docker:** Docker is not installed on this machine. `Dockerfile`, `frontend/Dockerfile` and
  the compose `app` profile were **not built or run**. They follow standard uv/gunicorn/Next.js
  practice but must be smoke-tested (`docker compose --profile app up -d --build`) on a Docker
  host before being considered working. Labeled *Untested* in `docs/OPERATIONS.md`.
- **Redis channel layer** (`USE_REDIS_CHANNELS=true`): only the in-memory layer is exercised by
  tests; the Redis backend config is written but not run against live Redis.
- **daphne under real HTTP/WS load:** WS behavior is verified via Channels' in-process
  `WebsocketCommunicator`, not a live network socket.
- **GitHub CI:** workflow exists and runs these same commands; it has never executed on GitHub.
- Live MT5 remains mock-only (unchanged from previous phases).

## 5. Tests added

- `core/tests/test_logging.py` (6) — redaction of password/JSON-secret/bearer patterns, filter
  behavior on records, JSON formatter validity + redaction.
- `core/tests/test_websocket.py` (3) — status snapshot on connect (no secrets), ping/pong,
  unknown-action rejection.
- `core/tests/test_e2e_workflow.py` (2) — the full user journey above, and that user B cannot
  see user A's journal entries.

## 6. Known limitations / follow-ups

- Container stack needs one verification run on a Docker host (above).
- Rate limiting at the reverse proxy (nginx/Caddy layer) is not configured — app-level throttles
  only.
- No error-tracking SaaS integrated (deliberate; needs owner approval).
- Remaining feature gaps unchanged from Phase 9 report (profile API, backtest HTTP API,
  analytics/export endpoints, interactive chart overlays, live MT5 validation).

## 7. Approval

Roadmap Phase 10 scope is complete and verified to the extent possible on this machine.
**Stopped here — awaiting explicit owner approval before any further phase or feature work.**
