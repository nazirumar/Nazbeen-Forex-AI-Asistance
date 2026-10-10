# PHASE 11C — Remaining Data Integrity and Safety Remediation

**Status:** complete (owner-approved workstream WS-B / `RECOMMENDED_FIXES.md` P1.1–P1.8) ·
**Date:** 2026-10-10 · **Scope:** analysis-only; no trading capability added; no unrelated
functionality touched; OpenAI/Gemini integrations from Phase 11B untouched and green.

## 1. Workstreams delivered

| # | Requirement (owner priority) | Audit IDs | What was implemented |
|---|---|---|---|
| 1 | Persist screenshots with user-specific access control | H-02 / P1.3 | `MEDIA_ROOT`/`MEDIA_URL` defined; uploads saved under `media/screenshots/` with **server-generated UUID names**; `image_path` stores only the relative path; new `GET /api/analysis/<id>/screenshot/` is **ownership-scoped** (404 for non-owners, 401/403 anonymous, 404 when not stored); `resolve_screenshot_path()` refuses traversal/absolute paths; persistence failure is logged and never fabricates a path |
| 2 | Correct MTF bias conflict detection across H1/M15/M5/M1 | H-05 / P1.1 | `mtf_bias` now computes a **real `conflicts` list** (every disagreeing pair of decisive non-NEUTRAL biases); `analysis/services.py` fetches the auxiliary timeframes (H1/M5/M1 alongside the analyzed one) and passes real data through; conflicts reach `mtf_conflicts`, `deterministic_signals`, the LLM prompt and a `mtf_conflict` evidence item; `uses_mtf_data` is now computed, never assumed |
| 3 | Strengthen the fabrication guard | H-04 / P1.2 | Missing/blank symbol or timeframe → **`symbol`/`timeframe` = `null`, decision WAIT, zero market-data fetches** (the `EURUSD`/`M15` defaults are gone); `data_synchronized` now requires `source == "mt5"` **and** fresh data — mock can never authorize a decision or price level, stale data is labeled and blocks synchronization; uncertainty notes name the exact cause (identity unknown / mock / stale / market closed) |
| 4 | Fix walk-forward leakage and reporting defects | M-07, P-02, P-03 / P1.4 | Strict **chronology validation** (shuffled or duplicated timestamps → `ValueError`); insufficient-data fallback (train==test) explicitly marked `walk_forward: False` + `is_walk_forward: False` + reason "NOT a walk-forward"; normal windows marked `walk_forward: True`; `overall` remains a true aggregation of window trades; engine "one signal consumed per trade" verified with non-overlap regression tests |
| 5 | Remove fabricated probability confidence intervals | M-08 / P1.5 | Both uncalibrated branches of `evaluate_probability` now return `confidence_interval: []` (the `[0.0,1.0]` and `[0.3,0.7]` figures were fabricated); `probability` stays `null` without calibration |
| 6 | Strict input validation for candles and risk | M-03, M-05, L-02 / P1.6 | `/api/mt5/candles/` validates symbol (charset), timeframe (whitelist), `count` (**numeric, 1–5000** → was unbounded/`int()`-crash) and `start` (ISO) → **400**, never 500; trade-plan request serializer (`risk/serializers.py`) enforces finite/typed/bounded values (risk `0<x≤10`, positive prices, whitelist bias/symbol) → **400**; every provider/internal exception is logged server-side and answered with a **generic message** — no `str(e)` ever reaches a client |
| 7 | MT5 suffix, staleness, market closure | H-09 / P1.8 | Factory now wires the previously **dead `marketdata.settings` config** (path/login/server/password/timeout/retries/backoff + new `MT5_SYMBOL_SUFFIX`) into `MT5MarketDataProvider`; connector resolves symbols bare-first with configured-suffix fallback (and falls back to the requested name so the real error surfaces — never a fabricated symbol); new `marketdata/freshness.py` measures **last-bar age** against `max(MT5_STALENESS_THRESHOLD_SEC, 1.5×timeframe)` and provides a documented weekend **market-closure heuristic** (Fri 21:00→Sun 21:00 UTC) surfaced as `market_state` and in uncertainty notes |
| 8 | Preserve working OpenAI/Gemini integrations | — | No file under `analysis/llm/`, `analysis/llm_providers/` (11B adapters) or their tests was modified; the 55 provider/transport + service tests from 11B still pass unchanged |
| 9 | Comprehensive regression/integration tests | — | **86 new tests** across 7 new files (see §2/§4) + HTTP-level integration tests through the real URL stack |
| 10 | Update audit findings and progress docs | — | `CRITICAL_ISSUES.md` status banners (H-02/H-04/H-05/H-09/M-03/M-04/M-05/M-07/M-08/P-02/P-03/L-02 → resolved; P-01/M-09 and the rest remain open), `RECOMMENDED_FIXES.md` P1 status block, `PROJECT_PROGRESS.md`, `.env.example` |

### Deterministic authority preserved (11B behavior unchanged)

`apply_deterministic_authority` keeps its contract: no candles → WAIT; unsynchronized → WAIT;
the LLM can never upgrade WAIT to BUY/SELL; `entry_levels`/`sl`/`tp` stay empty in the
analysis path. The 11B disagreement/evidence flow is untouched.

## 2. Every changed file

**New:** `marketdata/freshness.py`, `risk/serializers.py`,
`structure/tests/test_mtf_conflicts.py`, `analysis/tests/test_fabrication_guard.py`,
`analysis/tests/test_screenshot_storage.py`, `backtesting/tests/test_walkforward_integrity.py`,
`marketdata/tests/test_validation_11c.py`, `marketdata/tests/test_mt5_connector.py`,
`risk/tests/test_trade_plan_validation.py`.

