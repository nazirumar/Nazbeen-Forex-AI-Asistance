# PHASE 11G — Real MT5 Integration, Advanced Backtesting, AI Analysis Validation & Demo Forward Testing

**Status:** IN PROGRESS — WS2 (backtest execution + reporting API) and WS3 (backtesting dashboard)
**landed, tested and green** (2026-10-14). WS1/WS4/WS5/WS6/WS7 still outstanding — see §4.
**Authority:** the owner's Phase 11G specification is authoritative for this phase. Where the spec
overlaps existing Phase 11A–11F functionality, existing code is **preserved and verified**, never
rewritten. **Analysis-only: no order execution, no broker order placement, no live position
management anywhere.**

> This phase is large and is being delivered in small, reviewable increments (the project rule is
> "serve the current phase scope, verify, document, stop"). This report is updated as each
> workstream lands; §4 records exactly what is implemented/verified vs. still outstanding.

---

## 1. Mandatory audit — what already exists (baseline: Phase 11F, backend 394 tests passing)

| Subsystem | Location | State |
|---|---|---|
| MT5 connector + mock adapter | `marketdata/{factory,providers/*}.py`, `mt5_worker/` | Real Windows MT5 provider + labelled mock; UTC normalization, future-timestamp rejection, suffix/staleness/closure handling (11A/11C) |
| Market-data API | `marketdata/{views,urls}.py` | `/api/mt5/{status,symbols,candles,...}` authenticated |
| ICT/SMC detectors | `structure/*` | All 19 §3.C detectors; `confirmed_at` on events (11E) |
| Primary trading model | `structure/{analysis,model}.py` | Chronological state machine; BUY/SELL/WAIT; deterministic authority |
| Screenshot analysis + LangGraph | `analysis/*` | Upload/validate, vision+reasoning providers, 10-node `StateGraph`, reconciliation, persistence (11B/11D/11E) |
| Risk engine | `risk/*` | SL/TP, RR, sizing, spread filter, `/api/risk/trade-plan/` (analysis-only) |
| Backtest engine | `backtesting/{engine,walkforward,probability}.py` | Real SL/TP bar-by-bar simulation, costs, honest metrics, walk-forward splits (11A/11C) |
| Backtest history API | `backtesting/{views,urls}.py` | Read-only `GET /api/backtests/` owner-scoped (11F) |
| Journal | `journal/*` | Full §3.H fields, CRUD, performance/export, mentor (11F) |
| Auth / dashboard / chart | `accounts/*`, `frontend/*` | Token auth, dark dashboard shell, Lightweight Charts (11D), backtests/analytics/mentor/settings pages (11G start) |

Baseline re-verified for 11G: `manage.py check` clean · `makemigrations --check` no changes ·
`uv run pytest` **394 passed** · frontend `tsc` 0 errors · `next build` 15 routes.

---

## 2. Gap analysis (spec §→ current state → gap → plan)

| Spec § | Requirement | Current state | Gap | Plan |
|---|---|---|---|---|
| §2 | Real MT5 market data, symbol resolution, metadata, quality, connection mgmt | Implemented (11A/11C) | Add explicit **symbol-metadata** endpoint + connection-error detail surface; document | WS1 |
| §3 | MTF ICT/SMC (H1/M15/M5/M1) bullish/bearish 7-step, chronological, WAIT on missing | Implemented (11E) | **Verify** with regression tests; record contradictions | WS5 (verify) |
| §4 | E2E screenshot→MT5 reconcile→structure→bias→model→risk→persist | Implemented (11D/11E) | **Verify** deterministic authority + disagreement handling | WS5 (verify) |
| §5 | Backtest **execution** + reporting API (runs CRUD, trades, metrics, equity, export) | Only read-only list | **Missing**: run config/status model, Celery task, execution + per-run endpoints | **WS2 (primary new work)** |
| §6 | Extended metrics (avg R, durations, streaks, by session/weekday/setup, equity/balance, walk-forward, in/out-of-sample) | Partial (engine has basics) | Missing metrics/curves/splits | **WS2** |
| §7 | Backtest dashboard (config form, progress, results, trade inspection) | Read-only table only | Missing form + progress + detail | **WS3** |
| §8 | Forward-testing engine (observe closed candles, record decisions, track outcomes, dedupe, checkpoints) | Absent | **Missing** entirely | **WS4** |
| §9 | Forward-testing dashboard | Absent | Missing | WS4 |
| §10 | Journal integration for backtest/forward records, typed separation | Journal exists | Missing source-typed linkage | WS4/WS6 |
| §11 | Reliability/failure handling matrix | Partial | Add explicit handling + tests for new paths | WS2/WS4 |
| §12 | Security/isolation for new endpoints | Pattern exists | Apply to all new endpoints | WS2/WS4 |
| §13 | Automated tests (backend + frontend) | Suite exists | Add per workstream | each WS |
| §14 | Live MT5/LLM verification | Owner-run | **NOT VERIFIED here** (no terminal/keys) unless available | WS7 |
| §15 | Docs | This file | Update listed docs | WS7 |

