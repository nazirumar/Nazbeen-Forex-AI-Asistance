# PHASE 10 FULL AUDIT — Nazbeen Forex AI Asistance

**Audit date:** 2026-10-09 · **Type:** independent audit-first review (no feature development)
**Repo state at audit start:** 3 commits (`dbe7fba` → `5fb5408` → `19644e1`), clean tree, 78
backend tests claimed passing.

Companion documents:

- `docs/audits/FEATURE_VERIFICATION_MATRIX.md` — per-feature classification vs MASTER_SPEC
- `docs/audits/CRITICAL_ISSUES.md` — every issue with evidence, root cause, fix, regression test
- `docs/audits/RECOMMENDED_FIXES.md` — prioritized remediation
- `docs/audits/PHASE_11_PLAN.md` — proposed next phase (**not started**)
- `docs/audits/repro/test_audit_regressions.py` — 15 executable bug-reproduction tests

---

## Method

Phase completion reports (`docs/PHASE_REPORTS/PHASE_01..10.md`) were treated as **claims, not
evidence**. Every claim was checked against source; material claims were re-verified by execution.
Findings from parallel subsystem reviews were independently spot-checked by the lead auditor
before being recorded (imports run, endpoints exercised, formulas recomputed, live MT5 connected).
Nothing outside `docs/audits/` was modified.

## Step 1 — Repository inspection

- **Structure:** Django project `nazbeen_forex_ai/` with 9 apps (`core`, `accounts`,
  `marketdata`, `structure`, `analysis`, `risk`, `backtesting`, `journal`, `settings`), plus
  `frontend/` (Next.js 15), `mt5_worker/` (scaffold), `scripts/`, `docs/`, `.github/workflows/`.
- **Spec vs. implementation:** full comparison in `FEATURE_VERIFICATION_MATRIX.md`. Headline:
  infrastructure/auth/health/logging/throttling/backing-store work as claimed; the **trading-intel
  core has critical defects** (CRIT-01..05) and the **frontend covers a small fraction of
  MASTER_SPEC §3.I** (H-08).
- **Spec stack gaps:** `scikit-learn`, `LightGBM`, `LangGraph` are **not dependencies**; no real
  LLM provider exists (H-03).
- **Docs:** all required tracking files exist; several report claims are contradicted by code
  (H-10).

## Step 2 — MT5 audit

- Live connectivity **was exercised in this audit**: the configured provider connected to
  **MetaQuotes-Demo, login 113256064, terminal "MetaTrader 5"** and returned M15 candles.
- **CRIT-05:** those candle timestamps were **~2h12m ahead of true UTC** (bars 19:45–20:15Z while
  machine UTC was ~17:33Z) — server time is being stamped as UTC without correction.
- **CRIT-04:** the test suite itself selects the **real** provider in this environment
  (`.env:38 MT5_USE_MOCK=false`) — a test named `..._returns_mock_data` passes because it never
  asserts `data_source == "mock"`. The suite is non-hermetic and silently consumes live data.
- Suffix handling, market-closure detection, staleness: **missing** (H-05/H-09). Connector unit
  tests: **zero**. Worker service: **scaffold only**. OHLC validation checks exist but are dead
  (`pass`). Mock→real fallback is **not silent at the provider level** (factory raises; views
  return labeled 503) — verified correct.

## Step 3 — ICT/SMC algorithm audit

- **CRIT-02:** FVG direction labels are **inverted** (gap-up → `bearish`), plus a branch emitting
  `start_time > end_time` — executed repros.
- **CRIT-03:** BOS/CHOCH/MSS detector is a stub **always returning `[]`**; `orderblocks.py` is
  **unimportable** (`SyntaxError`).
- **H-05:** multi-timeframe bias returns the *type of the last swing* — a rising structure ending
  on a swing-high reports `BEARISH` (executed repro); `conflicts` hardcoded `[]`.
- Missing detectors: sweeps, equal lows, displacement, FVG mitigation, premium/discount, S/R,
  flips, rejection, engulfing — 9+ of 19 spec items (M-09).
- Look-ahead: detection windows themselves consume only past/confirming candles (no active
  look-ahead found), but events lack `confirmed_at` — latent repainting risk (M-10).
- Structure tests: 2, both vacuous (`len >= 0`, `isinstance list`).

## Step 4 — AI analysis audit

- Upload validation deliberately disabled (H-01, executed: garbage → **201**, 6 MB → **201**).
- Screenshot never stored; `MEDIA_ROOT` undefined (H-02).
- **LangGraph: absent** — no dependency, no graph, single synchronous method (H-03).
- **No real LLM provider:** both branches of `get_llm_provider()` return the mock; env vars dead.
- Fabrication guard bypassable when data is "synchronized" (mock counts as synchronized), and
  symbol/timeframe are **fabricated defaults** (`EURUSD`/`M15`) when extraction finds nothing
  (H-04).
- WAIT behavior and LLM-error→WAIT paths **verified correct**; deterministic-vs-LLM authority is
  **not enforced** (H-05).

## Step 5 — Probability & backtesting audit

