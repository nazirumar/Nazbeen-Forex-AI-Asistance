# PHASE 11D — Professional Trading Dashboard (frontend + supporting backend)

**Status:** complete, awaiting owner approval · **Date:** 2026-10-10 · **Scope:** the
owner-approved 11D brief (login/register token flow, dark responsive shell, TradingView
chart with structure overlays, screenshot-analysis workspace, MTF panel, risk panel,
journal/history). Analysis-only throughout: **no execution controls exist anywhere in the
UI**, no fabricated probabilities, no mock data presented as real (every panel shows the
backend's `data_source` label). Phase 11E not started.

## 1. What was delivered

### 1.1 Backend additions (only what the frontend scope demanded)

| Addition | Why the dashboard needed it |
|---|---|
| `GET /api/structure/` (`structure/views.py`, `structure/urls.py`, root mount) | The chart needs detector output aligned to candle timestamps: swings, BOS/CHOCH/MSS events, FVG/order blocks/liquidity (each with `formation_time`/`confirmed_at`/`start_time`/`end_time`, `level`/`levels`, `details`), plus the real `mtf` block (H1/M15/M5/M1 biases + `conflicts`) for the MTF panel. Unfetchable timeframe → bias `null` (UI shows "Unavailable", **never** a fabricated `NEUTRAL`). Same strict 11C validation and generic 503 error pattern as candles; same freshness labels (`market_state`, `stale`, `last_bar_age_sec`, `threshold_sec`). |
| `GET /api/analysis/` (`AnalysisListView`) | "Save & reopen" needs a history list. Owner-scoped server-side (`request.user` filter), newest first, summary rows only. |
| Freshness labels on `GET /api/mt5/candles/` | The topbar freshness indicator reads real data: `stale`, `last_bar_age_sec`, `threshold_sec`, `market_state` (via `marketdata/freshness.py: assess_staleness`). |
| Enriched `GET /api/journal/search/` rows | Added `timeframe`, `scenario_decision`, `rr`, `created_at` (additive, backward compatible) so the journal table shows recorded fields without a second fetch. |

No existing endpoint behavior changed; no migrations; no model changes.

### 1.2 Frontend (the dashboard itself)

- **Auth flow repaired** (`lib/api.ts`, `lib/auth.tsx`, `app/login`, `app/register`): the old
  shell logged in but **never persisted the token** — `/api/auth/me/` then 401'd immediately
  (the bug found in 11D prep). Now: login/register → DRF token persisted in `localStorage`
  (`nazbeen_token`) → profile loaded from `/api/auth/me/`; boot re-validates any stored token
  so a revoked session lands on `/login` instead of a half-rendered dashboard; logout revokes
  server-side and clears local state **even if the revoke fails** (never traps the user);
  a 401 on any non-credential path clears the token and fires `nazbeen:auth-expired` (the
  login page then shows "session expired"); Django password-validator and DRF field errors
  render field-by-field, verbatim.
- **Token storage decision (documented):** `localStorage` + `Authorization: Token …` header,
  not an httpOnly cookie. Dev runs cross-origin (`localhost:3000` → `localhost:8000`), where
  `SameSite=None` cookies require HTTPS; DRF's token header is the established backend
  contract. Trade-off: XSS exposure of the token is accepted for local dev; a production
  HTTPS deployment can revisit this as an ADR before any public release.
- **Dark responsive shell** (`components/layout/`): collapsible sidebar (icon rail on
  desktop, off-canvas drawer + backdrop on mobile, state persisted), topbar with symbol
  selector, M1/M5/M15/H1 timeframe selector, MT5 connection indicator (broker/server, honest
  "Connection unknown" when the status poll fails), freshness indicator (real bar age,
  market-closed/stale labels), UTC clock, profile menu with logout and an explicit
  "Analysis-only — no trade execution" line. Loading/empty/error states everywhere.
- **Chart** (`components/chart/`, TradingView Lightweight Charts v5.2.1): real OHLC candles
  from `/api/mt5/candles/`; BOS/CHOCH/MSS markers anchored to each break's **confirmation
  bar** (`confirmed_at`, per audit M-05/CRIT-02 — never the formation bar); FVG + order-block
  zones drawn by a custom series primitive (`ZonesPrimitive`) resolving coordinates through
  the library's public APIs on every repaint (price band exactly the backend's
  `[bottom, top]`, anchored at the event's candle time, extended rightward to the last
  candle as a rendering convention); liquidity levels + validated entry/SL/TP as price
  lines — **only when the backend computed them** (missing → no line, "—" in the panel).
  Unparseable timestamps/price bands are dropped, never invented (`lib/chart-data.ts`, pure
  and unit-tested).
