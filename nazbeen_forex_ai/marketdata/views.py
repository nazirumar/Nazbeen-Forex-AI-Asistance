"""Market data API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nazbeen_forex_ai.marketdata.factory import get_market_data_provider
from nazbeen_forex_ai.marketdata.providers import MarketDataProviderError


class MT5StatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        provider = get_market_data_provider()
        try:
            provider.connect()
            info = provider.get_connection_info()
            return Response(info, status=status.HTTP_200_OK)
        except MarketDataProviderError as e:
            return Response(
                {"connected": False, "error": str(e), "mode": "mt5" if "MetaTrader" not in str(type(provider)) else "auto"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
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
        except MarketDataProviderError as e:
            return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class MT5CandlesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        provider = get_market_data_provider()
        symbol = request.query_params.get("symbol") or "EURUSD"
        timeframe = request.query_params.get("timeframe") or "M15"
        count = request.query_params.get("count")
        start_str = request.query_params.get("start")
        try:
            provider.connect()
            start_dt = None
            if start_str:
                try:
                    start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    start_dt = None
            cnt = int(count) if count else 100
            candles = provider.get_candles(symbol=symbol, timeframe=timeframe, start=start_dt, count=cnt)
            info = provider.get_connection_info()
            mode = "mock" if "Mock" in type(provider).__name__ else info.get("mode", "mt5")
            return Response(
                {
                    "symbol": symbol.upper(),
                    "timeframe": timeframe,
                    "count": len(candles),
                    "candles": [c.to_dict() for c in candles],
                    "data_source": mode,
                },
                status=status.HTTP_200_OK,
            )
        except MarketDataProviderError as e:
            return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class MT5TickView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        provider = get_market_data_provider()
        symbol = request.query_params.get("symbol") or "EURUSD"
        try:
            provider.connect()
            tick = provider.get_tick(symbol=symbol)
            info = provider.get_connection_info()
            mode = "mock" if "Mock" in type(provider).__name__ else info.get("mode", "mt5")
            return Response({**tick, "data_source": mode}, status=status.HTTP_200_OK)
        except MarketDataProviderError as e:
            return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)