# API — Endpoint documentation

> Conventions are established in Phase 1 and extended each phase. Base path: `/api/`.
> All endpoints return JSON. All timestamps are ISO-8601 in **UTC** (suffix `Z`).

## Conventions

- Versioning: URL prefix `/api/` (a `/api/v1/` prefix is introduced if a breaking change is ever
  needed).
- Errors: DRF default error shape `{"detail": "..."}` for non-field errors, field maps otherwise.
- Authentication: none required for health endpoints; all analysis/journal endpoints require
  authentication (Phase 2).
- Rate limiting and upload limits are introduced in Phase 2 (MASTER_SPEC §4).
- Health endpoints are intended for liveness/readiness probes and expose no secrets.

## Phase 1 endpoints

### `GET /api/health/`

Application health check. Performs checks for database, cache (Redis), and Celery broker reachability/eager mode. Health endpoints expose no secrets and are intended for liveness/readiness probes.

**Response `200 OK`** (all critical checks `ok`/`eager`/`unconfigured`)

```json
{
  "status": "ok",
  "service": "nazbeen-forex-ai",
  "version": "0.1.0",
  "time": "2026-10-08T12:00:00Z",
  "checks": {
    "database": "ok",
    "cache": "ok",
    "celery": "eager"
  }
}
```

**Response `503 Service Unavailable`** when any critical check fails, with
`"status": "degraded"` (or `"status": "fail"` for broker-unreachable in strict cases) and the failing check reported as `"fail"`.

| Field | Type | Description |
|---|---|---|
| `status` | string | `ok`, `degraded`, or `fail` |
| `service` | string | Fixed service identifier |
| `version` | string | Application version from settings |
| `time` | string | Current UTC time, ISO-8601 (ends with `Z`) |
| `checks.database` | string | `ok` or `fail` |
| `checks.cache` | string | `ok` or `fail` |
| `checks.celery` | string | `ok`, `eager`, `unconfigured`, or `fail` |

### Auth endpoints (token-based, analysis-only)

All auth endpoints accept JSON; return `401` on missing/invalid tokens.

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/auth/register/` | Create account + profile; returns `token` + `user` (no password). Password validation enforced. Throttled (auth scope). |
| `POST` | `/api/auth/login/` | Validate credentials; returns `token` + `user`. Throttled (auth scope). |
| `POST` | `/api/auth/logout/` | Revoke the current token (requires `Authorization: Token …`). Throttled (defaults). |
| `GET`  | `/api/auth/me/`    | Return current authenticated user + embedded `profile` (`display_timezone`, timestamps UTC). Throttled (defaults). |

Example register response (201):

```json
{
  "token": "...",
  "user": {
    "id": 1,
    "username": "trader1",
    "email": "t1@example.com",
    "date_joined": "2026-10-08T12:00:00Z",
    "profile": {"display_timezone": "UTC", "created_at": "2026-10-08T12:00:00Z"}
  }
}
```

Rate limiting: `auth` scope defaults to `10/min` (login/register). Defaults are resilient — if the throttling cache (Redis) is unreachable, auth endpoints still respond (rate limiting degraded). See ADR-008.

## Implemented endpoints (Phases 2–7)

> Paths below are live in the repository (verified against `*/urls.py` during the Phase 9
> documentation audit, 2026-10-09). All require `Authorization: Token <key>` unless noted.

### Market data (Phase 2 — MT5 / mock provider)

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/mt5/status/` | Connection status + broker/server metadata. `mode` is `mock` or `mt5`. Returns `503` when the provider fails. |
| `GET` | `/api/mt5/symbols/` | Symbol discovery (`?search=`). |
| `GET` | `/api/mt5/candles/` | OHLCV for `M1/M5/M15/H1` (`?symbol=&timeframe=&count=&start=`). Every response carries `data_source` (`mock`/`mt5`) and UTC `Z` timestamps. |
| `GET` | `/api/mt5/tick/` | Bid/ask/spread (`?symbol=`). Labeled `data_source`. |

### Screenshot analysis (Phase 4)

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/analysis/upload/` | Multipart upload (`image`, optional `symbol`, `timeframe`). Validates image, runs analysis pipeline, persists `ScreenshotAnalysis`. Returns `201` `{analysis_id, result}`. |
| `GET` | `/api/analysis/{uuid}/` | Retrieve a saved analysis (owner-only). |

### Risk / trade planning (Phase 5 — analysis-only)

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/risk/trade-plan/` | Computes BUY/SELL/WAIT plan with entry/SL/TP, RR, lot size, reasons. **Never places orders.** Invalid inputs → `WAIT`. |

### Journal & mentor (Phase 7 — per-user isolation)

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/journal/entries/` | Create a journal entry. |
| `GET` | `/api/journal/search/?q=` | Search the caller's own entries. |
| `POST` | `/api/mentor/ask/` | Context-aware mentor answer; references only the caller's saved analyses. |

### WebSocket (Phase 10 — read-only operational status)

| Protocol | Path | Notes |
|---|---|---|
| `ws` | `/ws/status/` | On connect: pushes the same public health snapshot as `GET /api/health/` (database/cache/celery checks, version, UTC time — no secrets). Accepts exactly one client action: `{"action": "ping"}` → `{"type": "pong", "time": ...}`. Any other message → `{"type": "error", ...}`. **No commands, no trading actions — read-only by design.** Requires an ASGI server (daphne/`runserver`); in-memory channel layer by default, Redis when `USE_REDIS_CHANNELS=true`. |

## Planned endpoints (not yet implemented)

| Endpoint | Purpose |
|---|---|
| `GET/PATCH` `/api/auth/me/profile/` | Update user profile/settings (e.g. `display_timezone`) |
| `POST /api/backtests/`, `GET /api/backtests/{id}/` | Backtest run API (engine exists, no HTTP surface yet) |
| `GET /api/analytics/performance/` | Aggregated performance reports |
| Journal export endpoints | CSV/PDF journal reports |

> Each phase updates this file in the same commit as the endpoints it adds.
