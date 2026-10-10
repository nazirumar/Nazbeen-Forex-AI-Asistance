"""Structure API views (Phase 11D).

Exposes the deterministic ICT/SMC engine over HTTP so the dashboard chart can
draw BOS/CHOCH/MSS markers, FVG/order-block zones and liquidity levels that are
**aligned to real candle timestamps and prices** — the engine output is served
verbatim, never re-invented in the browser.

Design rules (MASTER_SPEC §3C/§7):

- Everything returned here is computed by the deterministic detectors from
  fetched candles; an empty detection list is returned as-is (the UI must show
  "none detected", never a fabricated marker).
- Multi-timeframe bias reuses :func:`nazbeen_forex_ai.structure.analysis.mtf_bias`
  including its real ``conflicts`` list. A timeframe whose data cannot be
  fetched is reported as ``null`` (unavailable) — it is never silently treated
  as NEUTRAL.
- Input validation, generic client errors and server-side-only exception logs
  follow the Phase 11C patterns from ``marketdata.views`` (audits M-03/L-02).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nazbeen_forex_ai.marketdata.factory import get_market_data_provider
from nazbeen_forex_ai.marketdata.freshness import assess_staleness, market_state
from nazbeen_forex_ai.marketdata.providers import MarketDataProviderError
from nazbeen_forex_ai.marketdata.views import (
    GENERIC_INTERNAL_ERROR,
    GENERIC_PROVIDER_ERROR,
    _validate_count,
    _validate_symbol,
    _validate_timeframe,
    provider_mode,
)
from nazbeen_forex_ai.structure.analysis import mtf_bias
from nazbeen_forex_ai.structure.bos import detect_bos_choch_mss
from nazbeen_forex_ai.structure.fvg import detect_fvg
from nazbeen_forex_ai.structure.liquidity import detect_liquidity
from nazbeen_forex_ai.structure.orderblocks import detect_orderblocks
from nazbeen_forex_ai.structure.swings import classify_structure, detect_swings
from nazbeen_forex_ai.structure.types import StructureEvent, candles_to_df

logger = logging.getLogger(__name__)

# Timeframes that make up the multi-timeframe bias view (MASTER_SPEC §1).
BIAS_TIMEFRAMES = ("H1", "M15", "M5", "M1")
# Candles fetched per auxiliary timeframe for bias computation.
MTF_COUNT = 120


def _fetch_candles(
    provider: Any, symbol: str, timeframe: str, count: int
) -> Optional[List[Dict[str, Any]]]:
    """Fetch candle dicts for one timeframe; None marks it unavailable.

    Failures are logged server-side and mapped to ``None`` so a single missing
    timeframe degrades honestly (bias shows "unavailable") instead of failing
    the whole request or inventing data.
    """
    try:
        candles = provider.get_candles(symbol=symbol, timeframe=timeframe, count=count)
    except Exception:
        logger.exception(
            "structure: candle fetch failed symbol=%s timeframe=%s", symbol, timeframe
        )
        return None
    if not candles:
        return None
    return [c.to_dict() for c in candles]


def _serialize_event(event: StructureEvent, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Detector event as JSON, adding the candle time for index-only events.

    Liquidity events carry only a bar index; the timestamp of that exact candle
    is attached here so the UI can align them — this is a mapping of real data,
    not an interpolation.
    """
    data = event.to_dict()
    idx = event.index
    if not data.get("confirmed_at") and idx is not None and 0 <= idx < len(candles):
        data["time"] = candles[idx]["time"]
    return data


class StructureView(APIView):
    """Detected market structure + multi-timeframe bias for one chart.

    ``GET /api/structure/?symbol=EURUSD&timeframe=M15&count=300``
    """

    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        try:
            symbol = _validate_symbol(request.query_params.get("symbol"))
            timeframe = _validate_timeframe(request.query_params.get("timeframe"))
            count = _validate_count(request.query_params.get("count"))
        except ValidationError as e:
            return Response(
                {"error": "Invalid request", "details": e.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        provider = get_market_data_provider()
        try:
            provider.connect()
            primary = _fetch_candles(provider, symbol, timeframe, count)
            if primary is None:
                # The chart's own data is missing — this is a provider failure,
                # exactly like GET /api/mt5/candles/ (503, generic message).
                logger.warning(
                    "structure: no candles symbol=%s timeframe=%s", symbol, timeframe
                )
                return Response(
                    {"error": GENERIC_PROVIDER_ERROR},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            # --- Deterministic detectors on the requested timeframe ---------
            events = detect_bos_choch_mss(primary)
            fvgs = detect_fvg(primary)
            order_blocks = detect_orderblocks(primary)
            liquidity = detect_liquidity(primary)
            swings = classify_structure(detect_swings(candles_to_df(primary)))

            # --- Multi-timeframe bias (H1/M15/M5/M1 + real conflicts) -------
            aux: Dict[str, Optional[List[Dict[str, Any]]]] = {}
            for tf in BIAS_TIMEFRAMES:
                aux[tf] = primary if tf == timeframe else _fetch_candles(provider, symbol, tf, MTF_COUNT)
            raw_bias = mtf_bias(
                aux["H1"] or [],
                aux["M15"] or [],
                aux["M5"] or [],
                aux["M1"] or [],
            )
            mtf: Dict[str, Any] = {
                # Unfetchable timeframe -> null ("unavailable" in the UI);
                # mtf_bias saw [] for it, so conflicts stay truthful.
                tf: (raw_bias[tf] if aux[tf] else None)
                for tf in BIAS_TIMEFRAMES
            }
            mtf["conflicts"] = raw_bias["conflicts"]

            freshness = assess_staleness(
                primary[-1]["time"],
                timeframe,
                threshold_sec=int(settings.MT5_STALENESS_THRESHOLD_SEC),
            )
        except MarketDataProviderError:
            logger.exception("structure: provider failure symbol=%s timeframe=%s", symbol, timeframe)
            return Response(
                {"error": GENERIC_PROVIDER_ERROR},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception:
            logger.exception("structure: unexpected failure symbol=%s timeframe=%s", symbol, timeframe)
            return Response(
                {"error": GENERIC_INTERNAL_ERROR},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "count": len(primary),
                "data_source": provider_mode(provider),
                "market_state": market_state(),
                "stale": freshness["stale"],
                "last_bar_age_sec": freshness["last_bar_age_sec"],
                "threshold_sec": freshness["threshold_sec"],
                "swings": swings,
                "events": [_serialize_event(e, primary) for e in events],
                "fvgs": [f.to_dict() for f in fvgs],
                "order_blocks": [o.to_dict() for o in order_blocks],
                "liquidity": [self._liq(e, primary) for e in liquidity],
                "mtf": mtf,
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _liq(event: StructureEvent, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        return _serialize_event(event, candles)