- **CRIT-01 (executed):** trade `pnl` hardcoded to `1.0` → win_rate **100%**, gross_loss 0,
  expectancy 1.0, drawdown 0 — fabricated performance metrics; commission/slippage/spread
  parameters accepted but **never applied** (executed: costs all 0).
- Window evaluation is leak-free in the main path (`candles[:i]`), but the walk-forward fallback
  runs train == test (P-02) and `overall` is not an aggregation (M-07: 49 ≠ 147).
- Probability ≥30-sample discipline: `null` below 30 — **verified correct**; above 30 it honestly
  stays `null`, but reports a **fabricated constant CI `[0.3, 0.7]`** (M-08). Drift detection: missing.
- Provenance: backtest results carry **no data-source label** (mock vs live) — needed for spec
  compliance.

## Step 6 — Risk & security audit

- RR math and SL/TP consistency: **verified correct**. Live order execution: **zero
  `order_send`/trade-execution code** — analysis-only confirmed repo-wide.
- **H-06 (executed):** position sizing pip value divides by `entry` → 1.1 lots where 1.00 is
  correct (+10% over-risk).
- Unknown symbols get fabricated specs (M-06); trade-plan endpoint has no input serializer —
  NaN → 500, error-text leaks (M-05).
- Auth: token auth + permissions on all mutating endpoints; object-level checks (user scoping)
  verified; **no IDOR found**; no raw SQL; no secrets in code; `.env`/`screenshots/` git-ignored.
- Dependency vulnerability scan: `pip-audit` tool itself failed in this environment (pip upgrade
  failure then timeout) — **BLOCKED**; substituted with a direct **OSV batch query of all 62
  locked packages: 0 known vulnerabilities**.
- Throttling, CORS, cookie flags, `DEBUG` gating: verified as configured (production knobs
  documented in `OPERATIONS.md`).

## Step 7 — Full integration testing

| Suite / check | Result |
|---|---|
| Backend: `uv run pytest` | **78 passed** (112.9s) |
| `manage.py check` | **0 issues** |
| `manage.py makemigrations --check --dry-run` | **No changes** |
| Audit repros: `uv run pytest docs/audits/repro` | **15 failed** — by design; each = confirmed bug (CRITICAL_ISSUES.md) |
| Frontend: `npm run typecheck` (`tsc --noEmit`) | **exit 0** |
| Frontend: `npm run build` | **Success** (`/`, `/_not-found`, `/api/health`) |
| Frontend unit tests | **None exist** — reported as absent, not passed |
| Dependency audit (OSV, 62 locked pkgs) | **0 known vulnerabilities** (pip-audit itself BLOCKED) |
| Docker image/compose build | **BLOCKED** — no Docker on this machine |
| GitHub Actions CI execution | **BLOCKED** — repo never pushed; workflow never ran on GitHub |
| PostgreSQL path (`DATABASE_URL`) | **BLOCKED** — only SQLite exercised |
| Redis channel layer | **BLOCKED** — in-memory layer tested; `USE_REDIS_CHANNELS` never live-tested |
| Live MT5 terminal | **EXECUTED** — connected (MetaQuotes-Demo); timestamps defective (CRIT-05); suffix/closure/staleness untested |
| `mt5_worker` service | **BLOCKED** — scaffold only, never run |
| Real LLM provider calls | **BLOCKED / MISSING** — no provider implemented |
| E2E workflow (API-level) | **PASSED** (part of the 78) |

**Important caveat:** because of CRIT-04, the passing suite includes tests that ran against **live
MT5** in this environment while the same tests would take the mock path elsewhere (e.g. CI).
"PASSED" therefore does not mean "hermetic".

## Step 8 — Reports produced

`PHASE_10_FULL_AUDIT.md` (this file), `FEATURE_VERIFICATION_MATRIX.md`,
`CRITICAL_ISSUES.md`, `RECOMMENDED_FIXES.md`, `PHASE_11_PLAN.md`,
`repro/test_audit_regressions.py`.

## Overall assessment (no numerical score, per instructions)

- **Verified working:** auth/token/permissions, health (incl. degraded 503), throttles, structured
  logging + redaction, WebSocket status consumer, deterministic swings, RR/risk math core,
  WAIT discipline, probability `null <30` rule, journal CRUD basics, provider labeling at the
  API boundary, CI-parity checks locally, frontend typecheck/build, e2e API workflow.
- **Critical bugs:** fabricated backtest metrics (CRIT-01), inverted FVG labels (CRIT-02),
  stubbed BOS/CHOCH/MSS + broken order blocks (CRIT-03), live-data contamination of the test
  suite (CRIT-04), non-UTC live timestamps (CRIT-05).
- **Security:** no critical exposure; one High — upload validation deliberately disabled (H-01);
  no live-trading surface; no IDOR; no committed secrets; clean dependency audit.
- **AI:** no LangGraph, no real LLM, guard gaps — the AI cannot yet be trusted to identify charts
  or police fabrication end-to-end (H-03/H-04).
- **Backtesting reliability: not usable for any performance claim** until CRIT-01 is fixed —
  metrics are fabricated from dummy outcomes.
- **Frontend:** far behind spec (H-07/H-08).

**This audit did not modify application code and did not start Phase 11. Waiting for approval.**
