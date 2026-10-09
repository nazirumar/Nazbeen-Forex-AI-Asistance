# FEATURE VERIFICATION MATRIX — Nazbeen Forex AI Asistance

**Audit date:** 2026-10-09 · **Auditor method:** source-level verification + executed repro cases
(`docs/audits/repro/`) + full test runs. Phase completion reports were treated as claims, not evidence.

**Classification key:**

| Label | Meaning |
|---|---|
| **Verified working** | Behavior confirmed by executed test/repro in this audit |
| **Implemented but unverified** | Code exists, no test evidence, not exercised here |
| **Partially implemented** | Works only under limited conditions or with material caveats |
| **Missing** | Not present in code |
| **Broken** | Present but does not work (reproduced failure) |

Repro references (`R-#`) point to `docs/audits/repro/test_audit_regressions.py` unless noted.

---

## 0. Technology stack (MASTER_SPEC §2)

| Requirement | Status | Evidence |
|---|---|---|
| Python 3.12 / Django 6.1 / DRF | Verified working | `pyproject.toml`, suite 78 passed |
| Celery / Redis | Implemented but unverified (eager dev mode; live worker not run) | `settings/base.py:142-150`; no broker test |
| Django Channels | Verified working (in-memory layer) | `core/tests/test_websocket.py` (3 passed) |
| PostgreSQL | Implemented but unverified (SQLite used everywhere; no live PG test) | `DATABASE_URL` path unexercised |
| MetaTrader5 package | Implemented but unverified → **partially verified live, with defects** (see §B) | connected to MetaQuotes-Demo in this audit |
| pandas / NumPy | Verified working | structure/backtest engines |
| **scikit-learn** | **Missing** | not in `pyproject.toml` |
| **LightGBM** | **Missing** (deliberate — ADR/Phase 6 note; probability stays null) | not in `pyproject.toml` |
| **LangGraph** | **Missing** — no dependency, no import; phase report title claims it | `pyproject.toml:10-25`; `services.py:1` docstring only |
| Pydantic structured outputs | Verified working | `analysis/schemas.py` |
| pytest + pytest-django | Verified working | 78 passed |
| Next.js + TypeScript + Tailwind | Verified working (typecheck exit 0, build OK) | executed this audit |
| **WebSocket updates (frontend)** | **Missing** — backend `ws/status/` exists, no frontend consumer | frontend source has no WS code |
| Configurable vision/reasoning LLM providers | **Missing** — env vars exist, zero code reads them | `.env.example:26-32`; `analysis/llm.py:49-57` |
| Docker Compose services | Partially implemented — Postgres/Redis written; app profile written but **never built** (no Docker) | `docker-compose.yml` |
| Windows MT5 worker | **Missing** (14-line scaffold, honestly labeled) | `mt5_worker/app.py` |
| Structured logging + redaction | Verified working | `core/tests/test_logging.py` (6 passed) |
| Health checks / CI / tests | Verified working locally; **CI never executed on GitHub (BLOCKED)** | `.github/workflows/ci.yml` |

## A. Screenshot analysis (MASTER_SPEC §3.A)

| Requirement | Status | Evidence |
|---|---|---|
| Upload screenshots | Partially implemented | works, but validation bypassed → R-13 (`expected 400, got 201`) |
| Upload validation (size/type/content) | **Broken** | `analysis/views.py:27-32` swallows `ValidationError`; `validators.py:43` literal `pass` |
| Persist screenshot | **Missing** | file never saved; `image_path` stores raw client filename (`views.py:46`) |
| Inspect candlestick structure via AI | Missing (deterministic engine does this, not the AI) | `analysis/services.py` never opens the image |
| Identify visible instrument/timeframe | **Broken** | `extract_symbol_timeframe({}, hints)` — echoes user hint or fabricates `EURUSD/M15` (`services.py:34-36,103-105`) |
| Screenshot timestamp reconciliation | **Missing** | no EXIF/capture-time code anywhere |
| Compare screenshot with MT5 data | Partially implemented | only the `data_synchronized` boolean compared (`services.py:63-76`) |
| Never invent price levels | **Partially implemented / enforced only by mock's hardcoding** | guard fires only when `data_synchronized` False; mock counts as synchronized (`services.py:122,139-149`) |
| Report uncertainty / missing evidence | Verified working | `uncertainty`/`errors` fields populated on failure paths |
| WAIT on insufficient info | Verified working | schema default + forced WAIT (`schemas.py:47`, `services.py:145-149`) |

