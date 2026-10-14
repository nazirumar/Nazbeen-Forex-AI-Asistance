"""Forward-testing app (Phase 11G §9/§10).

Analysis-only **simulated** forward testing: the deterministic engine is observed
bar-by-bar on live-fetched candles and every decision is recorded. Nothing here
places, routes or simulates a broker order — there is no order-execution code.
"""

default_app_config = "nazbeen_forex_ai.forwardtest.apps.ForwardTestConfig"
