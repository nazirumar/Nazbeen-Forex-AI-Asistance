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
`"status": "degraded"` and the failing check reported as `"fail"`. The handler only ever emits `ok` or `degraded` at the top level — there is no `"fail"` status.

| Field | Type | Description |
|---|---|---|
| `status` | string | `ok` or `degraded` |
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
| `POST` | `/api/auth/login/` | Validate credentials; returns `token` + `user`. Bad credentials → `401` with a uniform `{"detail": "Invalid credentials."}` (never reveals whether the account exists). Throttled (auth scope). |
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

## Implemented endpoints (Phases 2–7, 11C–11F additions)

> Paths below are live in the repository (verified against `*/urls.py` during the Phase 9
> documentation audit, 2026-10-09). All require `Authorization: Token <key>` unless noted.

### Market data (Phase 2 — MT5 / mock provider)

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/mt5/status/` | Connection status + broker/server metadata. `mode` is `mock` or `mt5`. Returns `503` when the provider fails. |
| `GET` | `/api/mt5/symbols/` | Symbol discovery (`?search=`). |
| `GET` | `/api/mt5/candles/` | OHLCV for `M1/M5/M15/H1` (`?symbol=&timeframe=&count=&start=`). Every response carries `data_source` (`mock`/`mt5`) and UTC `Z` timestamps. Since Phase 11C/11D it also labels freshness: `market_state` (`open`/`closed`), `stale` (bool), `last_bar_age_sec` (`null` when unknown) and `threshold_sec` — the UI never guesses staleness client-side. |
| `GET` | `/api/mt5/tick/` | Bid/ask/spread (`?symbol=`). Labeled `data_source`. |
| `GET` | `/api/mt5/symbol-info/` | Real symbol metadata (`?symbol=`) from the provider: digits, point, tick size/value, contract size, spread, base/profit currency, volume min/max/step, trade mode. `source` is `mt5` or `mock` (labelled). Invalid/missing symbol → `400`; a provider that cannot supply metadata → `503` (never fabricated). Phase 11G WS1. |

### Market structure (Phase 11D, extended in 11E — detector output for the chart)

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/structure/` | Deterministic ICT/SMC output for `?symbol=&timeframe=&count=` (same validation as candles): `swings`, `events` (BOS/CHOCH/MSS), `fvgs`, `order_blocks`, `liquidity`, plus `mtf` (`H1`/`M15`/`M5`/`M1` biases + `conflicts`). Every event carries its own `type`, `direction`, `index`, `level`/`levels`, `details` and **exact candle timestamps** (`formation_time`/`confirmed_at` etc.) so the chart can anchor overlays without inventing structure. A timeframe whose data cannot be fetched yields bias `null` (unavailable) — **never** a fabricated `NEUTRAL`. Same freshness labels as candles (`market_state`, `stale`, `last_bar_age_sec`, `threshold_sec`). Provider failure → `503` with a generic message. |

**Phase 11E additions to `/api/structure/` are purely additive keys** (the 11D contract above is unchanged):

| Key | Contents |
|---|---|
| `sweeps` | Liquidity sweeps (`detect_sweeps`) of previously confirmed BSL/SSL/equal pools. |
| `displacement` | Displacement candles (`detect_displacement`). |
| `rejections`, `engulfings` | Rejection and engulfing patterns (`detect_rejection`, `detect_engulfing`). |
| `support_resistance` | Clustered swing S/R levels (`detect_support_resistance`); each item's `level` is a real candle price. |
| `sr_flips` | Support↔resistance flips (`detect_sr_flips`). |
| `premium_discount` | At most one item: dealing-range premium/discount state (`details.zone` ∈ `premium`/`discount`/`equilibrium`, `level` = midpoint, `details.range_high`/`range_low`). |
| `mtf_alignment` | Explicit structure alignment: `structure` (`H1`/`M15`/`M5`/`M1` biases or `null`), `aligned` (`null` when no decisive evidence), `dominant`, `conflicts`, `unavailable`. |
| `setup` | Primary trading model (MASTER_SPEC §3.D): `model`, `direction`, `decision` (`BUY`/`SELL`/`WAIT`), `complete`, `stale`, the seven `steps` (each `{key,label,status,time,detail}`; status ∈ `satisfied`/`missing`/`invalid`/`unavailable`), `blocked_by`, `chain`, and `levels` (`entry`/`invalidation`/`target`, `null` unless the chain is complete). |

`fvgs` and `order_blocks` items now also carry `details.lifecycle` (`state` ∈ `open`/`retested`/`mitigated`/`invalidated`/`unknown`). All of these are computed by the deterministic engine; an empty list stays empty and is **never** fabricated.

