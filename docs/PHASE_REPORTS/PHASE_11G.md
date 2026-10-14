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

### 4.4–4.8 Outstanding workstreams

WS1 (MT5 symbol-metadata endpoint), WS4 (forward-testing engine + dashboard + §10 journal source
discriminator), WS5 (verify §3/§4 regression), WS6 (journal source typing), WS7 (remaining docs +
live verification) are **not yet implemented**. Backend + frontend suites for the landed work are
green (see §4.9); the outstanding items are listed honestly rather than claimed.

### 4.9 Verification table

| Check | Command | Result |
|---|---|---|
| Django check | `uv run python manage.py check` | **clean** (fresh run 2026-10-14, WS2) |
| Migrations | `uv run python manage.py makemigrations --check --dry-run` | **No changes detected** (WS2) |
| Backend tests | `uv run pytest` | **423 passed, 0 failed** (WS2: 394 baseline + 29 new) |
| Frontend tests | `npx vitest run` | **132 passed / 14 files** (11F baseline: 111/11) |
| Frontend types | `npm run typecheck` | **exit 0** (WS3) |
| Frontend build | `npm run build` | **exit 0 — 15 routes** |
| Docker build | `docker compose --profile app build` | **built** (backend/worker/frontend) |
| GitHub CI | Actions run for `4ebbc10` | **success** (run #12) |

> Frontend vitest on Windows occasionally fails to spawn a worker (the workspace path contains
> spaces); a re-run is clean. The clean run above is 14 files / 132 tests.