**Modified:** `structure/analysis.py` (real conflicts) · `analysis/services.py` (identity,
aux-TF fetch, sync rule, staleness/closure notes) · `analysis/storage.py` (UUID save + traversal-safe
resolve) · `analysis/views.py` (persist + screenshot endpoint) · `analysis/urls.py` (route) ·
`backtesting/walkforward.py` (chronology + fallback marking) · `backtesting/probability.py`
(empty CI) · `marketdata/views.py` (validation/redaction/mode) · `marketdata/factory.py`
(config wiring) · `marketdata/settings.py` (`MT5_SYMBOL_SUFFIX`) · `marketdata/mt5_connector.py`
(`symbol_suffix`, `_resolve_symbol`) · `risk/views.py` (serializer + generic errors) ·
`settings/base.py` (MEDIA + `MT5_STALENESS_THRESHOLD_SEC`) · `settings/test.py` (isolated
`MEDIA_ROOT`) · `.gitignore` (`.test_media/`) · `.env.example` (3 new documented vars) ·
`backtesting/tests/test_audit_regressions.py` + `docs/audits/repro/test_audit_regressions.py`
(fixture-timestamp repair, see below) · audit docs + `PROJECT_PROGRESS.md`.

### Documented test-fixture repair (NOT a weakening)

The `_oscillating_candles` helper in **both** audit-regression copies generated timestamps as
`minute = i % 60`, i.e. a cycling, out-of-order time series — precisely the defect the new
walk-forward chronology validation rejects. The helper now builds strictly increasing
timestamps via `timedelta(minutes=i)`. **No assertion was changed, added conditions removed,
or test deleted**; prices, counts and assertions are byte-identical, so test strength is
unchanged. This is recorded here per AGENTS.md test-strength-change policy.

## 3. Owner requirements → evidence

- **Screenshots persisted + user-scoped:** `test_upload_persists_screenshot_with_server_side_name`,
  `test_screenshot_endpoint_returns_image_to_owner`, `..._denies_other_users`, `..._requires_auth`,
  `..._path_traversal_is_refused`, `test_storage_helpers_refuse_traversal_and_absolute_paths`.
- **MTF conflicts real:** `test_mtf_conflicts.py` (7 tests, incl. fixture-sanity that both
  single-TF biases are what the fixtures claim) + `test_mtf_conflicts_surface_in_analysis_output`.
- **Fabrication guard:** `test_missing_identity_yields_null_symbol_timeframe_and_wait`,
  `test_blank_hints_are_treated_as_missing`, `test_mock_data_is_never_synchronized`,
  `test_llm_price_level_with_mock_data_is_rejected` (the audit's required regression),
  `test_stale_mt5_data_blocks_synchronization`, `test_fresh_mt5_data_is_synchronized`.
- **Walk-forward:** `test_insufficient_data_fallback_is_marked_not_walk_forward`,
  `test_walk_forward_rejects_shuffled_input`/`..._duplicate_timestamps`,
  `test_engine_never_overlapping_trades`, `test_each_bar_used_at_most_once_for_entries`.
- **No fabricated CI:** `test_probability_never_reports_ci_without_calibration`.
- **Input validation:** parametrized 400-cases (8 invalid queries, 10 invalid fields, 6 raw
  `NaN`/`Infinity` JSON bodies), `test_serializer_rejects_nonfinite_values_directly`,
  leak tests (`test_provider_error_text_is_never_leaked`, `test_internal_failure_returns_generic_500`).
- **Suffix/staleness/closure:** `test_mt5_connector.py` (suffix fallback/preferred/unresolvable,
  tick suffix, guards, factory wiring) + freshness/closure pure-function tests.

## 4. Test results (real counts)

```
uv run python manage.py check                → System check identified no issues (0 silenced)
uv run python manage.py makemigrations --check --dry-run → No changes detected
uv run pytest                                → 286 passed in 65.69s   (200 before this phase + 86 new)
uv run pytest docs/audits/repro              → 15 passed               (artifact still fully green)
```

No test was skipped, weakened or deleted. One existing test was made **hermetic**:
`test_error_path_mode_label_is_correct_mt5` initially assumed no terminal is installed; on this
machine a live MT5 terminal answers `connect()`, so the test now forces `mt5 = None` via
`monkeypatch` — it tests the same contract in every environment (the assertion is unchanged).

## 5. Explicitly not done (honest boundaries)

- **P-01 / M-09 detectors** (equal-high/low, sweeps, displacement, …), **M-10…M-16**, **H-10**
  docs pass, **L-01/L-03…L-07**, **frontend (P2.x)** — outside the approved 11C scope.
- **H-03/LangGraph** remains an owner decision (ADR-011); nothing in the 11B provider layer changed.
- Market-closure detection is a **documented weekend heuristic**, not a broker holiday calendar;
  it is surfaced as a state label and uncertainty note, never used to fabricate prices.
- Suffix handling is verified against a **mocked connector** (no real broker naming tested);
  live-terminal behavior remains a manual/local verification.
- `MEDIA_ROOT` is not exercised in production settings (development default `<repo>/media`);
  serving media in production (nginx/whitenoise) is not wired — the API endpoint streams files itself.
- Not re-verified in this phase (unchanged since 11B): OpenAI live calls (no key), Docker builds,
  live PostgreSQL/Redis, `mt5_worker`, frontend.

## 6. Verification commands

```powershell
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run pytest
uv run pytest docs/audits/repro
```
