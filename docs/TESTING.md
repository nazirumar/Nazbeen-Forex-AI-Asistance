## CI

- Backend: `python manage.py check`, `python manage.py makemigrations --check --dry-run`, `pytest`
- Frontend: `npm ci`, `npm run typecheck`, `npm run build` — the Vitest suite is **not**
  wired into CI yet; run it locally with `npm test` (see the note below).

(see `.github/workflows/ci.yml`)

## Frontend test suite (Phase 11D, extended in 11E)

`frontend/` now has its own unit/integration suite: **Vitest 5 + Testing Library + jsdom**,
run with `npm test` (`vitest run`). 111 tests across 11 files in `frontend/test/`, covering:

- `api.test.ts` — token attachment, DRF error extraction (detail/fields/details[]), 401 →
  token cleared + `nazbeen:auth-expired` event (with credential-path exemption), FormData
  passthrough, `apiBlob` for screenshots.
- `auth.test.tsx` — AuthProvider: boot re-validation via `/api/auth/me/`, login/register token
  persistence, logout clearing local state even when the server revoke fails, expiry event.
- `login-page.test.tsx` — credential errors verbatim, session-expired banner, password
  mismatch + Django field errors, server-unreachable hint.
- `shell.test.tsx` — protected-route guard (anonymous → `/login?reason=expired`), shell
  rendering when authenticated, honest "unknown" indicators on failed status polls, profile
  menu logout; Sidebar mobile drawer/off-canvas, desktop collapse, active-route marking.
- `chart-data.test.ts` — pure conversions: ISO→unix, candle normalize (sort/dedupe/drop),
  BOS/CHOCH/MSS markers anchored to `confirmed_at` (never the formation bar), zone price bands
  exactly as the backend reported, unparseable events skipped not guessed.
- `trading-chart.test.tsx` — with `lightweight-charts` mocked at the module boundary: candle
  `setData`, marker alignment, zone primitive attach, price lines only for computed levels,
  line cleanup on plan change; plus direct `ZonesPrimitive` draw tests (real rect calls,
  unresolvable-coordinate skip).
- `panels.test.tsx` — MTF bias rendering (Bullish/Bearish/Neutral/**Unavailable never NEUTRAL**),
  conflict surfacing, mock-data badge; shared Loading/Empty/Error states and ARIA.
- `upload-panel.test.tsx` — client-side PNG/JPEG + 5 MB rejection, preview, multipart submit
  with current symbol/timeframe, processing state, verdict/evidence/disagreement rendering,
  backend 400 shown verbatim.
- `risk-panel.test.tsx` — request payload, backend numbers only (missing → "—"), WAIT reasons
  + warnings, and an explicit **no-execution-controls** enforcement test.
- `journal-history.test.tsx` — journal search/save/rows (UTC times, real fields), analysis
  history rows + reopen links, empty/error states.
- `setup-checklist.test.tsx` **(11E)** — renders the primary-model steps with honest
  satisfied/missing/invalid/unavailable labels, model + `complete` + `blocked_by`, and the
  explicit "no setup yet / insufficient data" state; asserts **no execution controls**.
- 11E additions to `chart-data.test.ts` / `trading-chart.test.tsx` — sweep/displacement
  markers anchored to real timestamps (fallback `confirmed_at → end_time → time`), S/R and
  premium/discount midpoint lines, and setup Entry/SL/TP lines emitted **only** for a
  `complete` setup with finite values (otherwise `[]`); unparseable events are dropped, never
  guessed.

Notes:

- `vitest.config.ts` uses the **threads** pool (`maxWorkers: 4`): the workspace path contains
  spaces, which breaks the default `forks` pool worker spawn on Windows; Vitest's worker-start
  timeout is a hardcoded 60 s, so concurrency is capped to avoid a spawn pileup.
- `test/setup.ts` polyfills `ResizeObserver` and object URLs; jsdom 30 provides
  `URL.createObjectURL` natively.
- These tests are **not** in CI yet (CI predates the frontend test runner) — run
  `npm test` locally; wiring it into `.github/workflows/ci.yml` is a one-line addition
  (`npm test` after `npm run build`) left for owner confirmation.

## LLM provider smoke test (Phase 11B)

The automated suite **always** runs against the labeled mock LLM providers
(`settings/test.py: USE_MOCK_LLM = True`); every real-provider code path is covered by unit
tests with fake HTTP sessions — no network, no keys. To verify a **real** OpenAI/Gemini call:

1. In `.env` set:

   ```ini
   USE_MOCK_LLM=false
   VISION_LLM_PROVIDER=openai          # or gemini
   VISION_LLM_API_KEY=<key>
   VISION_LLM_MODEL=<model>
   REASONING_LLM_PROVIDER=openai       # or gemini
   REASONING_LLM_API_KEY=<key>
   REASONING_LLM_MODEL=<model>
   ```

2. Run one real call per role:

   ```powershell
   uv run python manage.py llm_smoke --role vision --image path\to\chart.png
   uv run python manage.py llm_smoke --role reasoning
   uv run python manage.py llm_smoke --role both --image chart.png
   ```

Contract:

- With `USE_MOCK_LLM=true` the command **refuses** (non-zero exit) unless `--allow-mock`
  is passed; a mock run is banner-labeled `MOCK — NOT A REAL PROVIDER TEST` so it can never
  be mistaken for a live verification.
- Exit is non-zero on misconfiguration (`LLMConfigurationError`) or provider failure
  (`LLMError`) with a safe message — the API key is never printed, logged, or echoed.
- Output shows provider, model, latency and the redacted model response only.

There is no CI job for the smoke test (it needs real keys); it is a manual, documented step.

## Phase 11E backend tests

| File | Focus |
|---|---|
| `structure/tests/test_detectors_11e.py` (17) | displacement, rejection, engulfing, S/R, S/R flips, premium/discount, sweeps, MTF alignment — documented rules, both directions, timestamps on the candle grid, `[]` on insufficient data. |
| `structure/tests/test_no_lookahead_11e.py` (9) | Generic no-look-ahead / no-repaint suite: growing the series never changes a prior event's formation/confirmation values. |
| `structure/tests/test_setup_model.py` (15) | `evaluate_primary_setup` chronological 7-step chain, blocked reasons, complete/incomplete, levels only when complete. |
| `analysis/tests/test_graph.py` (12) | LangGraph: 10-node inventory + wiring, deterministic authority (LLM cannot upgrade WAIT), loud provider failure (never mocked over), validation retry forced to WAIT, persistence hook. |
| `structure/tests/test_structure_api.py` (+5, 16 total) | Additive `/api/structure/` keys: shapes, lifecycle states, real price provenance, MTF alignment conflicts, honest unavailable timeframe. |

Helpers: `structure/tests/candles.py` (fixture builder) and `structure/tests/golden.py`
(deterministic golden fixtures). All hermetic — no network, no MT5, no real keys.