### Screenshot analysis (Phase 4, history in 11D)

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/analysis/upload/` | Multipart upload (`image`, optional `symbol`, `timeframe`). Validates image (PNG/JPEG, 5 MB, strict content/extension match), runs the analysis pipeline, persists `ScreenshotAnalysis` + screenshot. Returns `201` `{analysis_id, screenshot_stored, result}`; `screenshot_stored` is `false` when persistence failed (the record is kept, the UI says so). |
| `GET` | `/api/analysis/` | **(11D)** Owner-scoped history: newest-first list `{analyses: [{id, symbol, timeframe, created_at, decision, summary, data_source, screenshot_stored}]}`. Strictly the caller's own rows. |
| `GET` | `/api/analysis/{uuid}/` | Retrieve a saved analysis (owner-only). |
| `GET` | `/api/analysis/{uuid}/screenshot/` | **(11C)** The stored screenshot for an analysis the caller owns (binary). `404` for non-owners and when nothing was stored. |

### Risk / trade planning (Phase 5 — analysis-only)

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/risk/trade-plan/` | Computes BUY/SELL/WAIT plan with entry/SL/TP, RR, lot size, reasons. **Never places orders.** Invalid inputs → `WAIT`. |

### Journal, performance & mentor (Phases 7 & 11F — per-user isolation, analysis-only)

The journal records every MASTER_SPEC §3.H field (screenshot link, market snapshot, detected
structures, model/strategy version, estimated probability when available, scenario, entry /
invalidation levels, outcome, notes). **Nothing is fabricated**: an unrecorded value is `null`,
and every performance statistic is `null` when the data to compute it was not recorded. All
endpoints are scoped to the caller's own rows.

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/journal/entries/` | List/search the caller's entries. Query: `q` (notes text), `symbol`, `outcome`, `source`, `limit` (1–200, default 50). Returns `{count, entries:[…]}` with the full spec fields plus the Phase 11G `source`/`source_ref`. A non-integer `limit` → `400`. |
| `POST` | `/api/journal/entries/` | Create an entry. Optional `analysis_session_id` links a stored `ScreenshotAnalysis` and derives symbol/timeframe/market snapshot/structures/model version/analysis timestamp from it. Optional `source` (`manual` default, `screenshot_analysis`, `backtest`, `forward_test`) + `source_ref` type the origin; a linked screenshot analysis defaults `source` to `screenshot_analysis`. Invalid `outcome`/`source`/numeric/JSON fields → `400`. |
| `GET` | `/api/journal/entries/{uuid}/` | Retrieve one entry (owner-only; others → `404`). |
| `PATCH`/`PUT` | `/api/journal/entries/{uuid}/` | Partial/full update (owner-only). |
| `DELETE` | `/api/journal/entries/{uuid}/` | Delete (owner-only); `204` on success, `404` otherwise. |
| `GET` | `/api/journal/search/?q=` | Backward-compatible alias of `GET /api/journal/entries/`. |
| `GET` | `/api/journal/performance/` | Honest aggregate over recorded fields only: outcome `counts`, `win_rate`, `average_rr`, `total_pnl`, `expectancy`, `profit_factor`, `max_drawdown`, plus the `pnl_sample`/`rr_sample` sizes used. Each statistic is `null` when not computable. |
| `GET` | `/api/journal/export/?format=csv\|json` | Export the caller's recorded rows. `json` (default) → `{count, entries}`; `csv` → `text/csv` attachment. Invalid format → `400`. |
| `POST` | `/api/mentor/ask/` | Context-aware mentor answer; references only the caller's saved analyses. Empty `question` → `400`. |

> Note: `?format=` is an *application* parameter here, not DRF content negotiation — the DRF URL
> format override is disabled (`URL_FORMAT_OVERRIDE = None`) so `?format=csv` is not rejected.

### Backtest history (Phase 11F — read-only)

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/backtests/` | The caller's recorded `BacktestRun` metrics (newest first, max 100). Runs recorded **without an owner are not returned** — runs never leak across accounts. Engine-computed metrics only; never fabricated (audit CRIT-01). |

### Backtest execution & reporting (Phase 11G)

