# PHASE 11F — Journal, Analytics & Reporting + Infra Verification & Doc Errata

**Status:** IN PROGRESS — plan written before code changes (2026-10-14) · **Scope:** WS-E
(journal spec §3.H fields, full CRUD, performance/export endpoints, backtest-history surfacing —
audit M-15 / RECOMMENDED_FIXES P2.5) and WS-F (infrastructure verification + documentation errata
— audit M-11..M-16, H-10, L-01/L-03..L-07). Analysis-only: **no live order execution anywhere.**

---

## 0. Implementation plan (written before modifying code)

### 0.1 Preparation findings

Inspected: `journal/{models,services,views,urls,tests}` , `analysis/{models,views,schemas}.py`,
`backtesting/{models,views}.py`, `risk/views.py`, `nazbeen_forex_ai/urls.py`,
`docs/{MASTER_SPEC,API,ROADMAP,PROJECT_PROGRESS}.md`, `docs/audits/{CRITICAL_ISSUES,RECOMMENDED_FIXES,PHASE_11_PLAN}.md`.

| Area | State after 11E | 11F work |
|---|---|---|
| Journal model | `symbol/timeframe/scenario_decision/entry/sl/tp/rr/outcome/pnl/notes/tags/metrics` only | add spec §3.H fields: screenshot link, analysis timestamp, market snapshot, detected structures, model/strategy version, estimated probability |
| Journal CRUD | create + search only | add retrieve / update / delete (owner-scoped) |
| Journal analytics | none | performance aggregation (honest `null` when not measurable) |
| Journal export | none | CSV + JSON export of recorded rows |
| Backtest history | `BacktestRun` model exists, **no endpoint** | read-only `GET /api/backtests/` |
| README / API.md / ROADMAP / phase reports | stale claims (H-10, M-14, M-16) | errata addenda + alignment (do not rewrite history) |
| `.env.example` | ships `MT5_USE_MOCK=false` (M-12) | default `true`; document/remove dead vars |
| Production settings | HSTS off by default (L-04) | default on, documented override |
| Frontend header | static clock/EURUSD unlabeled (L-06) | label as static |
| Docker / GitHub CI | never built / never run | **verification is BLOCKED locally** (no Docker host); recorded honestly |

### 0.2 Work packages

**WP1 — Journal model (migration `journal/0002`).** Add to `JournalEntry`:
`screenshot_analysis` (FK → `analysis.ScreenshotAnalysis`, `SET_NULL`), `analysis_timestamp`,
`market_snapshot` (JSON), `detected_structures` (JSON), `model_version`, `strategy_version`,
`estimated_probability` (nullable float). Existing fields/records unchanged.

**WP2 — Journal service.** Owner-scoped `get_entry`/`update_entry`/`delete_entry`; `save_entry`
extended (links a `ScreenshotAnalysis` by id and derives model version / market snapshot /
structures / analysis timestamp from the stored analysis when not supplied); `search` gains
optional `symbol`/`outcome` filters; `performance` and `export` (see WP3). **No fabrication:** a
field that was never recorded is `None`/`[]`, never a default.

**WP3 — Performance & export.** `performance(user)` aggregates only recorded values: outcome
counts, win rate, average R:R, total P&L, expectancy, profit factor, max drawdown — each `null`
when the underlying data is absent. `export(user, fmt)` yields CSV/JSON rows of the recorded
fields (no derived claims).

**WP4 — API.** `GET/POST /api/journal/entries/`, `GET/PATCH/DELETE /api/journal/entries/<uuid>/`,
`GET /api/journal/performance/`, `GET /api/journal/export/?format=csv|json`; read-only
`GET /api/backtests/`. Strict input validation → 400 with safe messages; generic 500 pattern
(mirrors `risk/views.py`).

