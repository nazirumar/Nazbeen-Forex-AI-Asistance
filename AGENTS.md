# AGENTS.md — Instructions for AI coding agents

You are working on **Nazbeen Forex AI Asistance**, an analysis-only AI-powered Forex market
analysis platform. Follow these rules without exception.

## Before touching anything

1. Read `docs/MASTER_SPEC.md` — the canonical specification.
2. Read `docs/PROJECT_PROGRESS.md` — what phase we are in and what is done.
3. Read `docs/ROADMAP.md` — phase scope and boundaries.
4. Read `docs/DECISIONS.md` — established architecture decisions (ADRs).
5. Inspect the actual repository state (`git status`, `git log`, source tree) — never assume.

## Commands

- Setup: `uv sync` then `cp .env.example .env` (git-ignored, auto-loaded — see below).
- Run: `uv run python manage.py migrate && uv run python manage.py runserver`
- Tests: `uv run pytest` · single file:
  `uv run pytest nazbeen_forex_ai/core/tests/test_health.py` · filter: `uv run pytest -k health`
- CI parity (run in this order before calling any phase done):
  `uv run python manage.py check` → `uv run python manage.py makemigrations --check --dry-run`
  → `uv run pytest`. Workflow: `.github/workflows/ci.yml`.
- No Python linter/formatter/typechecker is configured — do not add one unless the phase asks
  for it. Dependencies only via `uv add <pkg>` (never pip, never edit `uv.lock` by hand).
- `frontend/` is a separate npm project (Next.js 15, Phase 9 scaffold, not wired to the
  backend): `npm run dev`, `npm run typecheck`. It is **not** covered by pytest or CI.

## Architecture notes (not obvious from filenames)

- Django project package is `nazbeen_forex_ai/` with split settings
  (`base` / `development` / `test` / `production`). `manage.py`, `wsgi.py`, `asgi.py`,
  `celery.py` default to `settings.development`; pytest forces `settings.test` via
  `DJANGO_SETTINGS_MODULE` in `pyproject.toml`.
- Root `.env` is loaded by a **homegrown** `load_dotenv()` in `nazbeen_forex_ai/config.py`
  (imported by `settings.base`) — there is no python-dotenv. Real environment variables always
  win. Read all config through the `env_str` / `env_bool` / `env_int` / `env_list` helpers; they
  fail fast on invalid values instead of silently defaulting.
- Tests live next to the app: `nazbeen_forex_ai/<app>/tests/test_*.py` (no top-level `tests/`
  tree). Test settings use in-memory SQLite, eager Celery, and fake broker URLs — a test must
  never require Redis, PostgreSQL, or a real MT5 terminal. Real-MT5 tests are manual/local only.
- `GET /api/health/` returns **503 when the database is unreachable** (degraded) by design —
  don't "fix" it as a bug.
- DB is SQLite by default; `DATABASE_URL` supports PostgreSQL but is untested against a live
  server. `USE_TZ = True` with UTC everywhere: tests must not depend on machine timezone.

## Phase boundaries (mandatory)

- Implement **only** the current phase scope. Do not "helpfully" start the next phase.
- Never attempt to build the whole platform in one session.
- After implementing a phase: run the tests, fix failures you introduced, update docs, write
  `docs/PHASE_REPORTS/PHASE_XX.md`, update `docs/PROJECT_PROGRESS.md`.
- Then **STOP and ask for explicit approval** before the next phase. Approval is never implied.
- Do not mark a feature complete without implementation + passing tests.

## Code rules

- Preserve working code; do not rewrite or delete unless the current phase requires it and the
  change is documented in `docs/DECISIONS.md`.
- Keep the established layout: Django project package `nazbeen_forex_ai`, feature apps inside it,
  service-layer separation, typed Python, UTC everywhere.
- Every endpoint/service/detector ships with tests in the same phase.

## Safety rules (from MASTER_SPEC §7 — non-negotiable)

- Never expose API keys or commit credentials. Config comes from environment variables
  (`.env.example`); `.env` stays git-ignored.
- Never enable live trading without separate explicit authorization. This project is
  **analysis-only**.
- Never invent market data; mock data must always be labeled as mock, never silently substituted.
- Never claim guaranteed profitability or fabricate model accuracy.
- Never skip, weaken, or delete failing tests to get to green.
- Never mark untested functionality as verified.
- Never use future market data to generate historical predictions.
- Never let LLM-generated text execute trading commands.
- Never overwrite user data without approval.

## Reporting

- Report exactly what was implemented and what the test run showed (real counts, real failures).
- If something could not be verified, say so explicitly instead of claiming success.
