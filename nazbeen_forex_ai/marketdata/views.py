"""Market data API endpoints.

Phase 11C hardening (audits M-03/M-04/L-02):

- Request parameters are strictly validated — invalid input returns **400**,
  never a 500 from an uncaught ``ValueError``/``int()`` failure, and ``count``
  is bounded (no unbounded fetch DoS).
- Provider failures return a generic client message; the real exception text
  is logged server-side only (never leaked to API clients).
- The provider-mode label is derived from the provider itself, not from an
  inverted string check (audit M-04).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nazbeen_forex_ai.marketdata.factory import get_market_data_provider
from nazbeen_forex_ai.marketdata.freshness import assess_staleness, market_state
from nazbeen_forex_ai.marketdata.providers import MarketDataProviderError

logger = logging.getLogger(__name__)

# Input-validation limits (audit M-03).
VALID_TIMEFRAMES = frozenset({"M1", "M5", "M15", "H1", "M1S", "M5S", "M15S"})
MAX_CANDLE_COUNT = 5000
DEFAULT_CANDLE_COUNT = 100
SYMBOL_RE = re.compile(r"^[A-Za-z0-9._/]{1,32}$")

GENERIC_PROVIDER_ERROR = "Market data is temporarily unavailable."
GENERIC_INTERNAL_ERROR = "Internal error while processing the request."


def provider_mode(provider: Any) -> str:
    """Honest provider-mode label from the provider instance (audit M-04).

    Walks the class hierarchy so subclasses (wrappers, test doubles) keep the
    identity of the provider they derive from.
    """
    hierarchy = " ".join(cls.__name__ for cls in type(provider).__mro__)
    if "Mock" in hierarchy:
        return "mock"
    if "MT5" in hierarchy:
        return "mt5"
    return "auto"


def _validate_symbol(raw: Optional[str]) -> str:
    symbol = (raw or "EURUSD").strip()
    if not SYMBOL_RE.match(symbol):
        raise ValidationError("symbol must be 1-32 characters of letters, digits, '.', '_' or '/'.")
    return symbol.upper()


def _validate_timeframe(raw: Optional[str]) -> str:
    timeframe = (raw or "M15").strip().upper()
    if timeframe not in VALID_TIMEFRAMES:
        raise ValidationError(
            f"timeframe must be one of {', '.join(sorted(VALID_TIMEFRAMES))}."
        )
    return timeframe


def _validate_count(raw: Optional[str]) -> int:
    if raw is None or raw == "":
        return DEFAULT_CANDLE_COUNT
    value = str(raw).strip()
    if not re.fullmatch(r"[0-9]+", value):
        raise ValidationError("count must be a positive integer.")
    count = int(value)
    if not (1 <= count <= MAX_CANDLE_COUNT):
        raise ValidationError(f"count must be between 1 and {MAX_CANDLE_COUNT}.")
    return count


def _validate_start(raw: Optional[str]) -> Optional[datetime]:
    if raw is None or raw == "":
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        raise ValidationError("start must be an ISO-8601 timestamp.")


class MT5StatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        provider = get_market_data_provider()
        try:
            provider.connect()
            info = provider.get_connection_info()
            return Response(
                {**info, "market_state": market_state()},
                status=status.HTTP_200_OK,
            )
        except MarketDataProviderError:
            logger.exception("MT5 status: provider failure")
            return Response(
                {
                    "connected": False,
                    "error": GENERIC_PROVIDER_ERROR,
                    "mode": provider_mode(provider),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception:
            logger.exception("MT5 status: unexpected failure")
            return Response(
                {
                    "connected": False,
                    "error": GENERIC_INTERNAL_ERROR,
                    "mode": provider_mode(provider),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MT5SymbolsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        provider = get_market_data_provider()
        search = request.query_params.get("search")
        try:
            provider.connect()
            symbols = provider.get_symbols(search=search)
            return Response({"symbols": symbols}, status=status.HTTP_200_OK)
        except MarketDataProviderError:
            logger.exception("MT5 symbols: provider failure")
            return Response({"error": GENERIC_PROVIDER_ERROR}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception:
            logger.exception("MT5 symbols: unexpected failure")
            return Response({"error": GENERIC_INTERNAL_ERROR}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MT5CandlesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        # Strict input validation (audit M-03): 400 for bad input, never 500.
        try:
            symbol = _validate_symbol(request.query_params.get("symbol"))
            timeframe = _validate_timeframe(request.query_params.get("timeframe"))
            count = _validate_count(request.query_params.get("count"))
            start_dt = _validate_start(request.query_params.get("start"))
        except ValidationError as e:
            return Response(
                {"error": "Invalid request", "details": e.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        provider = get_market_data_provider()
        try:
            provider.connect()
            candles = provider.get_candles(symbol=symbol, timeframe=timeframe, start=start_dt, count=count)
            # Freshness labels (Phase 11D): real age of the newest bar — the
            # dashboard's data-freshness indicator reads these. With no bars
            # the age is unknown (None), never dressed up as fresh.
            freshness = assess_staleness(
                candles[-1].time if candles else None,
                timeframe,
                threshold_sec=int(settings.MT5_STALENESS_THRESHOLD_SEC),
            )
            return Response(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "count": len(candles),
                    "candles": [c.to_dict() for c in candles],
                    "data_source": provider_mode(provider),
                    "market_state": market_state(),
                    "stale": freshness["stale"],
                    "last_bar_age_sec": freshness["last_bar_age_sec"],
                    "threshold_sec": freshness["threshold_sec"],
                },
                status=status.HTTP_200_OK,
            )
        except MarketDataProviderError:
            # Detail stays in the server log — never sent to the client (L-02).
            logger.exception("MT5 candles: provider failure symbol=%s timeframe=%s", symbol, timeframe)
            return Response({"error": GENERIC_PROVIDER_ERROR}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception:
            logger.exception("MT5 candles: unexpected failure symbol=%s timeframe=%s", symbol, timeframe)
            return Response({"error": GENERIC_INTERNAL_ERROR}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MT5TickView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        try:
            symbol = _validate_symbol(request.query_params.get("symbol"))
        except ValidationError as e:
            return Response(
                {"error": "Invalid request", "details": e.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )
        provider = get_market_data_provider()
        try:
            provider.connect()
            tick = provider.get_tick(symbol=symbol)
            return Response(
                {**tick, "data_source": provider_mode(provider)},
                status=status.HTTP_200_OK,
            )
        except MarketDataProviderError:
            logger.exception("MT5 tick: provider failure symbol=%s", symbol)
            return Response({"error": GENERIC_PROVIDER_ERROR}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception:
            logger.exception("MT5 tick: unexpected failure symbol=%s", symbol)
            return Response({"error": GENERIC_INTERNAL_ERROR}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
