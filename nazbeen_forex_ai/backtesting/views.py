"""Backtesting API views (Phase 11F).

Read-only surfacing of recorded backtest history. Scoped to the requesting user
so runs are never exposed across accounts; runs recorded without an owner are
not returned here.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nazbeen_forex_ai.backtesting.models import BacktestRun


def _serialize(run: BacktestRun) -> dict:
    return {
        "id": str(run.id),
        "symbol": run.symbol,
        "timeframe": run.timeframe,
        "total_trades": run.total_trades,
        "win_rate": run.win_rate,
        "profit_factor": run.profit_factor,
        "expectancy": run.expectancy,
        "max_drawdown": run.max_drawdown,
        "net_profit": run.net_profit,
        "metrics": run.metrics,
        "created_at": run.created_at.isoformat().replace("+00:00", "Z") if run.created_at else None,
    }


class BacktestRunListView(APIView):
    """`GET /api/backtests/` — the caller's recorded backtest runs."""

    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        runs = BacktestRun.objects.filter(user=request.user).order_by("-created_at")[:100]
        return Response(
            {"count": len(runs), "runs": [_serialize(run) for run in runs]},
            status=status.HTTP_200_OK,
        )
