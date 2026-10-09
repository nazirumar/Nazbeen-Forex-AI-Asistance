---

## ADR-007 — Phase 1 scope expansion (owner-approved)

**Status:** Accepted
**Date:** 2026-10-08

### Context

The owner's Phase 1 request bundled work previously slated for later phases (e.g., token auth, dashboard shell, docker-compose, dev scripts, CI frontend job). The existing ROADMAP/PHASE_01 report described a narrower "backend skeleton" (16 tests). The implementation expanded scope to meet the owner's acceptance criteria without breaking phase boundaries on analysis-only logic (no trading strategies, no AI analysis implemented).

### Decision

- Treat Phase 1 as "Foundation (expanded)" covering: Django backend skeleton, core health, accounts auth (register/login/logout/me), PostgreSQL/Redis/Celery wiring, resilient rate limiting, Next.js dashboard shell, frontend/backend health, dev scripts, docker-compose for Postgres+Redis, Windows 11 run docs, and CI covering backend + frontend.
- Explicitly exclude: trading strategies, market structure, AI pipeline, journal, probability, full frontend workspace — those remain in Phases 3–10.
- Document deviations in PROJECT_PROGRESS.md and this ADR.

### Consequences

- Tests grew from 16 to 38; documentation updated to match repo state.
- Future Phase 2 can focus on the remaining auth/limits hardening (timezone update, rate/limit tuning, object-level authorization, uploads) rather than re-establishing the auth skeleton.

---

## ADR-008 — Resilient rate limiting (degrade on cache outage)

**Status:** Accepted
**Date:** 2026-10-08

### Context

DRF throttles store counters in the Django cache. When Redis is configured but unreachable (broker down), throttle `allow_request` raised an unhandled `ConnectionError` → 500s on throttled endpoints (e.g., register/login). Test settings use LocMemCache so this path wasn't exercised.

### Options

1. Avoid throttling entirely in development. (Weaker, hides the security posture; fails parity.)
2. Fall back to LocMemCache when Redis is unreachable. (Hard to do robustly at runtime; settings-loaded constraints.)
3. Make throttles catch cache failures and allow requests (degrade-gracefully). Log the outage and do not take the API down.

### Decision

Create resilient throttle classes in `nazbeen_forex_ai/core/throttling.py`:
- `ResilientAnonRateThrottle`, `ResilientUserRateThrottle`, `ResilientScopedRateThrottle` — catch any exception from throttle checks (including Redis `ConnectionError`), log a warning with `exc_info`, and return `True` (allow).

Wire into:
- `REST_FRAMEWORK.DEFAULT_THROTTLE_CLASSES` (global defaults)
- `LoginView` / `RegisterView` use `ResilientScopedRateThrottle` with `auth` scope

Add tests: `test_register_degrades_gracefully_when_throttle_cache_down`, `test_login_degrades_gracefully_when_throttle_cache_down`, `test_rate_limit_still_enforced_when_cache_is_healthy`.

### Consequences

- Auth endpoints no longer 500 when Redis/broker is temporarily down (rate limiting is lost in that window — preferred over total outage). 
- Production behavior unchanged when cache is healthy. The health endpoint still truthfully reports cache status.
- This is documented as an operational trade-off in code comments and this ADR.

---

## ADR-009 — Owner-driven phase numbering supersedes ROADMAP labels

**Status:** Accepted
**Date:** 2026-10-09 (recorded during Phase 9 documentation audit)

### Context

The owner instructed phases by their own numbering ("PHASE 2: MT5 Market Data Integration",
"PHASE 3: Market Structure Engine", ... "PHASE 9: Final Integration"), while `docs/ROADMAP.md`
labels the same work differently (Roadmap Phase 3 = MT5 data layer, Phase 4 = market structure,
Phase 6 = screenshot/AI pipeline, Phase 7 = probability, Phase 8 = journal, Phase 9 = frontend,
Phase 10 = infra/ops). Reports and `PROJECT_PROGRESS.md` were produced using the **owner's
numbering**; the ROADMAP file retains its original labels. This discrepancy was implemented but
not previously recorded in DECISIONS.md.

### Decision

- The owner's phase numbering is authoritative for reports (`docs/PHASE_REPORTS/PHASE_XX.md`)
  and `PROJECT_PROGRESS.md`.
- `docs/ROADMAP.md` labels are kept as a historical reference only; scope content is what
  matters, not the label number.
- Mapping: Owner 1 = Roadmap 1(+2), Owner 2 = Roadmap 3, Owner 3 = Roadmap 4, Owner 4 = Roadmap 6,
  Owner 5 = Roadmap 5, Owner 6 = Roadmap 7, Owner 7 = Roadmap 8, Owner 8 = Roadmap 9,
  Owner 9 = release review. **Roadmap 10 (Infra & ops) remains open.**

### Consequences

- Documentation is internally consistent with owner instructions; ROADMAP renumbering was not
  performed to avoid rewriting working docs.
- Remaining open scope is explicitly tracked as Roadmap Phase 10 (full Docker app containers,
  Channels WebSockets, production logging/redaction, e2e suite, operational docs).