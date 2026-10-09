## CI

- Backend: `python manage.py check`, `python manage.py makemigrations --check --dry-run`, `pytest`
- Frontend: `npm ci`, `npm run typecheck`, `npm run build`

(see `.github/workflows/ci.yml`)

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