## B. MT5 market data (MASTER_SPEC §3.B)

| Requirement | Status | Evidence |
|---|---|---|
| Connection status | Verified working | `/api/mt5/status/` (reproduced live: broker MetaQuotes-Demo) |
| Broker/server metadata | Verified working | `mt5_connector.py:100-118` (live output captured) |
| Symbol discovery | Implemented but unverified | `get_symbols` untested |
| **Symbol suffix handling (EURUSD.pro)** | **Missing** | zero `suffix` code repo-wide (spec §B explicit requirement) |
| Historical OHLCV M1/M5/M15/H1 | Implemented but unverified (mapping correct; live M15 seen) | `mt5_connector.py:28-33`; no timeframe tests |
| OHLC validation | Partially implemented (dead checks) | `providers.py:57-60` are `pass`; no NaN guard |
| Current bid/ask + spread | Partially implemented | live tick path works; **mock tick broken** → R-09 (`NameError: utcnow`) |
| Spread units consistency | **Broken** | candles=MT5 points, ticks=price, risk consumes pips — no converter |
| **UTC normalization** | **Broken on live path (observed)** | bars returned 2h12m AHEAD of machine UTC (2026-10-09 17:33Z vs bars 19:45–20:15Z) |
| Data freshness checks | **Missing** | `analysis/services.py:50` hardcodes `"stale": False` |
| Reconnection handling | Partially implemented | retry only around `initialize` (`mt5_connector.py:60-70`) |
| Market-closure handling | **Missing** | zero weekend/closed-market code |
| Mock labeled, never silently substituted | Verified working (labeling) but **tests actually run live** | factory has no fallback; `.env` `MT5_USE_MOCK=false` → live provider in suite (CRIT-04) |
| Credentials from env | **Broken (dead config)** | `marketdata/settings.py` never imported; provider constructed with no args (`factory.py:18`) |
| MT5 worker service + auth token | **Missing** | `mt5_worker/app.py` scaffold; `MT5_WORKER_*` unread by any code |

## C. Market structure engine (MASTER_SPEC §3.C — 19 detectors)

| # | Detector | Status | Evidence |
|---|---|---|---|
| 1 | Swing highs/lows | Verified working | `swings.py:13-71`, bounds verified |
| 2 | HH/HL/LH/LL | Verified working (labels), Untested in suite | `swings.py:74-104` |
| 3 | Bullish/bearish BOS | **Missing (stub returns [])** | `bos.py:11-32` → R-05 |
| 4 | Bullish/bearish CHOCH | **Missing (stub returns [])** | same |
| 5 | MSS | **Missing** | same |
| 6 | Buy-side liquidity | **Missing** | `liquidity.py` only equal-highs |
| 7 | Sell-side liquidity | **Missing** | equal lows absent → R-14-equivalent (agent-traced) |
| 8 | Liquidity sweeps | **Missing** | zero sweep code |
| 9 | Equal highs/lows | Partially implemented | equal highs only; duplicates on runs |
| 10 | Displacement | **Missing** | zero matches repo-wide |
| 11 | FVG creation | **Broken — direction labels inverted** | `fvg.py:22,37` → R-02/R-03 |
| 12 | FVG mitigation/invalidation | **Missing** | docstring claims it; no function |
| 13 | Order blocks | **Broken — module unimportable** (`SyntaxError`) + placeholder logic | `orderblocks.py:3` → R-01 |
| 14 | Premium/discount zones | **Missing** | zero matches |
| 15 | Support/resistance | **Missing** | zero matches |
| 16 | S/R flips | **Missing** | zero matches |
| 17 | Rejection candles | **Missing** | zero matches |
| 18 | Engulfing patterns | **Missing** | zero matches |
| 19 | Multi-timeframe alignment | **Broken** | H1 always `[]`; M5/M1 computed then ignored; bias = last-swing type (inverted) → R-06; `conflicts` hardcoded `[]` |
| — | Configurable parameters | Partially implemented | `threshold_pips`, `min_strength`, `lookback` accepted but unused |
| — | Unit tests per detector | **Missing** | 2 structure tests, both vacuous (`len >= 0`, `isinstance list`) |
| — | No look-ahead (spec rule) | Partially implemented | detection windows correct, but events stamped at formation bar with no `confirmed_at` (latent repainting) |

## D. Primary trading model (MASTER_SPEC §3.D)