---

## 3. Implementation plan (workstreams, in order)

**WS1 — MT5 surface completion.** Add a symbol-metadata endpoint (digits, point, tick size/value,
contract size, spread) and expose connection-error detail, reusing `marketdata` providers. Tests
with the mocked connector only. *Preserve all existing MT5 routes/contracts.*

**WS2 — Backtest execution + reporting API (primary new backend work).**
- Extend `BacktestRun` **additively** (status, error, started/finished, config snapshot,
  strategy_version, split labels) and add `BacktestTrade` (+ equity/balance points).
- New `backtesting/services.py`: validate config → fetch validated candles → run
  `engine`/`walkforward` chronologically → persist trades → compute §6 metrics (null when not
  computable, sample sizes reported) → curves.
- New `backtesting/tasks.py`: Celery task with ownership + failure capture; eager in dev/test.
- Endpoints under `/api/backtests/runs/…` (create/list/detail/trades/metrics/equity/export),
  **keeping `GET /api/backtests/` compatible**. Auth + per-user isolation + throttling + resource
  limits + strict validation (400).
- Tests: config validation, execution, cost accounting, PF/drawdown math, walk-forward split
  separation, isolation, Celery failure capture.

**WS3 — Backtesting dashboard.** Extend `/dashboard/backtests` with the config form, run status,
results (equity/drawdown/summary/tables), and trade inspection using the existing chart. Frontend
tests for the form, validation, status, metrics, curve mapping, trade inspection, missing-data.

**WS4 — Forward-testing engine + dashboard.** `forwardtest` app: `ForwardTestDecision` +
checkpoint models, a Celery task that observes newly completed M1 candles, evaluates the existing
model, records BUY/SELL/WAIT + evidence + rejection reasons, tracks hypothetical outcomes
chronologically with costs, dedupes by (symbol, strategy_version, candle), and resumes from
checkpoints. Dashboard with the §9 panels; all results labelled **simulated**. Journal linkage
(§10) with a `source` discriminator. Tests: dedupe, restart recovery, WAIT recording, cost/outcome
math, isolation, provider-failure handling.

**WS5 — Verify §3/§4.** Regression tests asserting chronological no-lookahead MTF evaluation and
deterministic authority over the LLM (no new behaviour).

**WS6 — Journal integration.** Typed `source` on `JournalEntry` linkage so manual / backtest /
forward-test / screenshot-analysis records stay distinct; tests.

**WS7 — Docs + live verification.** Update `PROJECT_PROGRESS`, `ARCHITECTURE`, `API`, `TESTING`,
`OPERATIONS`, `ROADMAP`; record live MT5/LLM status truthfully (NOT VERIFIED where unavailable);
recommend Phase 11H scope.

**Delivery rule for every WS:** implement → tests in the same WS → run CI parity
(`check` → `makemigrations --check` → `pytest`; frontend `vitest`/`tsc`/`build`) → document → no
regression of 11A–11F. Do not weaken/delete tests. Do not commit without owner approval.

---

## 4. Results

### 4.0 Already landed at the start of 11G (interim dashboard scope)

- Missing P2.5 dashboard pages: `/dashboard/{backtests,analytics,mentor,settings}` wired to
  **existing** endpoints (no new backend), sidebar nav added, 13 new frontend tests; the sidebar
  nav assertion in `shell.test.tsx` updated. `tsc` clean; `next build` → 15 routes.
- **Container defect fixed:** `frontend/.dockerignore` was missing → the compose `frontend`
  build context shipped `node_modules`/`.next` (536 MB) and stalled. Added the file.

### 4.1 Docker / CI verification (audit M-11/M-13)

- **GitHub Actions CI: PASSED** for the 11F commit `4ebbc10` — workflow "CI", run #12,
  `conclusion: success` (read directly from the GitHub API).
