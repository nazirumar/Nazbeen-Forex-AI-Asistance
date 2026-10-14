"use client";

/**
 * Chart page (Phase 11D §4/§7; pro layout, Phase 11H follow-up): real OHLC
 * candles + structure overlays from `GET /api/mt5/candles/` and
 * `GET /api/structure/`, with the risk panel's validated entry/SL/TP levels
 * drawn on the chart when the backend computes them. Loading, empty and error
 * states replace the chart whenever data is not available — nothing is ever
 * synthesized to fill the canvas.
 *
 * The header mirrors a trading terminal: symbol / timeframe / data-source /
 * market-state readouts plus a one-click timeframe switcher and refresh. The
 * canvas itself owns the Fit / Latest view controls and the OHLC legend.
 */

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { TradingChart } from "@/components/chart/trading-chart";
import { SetupChecklist } from "@/components/analysis/setup-checklist";
import { useMarket } from "@/components/layout/market-context";
import { RiskPanel } from "@/components/risk/risk-panel";
import { DataSourceBadge, EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { formatAge } from "@/lib/format";
import {
  TIMEFRAMES,
  type CandlesResponse,
  type StructureResponse,
  type TradePlan,
} from "@/lib/types";

export default function ChartPage() {
  const { symbol, timeframe, setTimeframe } = useMarket();
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

  const marketOpen = candles?.market_state === "open";

  return (
    <div className="flex flex-col gap-4 xl:flex-row xl:items-start">
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        {/* Terminal toolbar. */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-zinc-800 bg-[#0c1118] px-3 py-2">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-base font-semibold tracking-tight text-zinc-100">{symbol}</h1>
            <span className="rounded-md bg-zinc-800 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-zinc-300">
              {timeframe}
            </span>
            {candles && <DataSourceBadge source={candles.data_source} />}
            {candles && (
              <span
                className={`inline-flex items-center gap-1 text-[11px] font-medium ${
                  marketOpen ? "text-emerald-400" : "text-zinc-500"
                }`}
                data-testid="market-state"
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    marketOpen ? "bg-emerald-400" : "bg-zinc-600"
                  }`}
                />
                {marketOpen ? "Market open" : "Market closed"}
              </span>
            )}
            {candles?.stale && (
              <span className="rounded-md bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300">
                Stale
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <div
              className="flex items-center rounded-lg border border-zinc-800 bg-[#0a0e14] p-0.5"
              role="group"
              aria-label="Timeframe"
            >
              {TIMEFRAMES.map((tf) => (
                <button
                  key={tf}
                  type="button"
                  onClick={() => setTimeframe(tf)}
                  aria-pressed={tf === timeframe}
                  className={`rounded-md px-2.5 py-1 text-xs font-semibold transition ${
                    tf === timeframe
                      ? "bg-cyan-500/15 text-cyan-300"
                      : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => void load()}
              className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-300 transition hover:bg-zinc-800"
            >
              Refresh
            </button>
          </div>
        </div>

        {/* Chart canvas. */}
        <div
          className="relative h-[420px] overflow-hidden rounded-2xl border border-zinc-800 bg-[#0a0e14] sm:h-[500px] xl:h-[560px]"
          data-testid="chart-panel"
        >
          {loading ? (
            <div className="flex h-full items-center justify-center p-4">
              <LoadingState label={`Loading ${symbol} ${timeframe} candles…`} />
            </div>
          ) : error ? (
            <div className="flex h-full items-center justify-center p-4">
              <ErrorState error={error} label="Chart data unavailable" onRetry={() => void load()} />
            </div>
          ) : !candles || candles.candles.length === 0 ? (
            <div className="flex h-full items-center justify-center p-4">
              <EmptyState
                title="No candles available"
                hint="The provider returned no data for this symbol/timeframe. Nothing is displayed instead of fabricated bars."
              />
            </div>
          ) : (
            <TradingChart
              symbol={symbol}
              timeframe={timeframe}
              candles={candles.candles}
              events={structure?.events ?? []}
              fvgs={structure?.fvgs ?? []}
              orderBlocks={structure?.order_blocks ?? []}
              liquidity={structure?.liquidity ?? []}
              plan={plan}
              sweeps={structure?.sweeps ?? []}
              displacement={structure?.displacement ?? []}
              supportResistance={structure?.support_resistance ?? []}
              premiumDiscount={structure?.premium_discount ?? []}
              setup={structure?.setup ?? null}
            />
          )}
        </div>

        {candles && (
          <div className="flex flex-wrap items-center justify-between gap-2 px-1 text-xs text-zinc-500">
            <span data-testid="bar-count">
              {candles.count} bars · age {formatAge(candles.last_bar_age_sec)}
            </span>
            <span className="text-zinc-600">
              Hover the chart for OHLC · Fit / Latest control the view
            </span>
          </div>
        )}

        {structure && (
          <p className="text-xs text-zinc-600">
            Overlays: BOS/CHOCH/MSS markers anchor to each break&apos;s confirmation bar; sweep and
            displacement markers anchor to the confirming candle; FVG and order-block rectangles span
            the engine&apos;s price band from their formation candle; liquidity, support/resistance,
            premium/discount midpoint and validated setup/plan levels are drawn as horizontal lines.
          </p>
        )}

        <SetupChecklist setup={structure?.setup ?? null} />
      </div>

      <aside className="w-full shrink-0 xl:w-96">
        <RiskPanel onPlan={setPlan} />
      </aside>
    </div>
  );
}
