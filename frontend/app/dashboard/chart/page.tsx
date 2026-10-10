"use client";

/**
 * Chart page (Phase 11D §4/§7): real OHLC candles + structure overlays from
 * `GET /api/mt5/candles/` and `GET /api/structure/`, with the risk panel's
 * validated entry/SL/TP levels drawn on the chart when the backend computes
 * them. Loading, empty and error states replace the chart whenever data is
 * not available — nothing is ever synthesized to fill the canvas.
 */

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { TradingChart } from "@/components/chart/trading-chart";
import { useMarket } from "@/components/layout/market-context";
import { RiskPanel } from "@/components/risk/risk-panel";
import { DataSourceBadge, EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import type { CandlesResponse, StructureResponse, TradePlan } from "@/lib/types";

export default function ChartPage() {
  const { symbol, timeframe } = useMarket();
  const [candles, setCandles] = useState<CandlesResponse | null>(null);
  const [structure, setStructure] = useState<StructureResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [plan, setPlan] = useState<TradePlan | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = `symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}&count=300`;
      const [c, s] = await Promise.all([
        api<CandlesResponse>(`/api/mt5/candles/?${qs}`),
        api<StructureResponse>(`/api/structure/?${qs}`),
      ]);
      setCandles(c);
      setStructure(s);
    } catch (err) {
      setError(err);
      setCandles(null);
      setStructure(null);
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="flex flex-col gap-4 xl:flex-row">
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <header className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h1 className="text-base font-semibold text-zinc-100">
              {symbol} <span className="text-zinc-500">· {timeframe}</span>
            </h1>
            {candles && <DataSourceBadge source={candles.data_source} />}
          </div>
          <div className="flex items-center gap-3 text-xs text-zinc-500">
            {candles && (
              <span data-testid="bar-count">
                {candles.count} bars · age{" "}
                {candles.last_bar_age_sec === null
                  ? "unknown"
                  : candles.last_bar_age_sec < 60
                    ? `${Math.round(candles.last_bar_age_sec)}s`
                    : `${Math.round(candles.last_bar_age_sec / 60)}m`}
              </span>
            )}
            <button
              type="button"
              onClick={() => void load()}
              className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 transition hover:bg-zinc-800"
            >
              Refresh
            </button>
          </div>
        </header>

        <div className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-2" data-testid="chart-panel">
          {loading ? (
            <div className="p-4">
              <LoadingState label={`Loading ${symbol} ${timeframe} candles…`} />
            </div>
          ) : error ? (
            <div className="p-4">
              <ErrorState error={error} label="Chart data unavailable" onRetry={() => void load()} />
            </div>
          ) : !candles || candles.candles.length === 0 ? (
            <div className="p-4">
              <EmptyState
                title="No candles available"
                hint="The provider returned no data for this symbol/timeframe. Nothing is displayed instead of fabricated bars."
              />
            </div>
          ) : (
            <TradingChart
              candles={candles.candles}
              events={structure?.events ?? []}
              fvgs={structure?.fvgs ?? []}
              orderBlocks={structure?.order_blocks ?? []}
              liquidity={structure?.liquidity ?? []}
              plan={plan}
            />
          )}
        </div>

        {structure && (
          <p className="text-xs text-zinc-600">
            Overlays: BOS/CHOCH/MSS markers anchor to each break&apos;s confirmation bar; FVG and
            order-block rectangles span the engine&apos;s price band from their formation candle;
            liquidity levels and validated plan levels are drawn as horizontal lines.
          </p>
        )}
      </div>

      <aside className="w-full shrink-0 xl:w-96">
        <RiskPanel onPlan={setPlan} />
      </aside>
    </div>
  );
}