- **Docker daemon: started** (Docker Desktop server 29.8.2).
- **Docker Compose build: SUCCEEDED** — `docker compose --profile app build` built the backend,
  worker and frontend images; the frontend image compiled all 15 routes inside the container. The
  first attempt failed because egress to `ghcr.io` transiently timed out; the retry pulled the
  base image normally. (Compose **run** of the full app profile is a separate step, recorded in
  §4.9.)

### 4.2 WS2 — Backtest execution + reporting API ✅ LANDED

**Models** (`backtesting/models.py`, migration `0003_backtestrun_config_…`):
- `BacktestRun` extended **additively**: `status` (queued/running/completed/failed, default
  `completed` so Phase 11F rows keep their meaning), `error`, `config` (JSON snapshot), `strategy_version`,
  `is_walk_forward`, `note`, `data_source`, `started_at`, `finished_at`.
- New `BacktestTrade`: `index`, `side`, `entry_time`, `exit_time`, `entry`, `exit_price`, `sl`, `tp`,
  `lots`, `result`, `pnl`, `realized_r`, `duration_seconds`, `exit_reason`, `session`, `weekday`,
  `commission`, `slippage`, `spread_cost`.

**Engine** (`backtesting/engine.py`, additive only — defaults preserve prior behaviour):
`run_backtest` gained optional `initial_balance`, `max_daily_loss` (absolute, per-UTC-day) and
`max_drawdown_pct` portfolio stops, both **disabled at 0**. `walkforward.walk_forward` gained
`**run_kwargs` forwarded to every out-of-sample `run_backtest`, so costs/sizing apply to splits.

**Services** (`backtesting/services.py`, new): strict `validate_config` (symbol, timeframe ∈
{M1,M5,M15,H1}, `count` 40–20000, `initial_balance`>0, `0<risk_pct≤100`, non-negative costs,
`sl/tp`>0, `0≤max_drawdown_pct≤100`, ISO start/end, walk-forward sizes); risk-based `compute_lots`;
`fetch_candles` via the provider factory (chronology/length validated, provider failures → safe
message); `execute_run` (persist trades, compute metrics); §6 `compute_metrics` — win rate, average
realized R, gross/net profit, profit factor (**null + note** when undefined), expectancy, max
drawdown + %, avg duration, consecutive win/loss streaks, **by session / weekday / setup type**,
`assumptions` block (spread/commission/slippage/SL/TP/sizing); `equity_curve`; CSV/JSON `export_run`;
`serialize_run` (superset of the 11F fields). Every non-computable value is `None`; sample size is
always reported; no fabricated figures.

**Task** (`backtesting/tasks.py`, new): `run_backtest_task` — routed to the `heavy` queue by
`CELERY_TASK_ROUTES`, eager in dev/test, captures failures on the run (status `failed` + safe error).

**Endpoints** (`backtesting/urls.py`): `POST/GET /api/backtests/runs/`,
`GET /api/backtests/runs/<uuid>/`, `…/trades/`, `…/metrics/`, `…/equity/`,
`…/export/?format=csv|json`, `GET /api/backtests/config/`. **`GET /api/backtests/` is unchanged.**
All authenticated, owner-scoped (cross-user id → 404), active-run cap (10 → 429), validation → 400.

**Tests:** `backtesting/tests/test_backtest_api_11g.py` — **29 tests**: config validation
(parametrised), risk sizing, metric mathematics (PF/drawdown/avg-R/streaks/grouping), null-metric
honesty, engine daily-loss & drawdown stops, walk-forward kwargs forwarding, insufficient-data
failure, Celery failure capture, mock-provider completion, auth, per-user isolation, create+retrieve,
invalid-config 400, trades/metrics/equity/export, config endpoint, active-run 429.

### 4.3 WS3 — Backtesting dashboard ✅ LANDED

`frontend/components/backtests/backtest-console.tsx` (new) + `/dashboard/backtests` updated:
configuration form (symbol/timeframe/candles/balance/risk/spread/commission/slippage/SL/TP/
walk-forward) → `POST /api/backtests/runs/`, status badge (word only — **no invented progress
percentage**), failed-run safe error, §6 metric tiles (`null` → "—"), assumptions line, inline SVG
equity curve, simulated-trades table with row selection → trade detail, and CSV/JSON export via the
real per-run endpoint. No live-execution control exists anywhere. Types extended additively in
`frontend/lib/types.ts`; fixtures in `frontend/test/helpers.ts`.

**Tests:** `frontend/test/backtest-console.test.tsx` — **8 tests** (form render, submit+results,
null-metric honesty, failed run, validation error, trade inspection, export endpoint, no
live-execution buttons).