| Requirement | Status | Evidence |
|---|---|---|
| 10-step bullish sequence (SL sweep → displacement → MSS → FVG → M1 confirm…) | **Missing** | steps 3–5 depend on absent detectors (sweeps/displacement/MSS) |
| Never BUY/SELL on a single pattern | **Broken in effect** | `evaluate_scenario` = bias + "any FVG anywhere in history" (`analysis.py:39-45`), no confluence weighting, no levels |
| BUY SCENARIO / SELL SCENARIO / WAIT supported | Partially implemented | WAIT paths solid; BUY/SELL directionally corrupted by CRIT-02 + H-05 |
| Entry/invalidation/RR/cost evaluation in scenario | Missing from scenario | `evaluate_scenario` returns decision only, no levels; risk engine separate |

## E. AI reasoning / LangGraph (MASTER_SPEC §3.E)

| Requirement | Status | Evidence |
|---|---|---|
| LangGraph orchestration (10 nodes) | **Missing** | no dep/import/graph; single synchronous method |
| Screenshot inspection node | Missing | image never read |
| Market-data retrieval/validation nodes | Partially implemented (plain functions) | `services.py:40-76` |
| Structure/MTF nodes | Partially implemented (single-TF; broken bias) | §C rows 19 |
| Evidence reconciliation node | **Missing** (stub compares one boolean) | `services.py:63-76` |
| Scenario/risk nodes | Partially implemented | deterministic scenario + risk engine exist, not graph-wired |
| Structured response validation | Verified working | Pydantic; failure → WAIT |
| Persistence node | Verified working (with silent-failure caveat) | `views.py:43-57` (`except: analysis=None`) |
| Real vision/reasoning providers | **Missing** | `OpenAIProvider` raises; `get_llm_provider()` returns mock in both branches (`llm.py:49-57`) |
| LLM error → WAIT, no fabrication | Verified working (for mock) | `services.py:134-137` + schema default |
| Deterministic output authoritative over LLM | **Missing** | final `decision` = LLM value; deterministic stored separately (`services.py:151-157`) |

## F. Probability engine (MASTER_SPEC §3.F)

| Requirement | Status | Evidence |
|---|---|---|
| Precise prediction outcomes | **Missing** | no outcome definition/linking in engine |
| Historical setup performance | **Broken — fabricated** | `engine.py:85` `pnl = 1.0` dummy → win_rate 100% → R-16/R-17 |
| Chronological train/val/test splits | Partially implemented | main path slices chronologically; **fallback runs train==test** (`walkforward.py:25-28`) |
| Walk-forward testing | Partially implemented | windows chronological; `overall` re-runs last window instead of aggregating → R-18 |
| Avoid data leakage | Verified in main windowing (`engine.py:61`) / **Broken in fallback** | repro + code |
| Spread/commission/slippage modeled | **Missing (dead parameters)** | params never referenced after signature → R-16 |
| Win rate/expectancy/drawdown/PF | **Broken — computed on dummy data** | `engine.py:80-102` |
| Probability calibration | Missing (stub honest) | `probability.py:29-36` returns null always ≥30 |
| Null probability <30 samples | **Verified working** | `probability.py:20-28` → null + reason |
| Sample sizes & confidence intervals | Partially implemented | `sample_size` reported; **CI `[0.3,0.7]` hardcoded** (fabricated figure) |
| Data drift detection | **Missing** | zero matches |
| Never present confluence as probability | Verified working | `probability=None`, `calibrated=False` |

## G. Risk management (MASTER_SPEC §3.G)

| Requirement | Status | Evidence |
|---|---|---|
| Risk per trade / SL / TP / RR | Verified working | `calculations.py:38-53`, `scenarios.py` (tested) |
| Position sizing | **Broken — pip value wrong** | `calculations.py:74` → R-11: 1.1 lots vs 1.0 (+10%) |
| Contract specs per symbol | Partially implemented | 7 majors hardcoded; others fabricated → R-12 |
| Max spread threshold | Verified working (input is caller-supplied) | `scenarios.py:120-131` |
| Min R/R requirement | Verified working | `scenarios.py:105-117` |
| Market-data freshness check | **Missing** | not wired |
| Volatility filters | **Missing (dead imports)** | `check_volatility` imported, never called |
| Session filters | **Missing (no-op)** | `is_market_hours` always `True` |
| Economic-event restrictions | **Missing** | zero matches |
| Daily/weekly risk limits | **Missing** | zero matches |
| Input validation on trade-plan API | **Missing** | no serializer; NaN → 500 (agent-verified code path) |
| Analysis-only, no live orders | **Verified working** | zero `order_send`/trade-execution code repo-wide |

