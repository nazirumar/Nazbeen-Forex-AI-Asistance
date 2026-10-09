"""Windows MT5 worker API (scaffold).

This scaffold shows the intended contract: the worker exposes authenticated
endpoints mirroring the Django API but backed directly by MetaTrader5.
Implementation is deferred until the worker is run on Windows with MT5.
"""

from __future__ import annotations

# Intended endpoints (conceptual):
# GET /status/ -> connection info (mode mt5, broker, server, build, etc.)
# GET /symbols/?search= -> symbol list
# GET /candles/?symbol=EURUSD&timeframe=M15&count=100 -> normalized candles (UTC Z)
# GET /tick/?symbol=EURUSD -> bid/ask/spread with timestamp (UTC Z)