### 4.4 WS1 — MT5 symbol-metadata endpoint ✅ LANDED

`MarketDataProvider.get_symbol_info(symbol)` added as a **concrete** base method that raises
`MarketDataProviderError` — existing subclasses (including test doubles) keep working, and a provider
that cannot supply metadata yields **503** rather than a fabricated digits/point/tick value.
`MockMarketDataProvider.get_symbol_info` returns internally consistent values explicitly labelled
`source: mock`; `MT5MarketDataProvider.get_symbol_info` reads real `mt5.symbol_info` (digits, point,
tick size/value, contract size, spread, base/profit currency, volume min/max/step, trade mode) and
labels `source: mt5`.

**Endpoint:** `GET /api/mt5/symbol-info/?symbol=…` (authenticated) — strict symbol validation → 400,
provider failure → 503 (generic), unexpected → 500.

**Tests:** `marketdata/tests/test_symbol_info_api.py` — **5 tests** (auth required, labelled mock
metadata, invalid-symbol 400, provider-without-metadata 503, mock consistency).

### 4.5 WS4 — Simulated forward-testing engine + dashboard ✅ LANDED

**App** `nazbeen_forex_ai.forwardtest` (new, registered in `INSTALLED_APPS`, root URLs, Celery
`heavy` queue).
- **Models** (migration `0001_initial`): `ForwardTestRun` (symbol, timeframe, config snapshot,
  status active/stopped/failed, `data_source`, strategy version, checkpoint `last_observed_bar` /
  `last_observed_at`, `observations_count`, safe `error`) and `ForwardTestObservation` (decision,
  reason, entry/sl/tp/rr, snapshot, `simulated=True`, outcome PENDING/WIN/LOSS/BE, outcome price/R,
  resolved_at) with a `(run, bar_time)` **unique constraint** for dedupe.
- **Services** (`forwardtest/services.py`): strict `validate_config`; `observe_run` fetches candles
  via the shared provider path, evaluates the Phase 11E deterministic engine on the closed window
  (no look-ahead — only bars up to and including the observed bar), records levels from the config's
  SL/TP, checkpoints the run, dedupes per bar, and resolves earlier PENDING observations from later
  bars (**stop-loss first** on a bar that touches both). Every run/observation is labelled
  **simulated**. No order-execution code exists.
- **Task** (`forwardtest/tasks.py`): `observe_run_task` on the `heavy` queue (eager in dev/test);
  captures failures on the run (status `failed` + safe error).
- **Endpoints:** `POST/GET /api/forwardtests/runs/`, `GET …/<uuid>/`, `…/observations/`,
  `POST …/<uuid>/observe/`, `POST …/<uuid>/stop/`,
  `POST /api/forwardtests/observations/<uuid>/journal/`, `GET /api/forwardtests/config/`.
  All authenticated, owner-scoped (cross-user → 404), active-run cap 5 → 429, validation → 400.
- **§10 journal linkage:** `journalize_observation` creates a typed journal row
  (`source="forward_test"`, `source_ref=<observation id>`, tags `[forward_test, simulated]`) — never
  claiming a real trade.

**Tests:** `forwardtest/tests/test_forwardtest_api_11g.py` — **25 tests** (config validation,
deterministic levels, observation creation, per-bar idempotence, outcome tracking, stop-first
resolution, Celery failure capture, journal typing + cross-user rejection, auth, create/list/detail,
isolation, observe/stop/conflict, config, active-run cap).

### 4.6 WS5 — §3 / §4 regression verification ✅ LANDED

`analysis/tests/test_phase_11g_invariants.py` — **10 tests** pinning the cross-cutting invariants:
MTF reads are deterministic from confirmed swings; real conflicts surface; an unavailable timeframe
is `null` (never NEUTRAL); an AI bullish reading cannot override a deterministic WAIT; a
deterministic BUY is retained when the AI disagrees; unsynchronized data forces WAIT with an
explanation; mock and stale data are never synchronized; fresh MT5 data is.

### 4.7 WS6 — Journal source typing ✅ LANDED

`JournalEntry` gained `source` (manual/screenshot_analysis/backtest/forward_test, default `manual`)
and `source_ref` (opaque origin id) additively; migration
`journal/0003_journalentry_source_journalentry_source_ref.py`. The service validates `source`,
defaults a linked screenshot analysis to `source="screenshot_analysis"`, filters by `source`, and
includes both fields in the serializer, list/search and CSV/JSON export.

**Tests:** `journal/tests/test_journal_source_11g.py` — **5 tests** (default manual, typed create,
invalid rejected, list filter, export includes source).

