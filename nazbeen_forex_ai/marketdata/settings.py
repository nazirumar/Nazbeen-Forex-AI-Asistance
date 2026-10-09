"""MT5 settings and environment defaults for market data.

See MASTER_SPEC for configuration notes. MT5 is Windows-only; tests use mock.
"""

from __future__ import annotations

from nazbeen_forex_ai.config import env_bool, env_int, env_str

MT5_USE_MOCK = env_bool("MT5_USE_MOCK", True)
MT5_PATH = env_str("MT5_PATH", "")
MT5_LOGIN = env_int("MT5_LOGIN", 0)
MT5_SERVER = env_str("MT5_SERVER", "")
MT5_PASSWORD = env_str("MT5_PASSWORD", "")
MT5_TIMEOUT_SEC = env_int("MT5_TIMEOUT_SEC", 30)
MT5_RETRY_MAX = env_int("MT5_RETRY_MAX", 3)
MT5_RETRY_BACKOFF = float(env_str("MT5_RETRY_BACKOFF", "0.5") or "0.5")