**WP5 — Tests.** Model/service/API coverage: field round-trip, ownership isolation (404 for
another user's entry), CRUD lifecycle, performance math on recorded vs. missing data,
export formats, validation errors, backtest listing.

**WP6 — WS-F doc errata + config.** README/API.md/ROADMAP/PROJECT_PROGRESS alignment; errata
addenda for PHASE_02/04/06/08; `.env.example` M-12; production HSTS default (L-04); frontend
static-label fix (L-06); L-01/L-03/L-05/L-07 handled or explicitly deferred with rationale.

**WP7 — Verification.** `manage.py check` → `makemigrations --check --dry-run` → `pytest`;
frontend `test`/`typecheck`/`build`.

### 0.3 Explicit non-actions / blocked

- **Docker build + compose run: BLOCKED** — no Docker host available (unchanged from M-11/M-13).
  Compose config may carry safe, review-only fixes but **no "deployable" claim** is made.
- **GitHub CI execution**: triggered by the Phase 11E push; outcome recorded if observable,
  otherwise marked unverified.
- No live trading, no fabricated probability/statistics, no history rewriting.

---

## 1. Results

**Status: IMPLEMENTED 2026-10-14 — awaiting owner approval before Phase 11G.**

### 1.1 WS-E — Journal, analytics & reporting (M-15 / P2.5)

Delivered:

- **Model (`journal/models.py`, migration `journal/0002_journalentry_analysis_timestamp_and_more.py`)**
  — `JournalEntry` now records every MASTER_SPEC §3.H field: `screenshot_analysis` (FK →
  `analysis.ScreenshotAnalysis`, `SET_NULL`), `analysis_timestamp`, `market_snapshot`,
  `detected_structures`, `model_version`, `strategy_version`, `estimated_probability`, alongside the
  existing symbol/timeframe/scenario/levels/outcome/notes/tags/metrics. Additive only.
- **Service (`journal/services.py`)** — owner-scoped `get_entry`/`update_entry`/`delete_entry`;
  `save_entry` extended; linking an `analysis_session_id` derives symbol/timeframe/market
  snapshot/detected structures/model version/analysis timestamp from the stored analysis when not
  supplied (another user's analysis id is opaque → unlinked). `search` gained `symbol`/`outcome`
  filters and a bounded `limit`. `performance()` and `export()` added. **No fabrication:** unset
  values stay `null`/`[]`/`{}`; every statistic is `null` when not computable and the sample sizes
  (`pnl_sample`/`rr_sample`) are always reported.
- **API (`journal/views.py`, `journal/urls.py`)** — `GET/POST /api/journal/entries/`,
  `GET/PATCH/PUT/DELETE /api/journal/entries/<uuid>/`, `GET /api/journal/performance/`,
  `GET /api/journal/export/?format=csv|json`; `journal/search/` retained as a compatible alias.
  Validation → `400` with safe messages; unexpected errors → generic `500` (logs server-side).
- **Backtest history (`backtesting/models.py`, `views.py`, `urls.py`, root `urls.py`)** —
  read-only `GET /api/backtests/`. `BacktestRun` gained a nullable `user` FK
  (`backtesting/0002_backtestrun_user.py`); the endpoint is owner-scoped and **never exposes
  unowned or other users' runs**.
- **Settings (`settings/base.py`)** — `REST_FRAMEWORK["URL_FORMAT_OVERRIDE"] = None` because DRF
  reserves `?format=` for content negotiation and 404s on `csv` with only the JSON renderer
  (ADR-013).

### 1.2 WS-F — Infrastructure verification & documentation errata

- **M-12** — `.env.example` is now mock-first (`MT5_USE_MOCK=true`), documented.
- **L-04** — production HSTS **on by default** (`SECURE_HSTS_SECONDS=31536000`, include-subdomains
  and preload default to on), override documented.
- **L-03** — `redact_text` now masks URL userinfo (`scheme://user:pass@host`); `JsonFormatter`
  redacts structured `extra` fields (including secrets nested under sensitive keys).
- **L-07** — login bad credentials answer **`401`** (uniform message); logout already revokes the
  token; password reset documented as out of scope.
- **L-06** — resolved by the Phase 11D shell rebuild (the static clock/label no longer exists; the
  topbar clock is a live UTC tick and the symbol is a real selector). No code change needed.
- **H-10 / M-14 / M-16** — README claim corrected (no present-tense "live MetaTrader 5"), `docs/API.md`
  regenerated against routes (health statuses corrected to `ok`/`degraded`; login `401`; 11F
  endpoints documented; `?format=` note), `ROADMAP.md` status table refreshed, errata addenda
  appended to `PHASE_02/04/06/08.md` (history not rewritten), audit status table updated.
- **L-01 / L-05** — deliberately **deferred and recorded** (health stays open by design; swing
  equality asymmetry is a behavioural change deferred to avoid unverified golden-fixture churn).

### 1.3 Explicitly blocked (honest, not claimed)

- **M-11 / M-13 — Docker build + compose run: BLOCKED.** No Docker host in this environment. No
  "deployable" claim is made.
- **GitHub CI execution: not observed here.** The workflow is unchanged; the Phase 11E push
  (`f8c5565`) may have triggered a run, but its outcome cannot be read from this environment.

### 1.4 Verification (CI parity)

| Check | Command | Result |
|---|---|---|
| Django check | `uv run python manage.py check` | **clean** (0 issues) |
| Migrations | `uv run python manage.py makemigrations --check --dry-run` | **No changes detected** |
| Backend tests | `uv run pytest` | **394 passed, 0 failed, 0 errors, 0 skipped** (JUnit: `tests=394 failures=0 errors=0 skipped=0`) |
| Frontend tests | `npx vitest run --maxWorkers=1` | **111 passed / 11 files** (exit 0) |
| Frontend types | `npm run typecheck` | **exit 0** (0 errors) |
| Frontend build | `npm run build` | **exit 0** — 11 routes compiled |

Backend test count grew from **361 (11E) → 394 (+33)**: `journal/tests/test_journal_11f.py` (26),
`backtesting/tests/test_backtest_history_api.py` (3), `core/tests/test_logging.py` (+2),
`core/tests/test_settings.py` (+2). The login-status assertion was updated in
`accounts/tests/test_auth.py` (`400` → `401`). No tests were skipped, weakened, or deleted.

### 1.5 Files changed

- Backend: `journal/{models,services,views,urls}.py`, `journal/migrations/0002_*.py`,
  `journal/tests/test_journal_11f.py` (new); `backtesting/{models,views,urls}.py`,
  `backtesting/migrations/0002_*.py`, `backtesting/tests/test_backtest_history_api.py` (new);
  `accounts/views.py`, `accounts/tests/test_auth.py`; `core/logging_extras.py`,
  `core/tests/{test_logging,test_settings}.py`; `settings/{base,production}.py`;
  `nazbeen_forex_ai/urls.py`.
- Docs: `PHASE_11F.md` (this file), `PROJECT_PROGRESS.md`, `DECISIONS.md` (ADR-013), `API.md`,
  `ROADMAP.md`, `TESTING.md`, `README.md`, `.env.example`, `audits/CRITICAL_ISSUES.md`,
  phase-report errata addenda (`PHASE_02/04/06/08.md`).

### 1.6 Not verified here (owner-run required)

- Any live MT5 / live-LLM behaviour (no terminal / no keys in this environment).
- Docker build/run and the GitHub Actions run (M-11/M-13).

