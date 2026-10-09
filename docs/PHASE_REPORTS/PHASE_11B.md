# PHASE 11B — Real Vision & Reasoning LLM Providers

**Status:** ✅ completed 2026-10-09 — **awaiting owner approval before further 11B scope**
**Scope source:** owner instruction — "Implement real configurable Vision and Reasoning LLM
providers" (conditioned on Phase 11A correctness fixes being verified, which they are:
`15f96ff`, 145 tests green). This phase covers audit **H-03 (real-provider half)** and the
**LLM-subordination half of H-05**; LangGraph orchestration stays an owner decision (ADR-011).
No trading, no unrelated features.

## 1. Workstreams delivered

| ID | Workstream | What changed |
|---|---|---|
| 11B.1 | Provider configuration & factory | `settings/base.py`: `USE_MOCK_LLM`, `VISION_LLM_PROVIDER/_API_KEY/_MODEL`, `REASONING_LLM_PROVIDER/_API_KEY/_MODEL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, `LLM_RETRY_BACKOFF_SECONDS` (all via `env_*` helpers). `settings/test.py`: `USE_MOCK_LLM = True` (hermetic suite, same pattern as `MT5_USE_MOCK`). `analysis/llm.py` rewritten: `get_llm_provider(role)` builds a real OpenAI/Gemini adapter in real mode and raises `LLMConfigurationError` for missing/unsupported configuration — **there is no silent mock fallback**; the mock branch is only the explicit `USE_MOCK_LLM=true` switch. |
| 11B.2 | Transport hardening | `analysis/llm_transport.py`: per-attempt timeout, bounded retries with exponential backoff for connection errors/timeouts/429/5xx, `Retry-After` honored and capped at 30 s, 401/403 and other 4xx fail fast. Safe errors by construction: provider label + HTTP status + ≤300-char body with known secrets stripped (`***REDACTED***`); payloads/headers are never echoed. Retry logging at DEBUG carries label/attempt only. |
| 11B.3 | Real adapters (OpenAI + Gemini) | `analysis/llm_providers.py`: `OpenAIProvider` (Chat Completions; base64 `image_url` data part for screenshots; `response_format: json_object`) and `GeminiProvider` (`generateContent`; `inline_data` image part; `responseMimeType: application/json`; API key in the `x-goog-api-key` **header**, never the URL). Both parse the model output, strip code fences, tolerate stray prose, and validate against Pydantic schemas — malformed or schema-violating output raises `LLMResponseFormatError` instead of being guessed at. |
| 11B.4 | Deterministic authority in the service | `analysis/schemas.py`: new `LLMChartAssessment` + `LLMReasoningOutput` claim schemas — **deliberately contain no `decision` field**: the LLM reports observations/explanations only. `analysis/services.py` rewritten: forwards the validated screenshot bytes to the vision provider; asks the reasoning provider for a write-up grounded in deterministic findings; `apply_deterministic_authority()` makes the deterministic decision final (LLM can never upgrade WAIT→BUY/SELL, never overrides BUY/SELL), strips levels when data is unsynchronized, records direction/symbol disagreements as resolved-in-favor-of-deterministic; LLM candidate levels stay `evidence` entries tagged `source="ai"` / "unverified" and **never** become `entry_levels`/`sl`/`tp`; provider failures land in `errors` + `uncertainty` and the analysis continues deterministic-only with `WAIT` unless the engine itself confirmed a setup. |
| 11B.5 | Smoke test + docs | `manage.py llm_smoke --role {vision,reasoning,both} [--image PATH] [--allow-mock]`: one real call per role, prints provider/model/latency/redacted output (never the key); **refuses to run under mock mode without `--allow-mock`** and labels its output `MOCK — NOT A REAL PROVIDER TEST` / `REAL PROVIDER` so a wiring check can never be mistaken for a live test. Documented in `docs/TESTING.md`; ADR-011 in `docs/DECISIONS.md`. |

## 2. Every changed file

**Modified (7 code + 1 lockfile + 4 docs):**

| File | Workstream |
|---|---|
| `pyproject.toml` / `uv.lock` | 11B.2 — `httpx` added via `uv add httpx` |
| `nazbeen_forex_ai/settings/base.py` | 11B.1 |
| `nazbeen_forex_ai/settings/test.py` | 11B.1 (mock isolation) |
| `nazbeen_forex_ai/analysis/llm.py` | 11B.1 (factory rewrite) |
| `nazbeen_forex_ai/analysis/schemas.py` | 11B.4 (claim schemas) |
| `nazbeen_forex_ai/analysis/services.py` | 11B.4 (orchestration) |
| `.env.example` | 11B.1/11B.2 (`USE_MOCK_LLM`, transport knobs) |
| `docs/DECISIONS.md`, `docs/TESTING.md`, `docs/PROJECT_PROGRESS.md`, `docs/audits/CRITICAL_ISSUES.md` | 11B.5 |

**Added (9 files):**

| File | Tests/role |
|---|---|
| `nazbeen_forex_ai/analysis/llm_errors.py` | error hierarchy (safe messages) |
| `nazbeen_forex_ai/analysis/llm_transport.py` | hardened HTTP transport |
| `nazbeen_forex_ai/analysis/llm_providers.py` | OpenAI + Gemini adapters |
| `nazbeen_forex_ai/analysis/management/__init__.py` (+ `commands/__init__.py`) | package scaffolding |
| `nazbeen_forex_ai/analysis/management/commands/llm_smoke.py` | smoke-test command |
| `nazbeen_forex_ai/analysis/tests/test_llm_providers.py` | **33** — factory, mock honesty, transport retries/429/timeout/redaction, OpenAI & Gemini adapters, key-never-rendered |
| `nazbeen_forex_ai/analysis/tests/test_llm_service.py` | **14** — authority precedence, image forwarding, level non-promotion, loud failures, API end-to-end |
| `nazbeen_forex_ai/analysis/tests/test_llm_smoke.py` | **8** — refusal, labels, image forwarding, non-zero exits |

**No existing test was modified, weakened, or deleted in this phase** — the mock-provider
contract changed internally (`generate_analysis` → `inspect_chart`/`reason`) but its only
consumer was `services.py`, so every pre-existing assertion was untouched.

## 3. Owner requirements → evidence

| # | Requirement | Where / verified by |
|---|---|---|
| 1 | Real provider adapters replace the mock-only factory | `llm.py::get_llm_provider`, `llm_providers.py`; `test_factory_builds_openai_vision_provider`, `test_factory_builds_gemini_reasoning_provider` |
| 2 | Screenshot image inputs for vision | OpenAI data-URL part / Gemini `inline_data`; `test_openai_inspect_chart_parses_structured_json`, `test_gemini_inspect_chart_parses_and_sends_inline_image`, `test_vision_provider_receives_screenshot_bytes`, `test_smoke_vision_forwards_image` |
| 3 | Structured JSON via validated Pydantic schemas | `response_format`/`responseMimeType` + `LLMChartAssessment`/`LLMReasoningOutput`; `test_openai_schema_violation_raises_format_error`, `test_openai_invalid_json_raises_format_error`, `test_gemini_missing_candidates_raises_format_error` |
| 4 | Mock providers kept for isolated tests | `MockLLMProvider` + `USE_MOCK_LLM=True` in test settings; `test_factory_returns_mock_in_mock_mode_even_when_real_configured`, `test_mock_provider_fabricates_nothing`, `test_upload_with_default_mock_providers_still_works` |
| 5 | Never silent mock fallback on real failure | factory raises `LLMConfigurationError`; service records the failure and continues deterministic-only; `test_factory_unconfigured_raises_never_silently_mocks`, `test_vision_failure_is_loud_and_never_mocked`, `test_configuration_error_surfaces_as_loud_error`, `test_smoke_misconfiguration_is_an_error_not_a_mock` |
| 6 | Timeouts, retries, rate limits, safe errors | `HTTPTransport`; `test_transport_429_retries_and_honours_retry_after`, `test_transport_rate_limit_exhausted_raises`, `test_transport_timeout_retries_then_succeeds`, `test_transport_retry_after_header_is_capped`, `test_transport_400_fails_fast_without_retry` |
| 7 | Never log/expose API keys | header-based auth, redacted `__repr__`/`describe`, secret-stripped errors; `test_openai_provider_never_renders_api_key`, `test_gemini_provider_never_renders_api_key`, `test_transport_401_fails_fast_and_names_no_key`, `test_transport_redacts_secret_from_provider_error_body` |
| 8 | Deterministic findings authoritative over the LLM | claim schemas have no `decision`; `apply_deterministic_authority` + disagreement records; `test_authority_*` ×4, `test_llm_levels_never_become_entry_levels`, `test_direction_disagreement_recorded_and_resolved_for_deterministic`, `test_upload_with_scripted_real_providers_returns_deterministic_wait` |
| 9 | WAIT when essential evidence can't be verified | unsynchronized data → WAIT + no levels; LLM/schema failure → WAIT with recorded errors; `test_authority_no_synchronized_data_forces_wait`, `test_configuration_error_surfaces_as_loud_error` |
| 10 | Mocked provider tests + real-provider smoke-test docs | §2 test counts; `docs/TESTING.md` "LLM provider smoke test"; `manage.py llm_smoke` |

## 4. Test results (real counts)

- `uv run pytest` → **200 passed, 0 failed** (14.06 s) — 145 pre-existing + **55 new**
  (33 + 14 + 8). No test was skipped, weakened, or deleted.
- `uv run python manage.py check` → clean; `makemigrations --check --dry-run` → no changes.
- Suite stays hermetic: test settings force `USE_MOCK_LLM = True`; every real-provider code
  path is exercised with fake HTTP sessions (no network, no keys).

## 5. How to run a real-provider smoke test

Documented in `docs/TESTING.md`; in short:

```powershell
# .env: USE_MOCK_LLM=false plus VISION_LLM_* / REASONING_LLM_* (provider: openai|gemini)
uv run python manage.py llm_smoke --role vision --image path\to\chart.png
uv run python manage.py llm_smoke --role reasoning
```

The command exits non-zero on misconfiguration or provider failure and never prints the key.

## 6. Explicitly not done (honest boundaries)

- **No real provider call was made *during implementation*** — corrected by the owner-directed
  live verification on 2026-10-09 (§8): real Google Gemini calls now verified for both roles.
- **LangGraph orchestration is not implemented** (H-03's other half) — master spec still
  requires it; awaiting the owner decision recorded in ADR-011.
- **H-04 symbol/timeframe defaults (`EURUSD`/`M15`) were not changed** — out of this scope;
  note that H-04's other half (fabricated LLM price levels passing the guard) is now
  structurally impossible: LLM levels can never reach `entry_levels`/`sl`/`tp`.
- **No live trading, no new endpoints, no frontend changes.**

## 7. Verification commands

```powershell
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run pytest
uv run pytest docs/audits/repro    # 15/15 audit repros still pass
```

## 8. Live real-provider verification (2026-10-09, owner-directed)

After implementation, the owner configured real credentials in `.env` (Google Gemini) and
requested a live check. Results — real Google Gemini API, no mocks:

- **Config findings fixed:** `gemini-2.5-flash` returned **HTTP 404** — Google has retired it
  for these keys ("use models/gemini-3.8-flash"). `.env` updated to `gemini-3.8-flash`,
  `USE_MOCK_LLM=false` added (it was missing, i.e. mock was still the default), and transport
  knobs raised to observed reality (`LLM_TIMEOUT_SECONDS=180`, backoff 5 s). API keys were
  never printed, logged, or echoed in any error.
- **Reasoning smoke:** HTTP 200, 12.3 s, schema-valid JSON, exit 0.
- **Vision smoke:** HTTP 200, 128 s under Google demand; summary correctly identified the
  input as a synthetic test chart with **zero fabricated price levels** (`candidate_levels=0`,
  `observed_symbol=None` — no axes were legible). The input image was synthetic (labeled as
  such on the image itself; no real chart was available) and is only an input fixture — not
  market data.
- **Transient 503s observed** ("high demand"): the transport retried with backoff exactly as
  designed; when retries were exhausted the failure surfaced in `errors` with exit 1 (smoke) /
  analysis-continues-deterministic-only (pipeline) — never a silent mock. One e2e run
  captured this failure path live (vision 503 ×3 → loud `errors` entry, `model` credited only
  the successful reasoning role).
- **End-to-end `analyze()` (both roles live, real MT5 data):** `source=mt5`,
  `decision=SELL` from the deterministic engine while the vision model read the chart
  **bullish** → recorded as a direction disagreement, `resolved=True` (deterministic
  retained); evidence = 3 deterministic + 3 AI-tagged; `entry_levels=[] sl=None tp=None`;
  `model=vision=gemini/gemini-3.8-flash, reasoning=gemini/gemini-3.8-flash`.

Honest boundaries: verification used Google Gemini only (no OpenAI key available), latency is
provider/load-dependent (up to ~2 min per call observed), and no claim is made about OpenAI
behavior beyond its unit-tested adapter paths.