### 4.8 WS7 — Docs + live verification ✅ LANDED

- This report updated (§4.4–4.8, §4.9, §5, §6); `docs/PROJECT_PROGRESS.md`, `docs/API.md`,
  `docs/DECISIONS.md` (ADR-015) updated.
- **Live MT5:** NOT VERIFIED — no MetaTrader5 terminal is available in this environment. All MT5
  paths are exercised through the labelled mock provider only; real-terminal behaviour is owner-manual.
- **Live LLM:** NOT VERIFIED — no provider API keys are configured here; the mock providers are used.
  Real provider calls are owner-manual.

### 4.9 Verification table

| Check | Command | Result |
|---|---|---|
| Django check | `uv run python manage.py check` | **clean** (2026-10-14) |
| Migrations | `uv run python manage.py makemigrations --check --dry-run` | **No changes detected** |
| Backend tests | `uv run pytest` | **468 passed, 0 failed** (423 + WS1 5 + WS4 25 + WS5 10 + WS6 5) |
| Frontend tests | `npx vitest run --no-file-parallelism` | **140 passed / 15 files** (132 + WS4 console 8) |
| Frontend types | `npm run typecheck` | **exit 0** |
| Frontend build | `npm run build` | **exit 0 — 15 → 16 routes** (added `/dashboard/forward`) |
| Docker build | `docker compose --profile app build` | **built** (backend/worker/frontend) |
| GitHub CI | Actions run for `4ebbc10` (last pushed) | **success** (run #12) |
| Live MT5 terminal | manual, owner host | **NOT VERIFIED** (no terminal here) |
| Live LLM providers | manual, owner host | **NOT VERIFIED** (no keys here) |

> Frontend vitest on Windows occasionally fails to spawn a worker (the workspace path contains
> spaces); run with `--no-file-parallelism` or re-run. The clean run above is 15 files / 140 tests.

---

## 5. Deliverables (10)

1. **Files changed/added** — backend: `marketdata/{providers,mock,mt5_connector,views,urls}.py`;
   `journal/{models,services,views}.py` + migration `0003`; `analysis/tests/test_phase_11g_invariants.py`;
   `backtesting/*` (WS2/WS3, prior increment); new app `forwardtest/` (models, services, tasks, views,
   urls, admin, apps, migration `0001`, tests). Frontend: `components/forwardtests/forwardtest-console.tsx`,
   `app/dashboard/forward/page.tsx`, `components/layout/sidebar.tsx`, `lib/types.ts`,
   `test/{helpers,shell,forwardtest-console}.*`. Settings/root URLS updated.
2. **Migrations** — `backtesting/0003_…`, `journal/0003_journalentry_source_journalentry_source_ref.py`,
   `forwardtest/0001_initial.py`. `makemigrations --check` clean.
3. **Endpoints** — `GET /api/mt5/symbol-info/`; forward-testing surface (§4.5); plus the WS2
   backtest surface. All authenticated + owner-scoped.
4. **Frontend** — `/dashboard/forward` console (start/observe/stop, observations table, typed
   journal action), sidebar entry, additive types + fixtures.
5. **Backend test results** — `uv run pytest` → **468 passed, 0 failed** (was 423).
6. **Frontend test results** — `npx vitest run --no-file-parallelism` → **140 passed / 15 files**
   (was 132/14); `npm run typecheck` exit 0; `npm run build` exit 0.
7. **Live MT5 status** — **NOT VERIFIED** (no terminal in this environment).
8. **Live LLM status** — **NOT VERIFIED** (no provider keys in this environment).
9. **Unresolved issues** — live MT5/LLM verification (owner-manual); scheduled/automatic forward-test
   observation (a Celery beat schedule) is not configured — observation is manual via the endpoint;
   Docker compose full-run of the app profile is not re-executed this increment.
10. **Recommended Phase 11H plan** — see §6.

## 6. Recommended Phase 11H plan

1. Optional Celery-beat schedule for active forward tests (periodic `observe_run_task`) with a
   per-run interval and rate limiting.
2. Live-verification harness: a documented, owner-run checklist for MT5 symbol-info + candle sync
   and real LLM providers, recording results back into the docs.
3. Forward-test aggregate analytics (per-source journal performance split by `source`, sample sizes,
   `null` when not computable) reusing the 11G metrics conventions.
4. Re-run `docker compose --profile app up` end-to-end and record it.
5. Address the outstanding Dependabot findings if in scope.

Owner approval is required before starting Phase 11H.