## H. Trading journal (MASTER_SPEC §3.H)

| Requirement | Status | Evidence |
|---|---|---|
| Record symbol/timeframe/decision/entry/SL/TP/RR/outcome/PNL/notes/tags | Verified working | `journal/models.py:14-25` |
| Uploaded screenshot in journal | **Missing** | no image field/link |
| Market-data snapshot | **Missing** | no snapshot field |
| Detected structures | **Missing** | — |
| Model version / strategy version | **Missing** | — |
| Estimated probability | **Missing** (metrics JSON could hold it; not wired) | — |
| Historical review (search) | Verified working | `/api/journal/search/` user-scoped |
| Performance reports | **Missing** | no analytics endpoints |
| CRUD | Partially implemented | create+search only; no retrieve/update/delete |

## I. User dashboard (MASTER_SPEC §3.I — frontend)

Frontend inventory: 1 page (`app/page.tsx`), 2 components, 1 API helper, 1 health route. Wired endpoints: `/api/health`, `/api/auth/{login,register,logout,me}` only.

| Feature | Status | Evidence |
|---|---|---|
| Overview dashboard | Partially implemented | real health cards; static unlabeled clock + "EURUSD · M15 primary" (`page.tsx:62,66`) |
| Screenshot upload | **Missing** | no component |
| AI analysis workspace | **Missing** | `page.tsx:8` comment |
| Live MT5 connection status | **Missing** | no `/api/mt5/*` fetch |
| Multi-timeframe bias | **Missing** | — |
| Interactive candlestick chart | **Missing** | no chart code (docs' "placeholder" claim false) |
| Detected structures / scenarios / R-R / probability explanations | **Missing** | zero matches |
| Analysis history | **Missing** | — |
| Trading journal | **Missing** | nav item disabled |
| Backtesting results / analytics | **Missing** | — |
| AI mentor chat | **Missing** | — |
| Settings | **Missing** | nav item disabled |
| **Login/register actually work** | **Broken** | token discarded before `GET /me` → 401 loop (`auth-panel.tsx:68-81`) |
| Dark professional theme | Verified working | `globals.css` |
| Misleading confidence/performance display | Verified absent | no % / win-rate / confidence in frontend (grep-verified) |

## Infrastructure & quality (MASTER_SPEC §4, §6)

| Requirement | Status | Evidence |
|---|---|---|
| Modular apps, service layer, typed Python | Verified working | 9 apps |
| Background jobs for expensive analysis | Missing | Celery configured; no analysis task enqueued |
| Labeled mock adapter, no silent substitution | Verified working (provider factory) **but** test/dev env runs live silently | CRIT-04 |
| Migrations/input validation/authN/authZ/rate limiting/upload limits/secure files | Partially implemented | auth/permissions/throttles verified; upload validation bypassed; file storage dead |
| Unit/integration/e2e tests | Partially implemented | 78 pass but structure detectors untested; e2e is API-level |
| Error handling/logging/ops docs | Verified working | `OPERATIONS.md`, redaction tested |
| Required tracking files present | Verified working | all exist (ROADMAP status table stale) |

## Phase-report claim spot-checks (not exhaustive)

| Claim | Verdict |
|---|---|
| PHASE_04 title "LangGraph Orchestration" | **False** (body hedges "LangGraph-style") |
| PHASE_04 "vision LLM / MT5 reconciliation" | Mock-only; boolean-only reconciliation |
| PHASE_04 "AI never fabricates price levels" | True only because the mock hardcodes empty levels |
| PHASE_02 "OHLC validation / staleness helpers / configurable retry" | Overstated — dead checks, no staleness code, retry env vars dead |
| PHASE_03 "BOS/CHOCH/OB" (report admits scaffolds) | Honest in report; **PROJECT_PROGRESS lists them as delivered features** |
| PHASE_06 "basic trade simulation / metrics" | **False** — dummy outcomes, costs ignored |
| PHASE_08 "All core workflows accessible / chart placeholder" | **False** — none exist in frontend |
| PHASE_09 "security review" | Missed: disabled upload validation, dead MEDIA_ROOT, pip-value math |
| README "live MetaTrader 5 data" (present tense) | Misleading |
| API.md "Validates image" | **False** (bypassed) |
