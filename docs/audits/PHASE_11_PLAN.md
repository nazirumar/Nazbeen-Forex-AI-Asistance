# PHASE 11 PLAN — Proposed (NOT STARTED — awaiting owner approval)

**Status:** draft only. No Phase 11 code has been written. Per AGENTS.md, implementation begins
only after explicit approval.

## Objective

Bring the application to a state where its **trading intelligence is correct and its claims are
true**, then close the highest-value product gaps. Every workstream starts from the audit in
`docs/audits/` and carries its regression tests forward.

## Scope (ordered)

### WS-A — P0 correctness batch (mandatory, first)

Execute `RECOMMENDED_FIXES.md` P0.1–P0.7 (backtest realism, FVG labels, BOS/CHOCH/MSS + order
blocks, hermetic tests, MT5 UTC, upload validation, pip-value math).

- **Acceptance:** all 15 migrated repro tests pass; full suite green with `.env` removed;
  `manage.py check` + `makemigrations --check` clean; audit documents updated with an errata
  section marking issues Resolved/Open.

### WS-B — Safety & honesty batch (P1)

P1.1–P1.8 (MTF bias + deterministic authority, fabrication guard, screenshot persistence,
walk-forward integrity, probability CI, input validation, mock tick/timeframe, MT5
suffix/staleness/closure).

- **Acceptance:** no fabricated defaults (symbol/timeframe/CI); trade-plan and candles endpoints
  return 400 (not 500) on invalid input; suffix + staleness unit tests pass.

### WS-C — Frontend MVP (P2.1–P2.4)

Working login → upload → analysis workspace → MT5 status/bias → chart with structure overlays.
Dark theme retained; mock/live labeling everywhere.

- **Acceptance:** `npm run typecheck` + `build` clean; new component/integration tests for each
  feature; e2e smoke: register → login → upload → see WAIT analysis.

### WS-D — Spec detectors & AI orchestration (owner decision required)

Two options to be chosen explicitly before start:

1. **Full spec:** implement missing detectors (M-09) + `confirmed_at` (M-10), real LLM providers
   with mock-first development, LangGraph graph (10-node per MASTER_SPEC §3.E), deterministic
   authority enforcement tests.
2. **Reduced spec (requires formal MASTER_SPEC amendment in `DECISIONS.md`):** defer LangGraph /
   LightGBM / scikit-learn with documented rationale, implement detectors only.

- **Acceptance (either):** each detector has golden-candle tests; LLM path has recorded
  no-network mock tests + one manual real-provider run documented; decision = deterministic
  authority or WAIT whenever they disagree.

### WS-E — Journal, analytics & reporting (P2.5, M-15)

Journal spec fields, CRUD, performance/export endpoints, backtest-history surfacing (only after
P0.1).

### WS-F — Infrastructure verification & doc errata (M-11..M-16, H-10, L-01..L-07)

Docker build+compose run on a Docker host, compose fixes, GitHub CI first execution, documentation
errata pass (PHASE_02/04/06/08 addenda, README, API.md regeneration, ROADMAP/PROJECT_PROGRESS
alignment).

## Deliverables per workstream

Implementation + tests → CI-parity checks (`check`, `makemigrations --check`, `pytest`) →
`docs/PHASE_REPORTS/PHASE_11_*.md` → update `PROJECT_PROGRESS.md` and mark audit issues
Resolved/Open → **STOP for approval** before the next workstream if the owner prefers
workstream-level gating.

## Out of scope (unchanged)

Live order execution, guaranteed-profitability claims, any data fabrication, silent mock
substitution, and any push/deploy of the repo (still local-only).

## Risks & open questions for the owner

1. LangGraph/LightGBM/scikit-learn: implement or amend spec? (H-03, WS-D option 2)
2. Frontend scope: full §3.I is large — approve WS-C MVP subset first?
3. Docker/CI verification requires a Docker host and a GitHub remote — both currently absent.
4. Live-MT5 UTC correction (P0.5) needs confirmation of the broker's server-time convention.