All endpoints require authentication and are **owner-scoped**: a run is only ever visible to its
owner (cross-user ids answer **404**, never a disclosure). Validation failures answer **400**;
a per-user cap of 10 active (`queued`/`running`) runs answers **429**. A metric the recorded trades
cannot support is `null` on the wire — never a fabricated `0`.

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/backtests/config/` | Default configuration + valid ranges (symbol, timeframe ∈ {M1,M5,M15,H1}, count 40–20000, initial_balance, risk_pct, spread/commission/slippage, sl/tp, max_daily_loss, max_drawdown_pct, walk-forward sizes). |
| `POST` | `/api/backtests/runs/` | Validate config, create a `BacktestRun` (status `queued`) and enqueue the Celery `heavy`-queue task. Answers **202** with `{run}`. |
| `GET` | `/api/backtests/runs/` | The caller's runs (newest first, max 100): `{count, runs}`. |
| `GET` | `/api/backtests/runs/<uuid>/` | Run detail (`{run}`) incl. `status`, `error`, `config`, `metrics`, `data_source`, `is_walk_forward`, timestamps. |
| `GET` | `/api/backtests/runs/<uuid>/trades/` | Stored simulated trades (`{count, trades}`): side, times, entry/exit/SL/TP, lots, result, pnl, realized R, duration, exit reason, session, weekday. |
| `GET` | `/api/backtests/runs/<uuid>/metrics/` | §6 metrics (`{metrics, status}`): win rate, avg R, gross/net profit, profit factor (`null` + note when undefined), expectancy, max drawdown (+%), avg duration, consecutive streaks, by session/weekday/setup type, and the `assumptions` block. |
| `GET` | `/api/backtests/runs/<uuid>/equity/` | Equity/balance curve (`{points:[{time, equity, balance, drawdown}]}`). |
| `GET` | `/api/backtests/runs/<uuid>/export/?format=csv\|json` | Recorded trades as `text/csv` (attachment) or a JSON document `{run, trades}`. |

> Backtests are **simulated** historical evaluations of the deterministic strategy. No endpoint
> places, schedules or manages any broker order — the platform is analysis-only.

### Forward testing (Phase 11G §9/§10 — simulated)

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/forwardtests/config/` | Default configuration + valid ranges (symbol, timeframe ∈ {M1,M5,M15,H1}, count 40–20000, sl_pips, tp_pips, max_active_runs). |
| `POST` | `/api/forwardtests/runs/` | Validate config and create a **simulated** forward test (status `active`). Invalid config → `400`; more than 5 active runs → `429`. Returns `{run}` (**201**). |
| `GET` | `/api/forwardtests/runs/` | The caller's runs (newest first, max 100): `{count, runs}`. |
| `GET` | `/api/forwardtests/runs/<uuid>/` | Run detail: status, config, checkpoint (`last_observed_bar`), `observations_count`, `outcomes` breakdown, `data_source`, safe `error`. Owner-only (others → `404`). |
| `GET` | `/api/forwardtests/runs/<uuid>/observations/` | Recorded decisions (`{count, observations}`): bar time, decision, reason, entry/SL/TP/R, snapshot, `simulated`, outcome (`PENDING`/`WIN`/`LOSS`/`BE`) + outcome R. `?limit=` 1–1000. |
| `POST` | `/api/forwardtests/runs/<uuid>/observe/` | Run one observation cycle (Celery `heavy` queue; eager in dev/test). Records at most one decision per bar (dedupe), resolves earlier pending outcomes, advances the checkpoint. Non-active run → `409`. Answers **202** with `{run}`. |
| `POST` | `/api/forwardtests/runs/<uuid>/stop/` | Stop observing an active run (status `stopped`). Answers `{run}`. |
| `POST` | `/api/forwardtests/observations/<uuid>/journal/` | Create a typed journal entry from an observation (`source="forward_test"`, `source_ref=<observation id>`). Owner-only. Answers **201** `{journal_entry_id, source}`. |

> Forward tests are **simulated** — the deterministic engine is observed on fetched candles and
> no orders are placed. Every run/observation is labelled `simulated: true`; a metric that cannot
> be computed is `null`, never invented.

### WebSocket (Phase 10 — read-only operational status)

| Protocol | Path | Notes |
|---|---|---|
| `ws` | `/ws/status/` | On connect: pushes the same public health snapshot as `GET /api/health/` (database/cache/celery checks, version, UTC time — no secrets). Accepts exactly one client action: `{"action": "ping"}` → `{"type": "pong", "time": ...}`. Any other message → `{"type": "error", ...}`. **No commands, no trading actions — read-only by design.** Requires an ASGI server (daphne/`runserver`); in-memory channel layer by default, Redis when `USE_REDIS_CHANNELS=true`. |

## Planned endpoints (not yet implemented)

| Endpoint | Purpose |
|---|---|
| `GET/PATCH` `/api/auth/me/profile/` | Update user profile/settings (e.g. `display_timezone`) |
| Password reset | Not implemented; out of scope for the current phases (audit L-07) |

> Each phase updates this file in the same commit as the endpoints it adds.