- **Screenshot workspace** (`components/analysis/`): PNG/JPEG + 5 MB client checks that
  mirror the backend validator purely to fail fast (backend remains the authority and its
  400 is shown verbatim), object-URL preview (revoked on change/unmount), multipart submit
  with the current symbol/timeframe hints, processing state, full result view (decision
  badge BUY/SELL/WAIT, AI observations labeled as non-authoritative, deterministic findings,
  evidence with source, disagreements, uncertainty/unavailable data, sync + mock badges),
  save → reopen via History (stored screenshot fetched as an authenticated blob; "not
  stored" stated honestly when persistence failed).
- **MTF panel**: H1/M15/M5/M1 bias cards + real conflicts from `/api/structure/`; `null`
  bias renders "Unavailable", never "Neutral".
- **Risk panel**: inputs → `POST /api/risk/trade-plan/`; displays **only** backend-returned
  numbers (missing → "—"), reasons and warnings; "Confluence (not probability)" labeled as
  such; **no trade-execution controls exist** (enforced by a dedicated test).
- **Journal + history**: journal search/save with real recorded fields (no client-side
  performance analytics); history list with owner-scoped rows and reopen links.
- Pages: `/` (session-aware redirect), `/login`, `/register`, `/dashboard` (overview:
  connection card, MTF panel, detection counts), `/dashboard/chart`, `/dashboard/analysis`,
  `/dashboard/analysis/[id]`, `/dashboard/history`, `/dashboard/journal`. Protected by the
  `AppShell` guard (loading → session check; anonymous → `/login?reason=expired`).

### 1.3 Removed (documented per AGENTS.md)

`components/auth-panel.tsx` and `components/status-cards.tsx` were deleted: they were the
Phase-11A shell whose broken token flow this phase replaced, and nothing referenced them
anymore (verified by grep before removal). The frontend `/api/health` liveness probe
(`app/api/health/route.ts`) is kept.

## 2. Every changed file

**Backend — new:** `structure/views.py` (rewritten: `StructureView`), `structure/urls.py`,
`structure/tests/test_structure_api.py`, `analysis/tests/test_analysis_history.py`,
`marketdata/tests/test_freshness_api.py`.

**Backend — modified:** `nazbeen_forex_ai/urls.py` (mount `/api/structure/`),
`analysis/views.py` + `analysis/urls.py` (`AnalysisListView`),
`marketdata/views.py` (candles freshness labels),
`journal/views.py` (enriched search fields) + 1 journal test.

**Frontend — new:** `lib/types.ts`, `lib/api.ts` (rewritten), `lib/auth.tsx`,
`lib/format.ts`, `lib/chart-data.ts`; `components/ui/states.tsx`,
`components/chart/zone-primitive.ts`, `components/chart/trading-chart.tsx`,
`components/layout/{market-context,sidebar,topbar,app-shell}.tsx`,
`components/analysis/{mtf-panel,analysis-result,upload-panel}.tsx`,
`components/risk/risk-panel.tsx`, `components/journal/journal-panel.tsx`,
`components/history/history-list.tsx`; `app/{layout,page}.tsx` (rewritten),
`app/{login,register}/page.tsx`, `app/dashboard/{layout,page}.tsx`,
`app/dashboard/{chart,analysis,history,journal}/page.tsx`,
`app/dashboard/analysis/[id]/page.tsx`; `vitest.config.ts`, `test/setup.ts`,
`test/helpers.ts` + 10 test files; `package.json`/`package-lock.json`
(`lightweight-charts`, vitest toolchain).

**Docs:** `API.md`, `TESTING.md`, `PROJECT_PROGRESS.md`, this file.

## 3. Test results (real counts)

```
Backend   uv run pytest                          → 303 passed (+17: 11 structure API,
                                                  3 analysis history incl. cross-user
                                                  isolation, 2 candles freshness,
                                                  1 journal fields)
          manage.py check                        → 0 issues
          makemigrations --check --dry-run       → no changes

Frontend  npm test (vitest, 10 files)            → 92 passed, 0 failed
          npx tsc --noEmit                       → 0 errors
          npx next build                         → compiled + type-checked clean
```

Frontend suite breakdown: api 10 · auth 8 · login/register 7 · shell+sidebar 9 ·
chart-data 14 · trading-chart+zones 11 · panels/states 10 · upload 8 · risk 7 ·
journal/history 8.

Nothing was verified visually in a real browser during this phase (no browser automation
configured); component behavior is covered by the jsdom suite, and layout responsiveness is
asserted structurally (drawer/collapse classes, ARIA). The dev server compiles and serves
all routes; the owner should click through `/dashboard` once against the running backend.

## 4. Known limitations / follow-ups

- Frontend tests are not wired into CI (one-line `npm test` addition; left for owner OK).
- Cross-origin token storage is a dev decision (§1.2) — revisit as an ADR before public
  HTTPS deployment.
- Zone rectangles extend from the event's candle to the last candle (chart convention for a
  still-valid band); the price band itself is exactly the backend's.
- No visual-regression or e2e browser testing yet (unit/integration only).
- `npm audit` still reports the pre-existing advisories from Phase 11's dependency tree
  (Dependabot PR #1 triage remains an owner decision); no `audit fix --force` was run.
