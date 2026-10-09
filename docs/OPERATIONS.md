# Operations Runbook — Nazbeen Forex AI Asistance

Analysis-only platform. Nothing in this document enables live trading (MASTER_SPEC §7).

Status legend: **Verified** = exercised on the dev machine · **Untested** = written to
standard practice but not run here (Docker unavailable on Windows dev machine).

---

## 1. Service overview

| Service      | Tech                       | Port  | Notes                                     |
|--------------|----------------------------|-------|-------------------------------------------|
| API          | Django 6 + DRF (gunicorn)  | 8000  | Verified natively (`manage.py runserver`) |
| Worker       | Celery (Redis broker)      | —     | Eager mode in dev; real worker in compose |
| Frontend     | Next.js 15                 | 3000  | Verified natively (`npm run dev`)         |
| WebSocket    | Channels `ws/status/`      | 8000  | Verified via in-process test client       |
| MT5 worker   | Windows-only FastAPI       | —     | Run natively on Windows; never in Docker  |
| PostgreSQL   | postgres:16-alpine         | 5432  | Optional (SQLite default)                 |
| Redis        | redis:7-alpine             | 6379  | Cache/broker/channel layer                |

## 2. Starting (development, native Windows — Verified)

```powershell
uv sync
Copy-Item .env.example .env        # then edit values
uv run python manage.py migrate
uv run python manage.py runserver  # API; daphne serves WebSockets
npm --prefix frontend run dev      # dashboard
```

Infrastructure-only services: `docker compose up -d` (Postgres + Redis).

## 3. Starting (full Docker stack — Untested)

Requires Docker Desktop (WSL2) and a real `DJANGO_SECRET_KEY` in `.env`
(compose aborts if it is unset; production settings reject insecure keys).

```bash
docker compose --profile app up -d --build
```

- `backend` — runs migrations, then gunicorn on :8000
- `worker`  — Celery on queues `default,heavy`
- `frontend`— Next.js on :3000

The MT5 connector (`mt5_worker/`) cannot run in Linux containers — run it natively
on Windows and point `MT5_WORKER_URL` at it.

## 4. Health & monitoring

- `GET /api/health/` — checks database, cache, Celery broker. Returns **503 when the
  database is unreachable** (degraded) by design — do not "fix" it as a bug.
- WebSocket `ws/status/` — same snapshot pushed on connect; send
  `{"action": "ping"}` for a liveness round-trip. Read-only; no commands accepted.
- Logs go to stdout (container-friendly), level via `LOG_LEVEL`.
- No external error-tracking SaaS is integrated; stdout + container logs are the
  source of truth. Add Sentry (or similar) only with owner approval.

## 5. Logging & redaction

- `LOG_FORMAT=text` (default, `key=value` lines) or `LOG_FORMAT=json`
  (one JSON object per line — recommended in production).
- Every record passes a redaction filter: `password=`, `secret`, `token`,
  `api_key`, `Authorization: Token …` patterns are masked as `***REDACTED***`
  in message *and* exception text. Tests: `core/tests/test_logging.py`.
- Redaction is defense-in-depth — never log secrets deliberately.

## 6. Backups

- **SQLite (default):** copy `db.sqlite3` while the server is stopped, or use
  `uv run python manage.py dumpdata --indent 2 > backup.json` while running.
- **PostgreSQL:** `pg_dump -U nazbeen nazbeen_forex > backup.sql` (container:
  `docker compose exec postgres pg_dump -U nazbeen nazbeen_forex`).
- **Uploads:** archive `media/` (analysis screenshots are user data — never
  delete without owner approval).
- Suggested cadence: daily dump + weekly full archive; keep off-machine.

## 7. Rate limiting

DRF throttles apply in every environment (base settings, resilient to cache
outages): anon `60/min`, authenticated `600/min`, auth endpoints `10/min`.
Tune via `THROTTLE_RATE_*` in `.env`. Behind a proxy, additionally rate-limit at
the reverse proxy for defense-in-depth.

## 8. Deploying a change

1. `uv run python manage.py check`
2. `uv run python manage.py makemigrations --check --dry-run`
3. `uv run pytest`
4. Build/deploy new image → run `manage.py migrate` (compose does this at start;
   for zero-downtime deploys, run migrations as a release step instead).
5. Smoke: `GET /api/health/` returns `200`.

## 9. Incident runbook

| Symptom | Likely cause | Action |
|---|---|---|
| `/api/health/` → 503 | DB down/unreachable | Check Postgres container/`DATABASE_URL`; restart DB |
| Health `cache: fail` | Redis down | Restart Redis; API keeps serving (resilient throttles) |
| 429 responses spike | Throttle misconfig or abuse | Check `THROTTLE_RATE_*`; inspect proxy logs |
| Celery tasks never run | Broker down or worker not started | `docker compose up worker`; check `CELERY_BROKER_URL` |
| WS connect refused | App served as plain HTTP server without ASGI | Run via daphne/`runserver`, not a WSGI-only server |
| MT5 status `unavailable` | Terminal/worker not running on Windows | Start MT5 terminal + `mt5_worker`; check `MT5_WORKER_URL` |

## 10. Security reminders

- `.env` is git-ignored; never commit it (baseline commit verified: only
  `.env.example` tracked).
- Production refuses to boot with an insecure `DJANGO_SECRET_KEY`.
- TLS: set `SECURE_SSL_REDIRECT=true` and `SECURE_HSTS_SECONDS=31536000`
  when serving over HTTPS behind a proxy.
- Analysis-only: there is no endpoint, task, or flag that executes trades.
