"use client";

/**
 * Trading chart wrapper (Phase 11D §4; pro layout, Phase 11H follow-up).
 *
 * Renders real OHLC candles from the backend with:
 * - BOS / CHOCH / MSS markers anchored to the engine's confirmation bar;
 * - FVG + order-block zones drawn by `ZonesPrimitive` (timestamp/price aligned);
 * - liquidity levels and validated entry/SL/TP as price lines.
 *
 * Phase 11E adds: sweep / displacement markers, clustered support-resistance
 * and premium-discount midpoint lines, and the primary setup's entry/SL/TP
 * (drawn only for a complete setup — see `lib/chart-data.ts`).
 *
 * Phase 11H follow-up adds the professional trading-terminal chrome on top of
 * the canvas: a live OHLC legend (crosshair-linked, falls back to the last
 * closed bar), a faint symbol watermark, a live "last price" line and
 * Fit / Latest view controls. All of it is presentation only — the component
 * still never synthesizes bars: with no data it renders nothing and the parent
 * page shows its empty state.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  createChart,
  createSeriesMarkers,
  LineStyle,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type MouseEventParams,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import {
  buildDisplacementMarkers,
  buildLiquidityLines,
  buildMarkers,
  buildPremiumDiscountLine,
  buildSetupLevels,
  buildSupportResistanceLines,
  buildSweepMarkers,
  buildZones,
  planLevels,
  toChartCandles,
  toUtcSeconds,
  type ChartZone,
  type LevelLine,
} from "@/lib/chart-data";
import { formatPrice } from "@/lib/format";
import type { CandlePoint, SetupResult, StructureEvent, TradePlan } from "@/lib/types";
import { ZonesPrimitive } from "./zone-primitive";

export interface TradingChartProps {
  candles: CandlePoint[];
  events?: StructureEvent[];
  fvgs?: StructureEvent[];
  orderBlocks?: StructureEvent[];
  liquidity?: StructureEvent[];
  plan?: TradePlan | null;
  /** Phase 11E detector overlays. */
  sweeps?: StructureEvent[];
  displacement?: StructureEvent[];
  supportResistance?: StructureEvent[];
  premiumDiscount?: StructureEvent[];
  setup?: SetupResult | null;
  /** Display context for the on-canvas legend/watermark (presentation only). */
  symbol?: string;
  timeframe?: string;
}

const UP = "#26a69a";
const DOWN = "#ef5350";
const LEVEL_COLORS = { entry: "#22d3ee", sl: "#ef5350", tp: "#26a69a" };

/** "+0.00042" / "-0.00042" — sign always shown, matching terminal conventions. */
function signed(value: number, digits = 5): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
}

interface LegendValue {
  label: string;
  value: string;
  color: string;
}

/** Build the O/H/L/C readout for a bar (values colored by bar direction). */
function legendValues(bar: CandlePoint): LegendValue[] {
  const color = bar.close >= bar.open ? UP : DOWN;
  return [
    { label: "O", value: formatPrice(bar.open), color },
    { label: "H", value: formatPrice(bar.high), color },
    { label: "L", value: formatPrice(bar.low), color },
    { label: "C", value: formatPrice(bar.close), color },
  ];
}

export function TradingChart({
  candles,
  events = [],
  fvgs = [],
  orderBlocks = [],
  liquidity = [],
  plan = null,
  sweeps = [],
  displacement = [],
  supportResistance = [],
  premiumDiscount = [],
  setup = null,
  symbol = "",
  timeframe = "",
}: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick", Time> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const primitiveRef = useRef<ZonesPrimitive | null>(null);
  const priceLinesRef = useRef<IPriceLine[]>([]);
  const fittedRef = useRef(false);

  // Crosshair-linked legend: the hovered bar, or null to fall back to the last.
  const [hovered, setHovered] = useState<CandlePoint | null>(null);

  // Create / destroy the chart instance once per mount.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      width: container.clientWidth || 640,
      height: container.clientHeight || 380,
      layout: {
        background: { type: ColorType.Solid, color: "#0a0e14" },
        textColor: "#8b93a1",
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: "#141b23", style: LineStyle.Dotted },
        horzLines: { color: "#141b23", style: LineStyle.Dotted },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: "#4b5563",
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: "#1f2733",
        },
        horzLine: {
          color: "#4b5563",
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: "#1f2733",
        },
      },
      rightPriceScale: {
        borderColor: "#1c242e",
        scaleMargins: { top: 0.12, bottom: 0.12 },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: "#1c242e",
        rightOffset: 6,
        barSpacing: 8,
        minBarSpacing: 2,
        fixLeftEdge: true,
        lockVisibleTimeRangeOnResize: true,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: false,
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
      },
      localization: { locale: "en-US" },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: UP,
      downColor: DOWN,
      borderVisible: false,
      wickUpColor: UP,
      wickDownColor: DOWN,
      // Terminal-style current-price line + axis label (built-in, not a
      // createPriceLine call, so level/plan lines stay the only custom ones).
      priceLineVisible: true,
      priceLineColor: "#64748b",
      priceLineStyle: LineStyle.Dashed,
      priceLineWidth: 1,
      lastValueVisible: true,
    });

    const markers = createSeriesMarkers<Time>(series, []);
    const primitive = new ZonesPrimitive([]);
    series.attachPrimitive(primitive);

    chartRef.current = chart;
    seriesRef.current = series;
    markersRef.current = markers;
    primitiveRef.current = primitive;

    const observer = new ResizeObserver((entries) => {
      const rect = entries[0]?.contentRect;
      if (rect && rect.width > 0 && rect.height > 0) {
        chart.applyOptions({ width: Math.floor(rect.width), height: Math.floor(rect.height) });
      }
    });
    observer.observe(container);

    return () => {
      observer.disconnect();
      priceLinesRef.current = [];
      markersRef.current = null;
      primitiveRef.current = null;
      seriesRef.current = null;
      chartRef.current = null;
      chart.remove();
    };
  }, []);

  // Candles + markers (normalized once; library rejects unordered input).
  useEffect(() => {
    const series = seriesRef.current;
    const markers = markersRef.current;
    if (!series || !markers) return;
    const data = toChartCandles(candles);
    series.setData(data);
    // Structure breaks plus Phase 11E sweep/displacement events, merged and
    // re-sorted chronologically (the library rejects unordered markers).
    const allMarkers = [
      ...buildMarkers(events),
      ...buildSweepMarkers(sweeps),
      ...buildDisplacementMarkers(displacement),
    ].sort((a, b) => a.time - b.time);
    markers.setMarkers(allMarkers as SeriesMarker<Time>[]);
    if (data.length > 0 && !fittedRef.current) {
      chartRef.current?.timeScale().fitContent();
      fittedRef.current = true;
    }
  }, [candles, events, sweeps, displacement]);

  // Zones (FVG / order blocks) redraw through the primitive.
  useEffect(() => {
    const primitive = primitiveRef.current;
    if (!primitive) return;
    const last = candles.length ? candles[candles.length - 1] : null;
    const zones: ChartZone[] = buildZones(fvgs, orderBlocks, last);
    primitive.setZones(zones);
  }, [candles, fvgs, orderBlocks]);

  // Liquidity levels + validated plan/setup levels as price lines.
  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;
    for (const line of priceLinesRef.current) series.removePriceLine(line);
    priceLinesRef.current = [];

    const add = (line: LevelLine) => {
      const created = series.createPriceLine({
        price: line.price,
        color: line.color,
        lineWidth: 1,
        lineStyle: line.lineStyle === "dashed" ? LineStyle.Dashed : LineStyle.Solid,
        axisLabelVisible: true,
        title: line.title,
      });
      priceLinesRef.current.push(created);
    };

    for (const line of buildLiquidityLines(liquidity)) add(line);

    // Phase 11E: support/resistance, premium/discount midpoint and the primary
    // setup's entry/SL/TP (complete setups only — see the builders).
    for (const line of buildSupportResistanceLines(supportResistance)) add(line);
    for (const line of buildPremiumDiscountLine(premiumDiscount)) add(line);
    for (const line of buildSetupLevels(setup)) add(line);

    const levels = planLevels(plan);
    if (levels.entry !== null) {
      add({ price: levels.entry, title: "Entry", color: LEVEL_COLORS.entry, lineStyle: "solid" });
    }
    if (levels.sl !== null) {
      add({ price: levels.sl, title: "SL", color: LEVEL_COLORS.sl, lineStyle: "solid" });
    }
    if (levels.tp !== null) {
      add({ price: levels.tp, title: "TP", color: LEVEL_COLORS.tp, lineStyle: "solid" });
    }
  }, [liquidity, plan, supportResistance, premiumDiscount, setup]);

  // Crosshair → legend. Uses a per-bar lookup so state only changes when the
  // pointer moves to a different bar (same bar object → React bails out).
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || typeof chart.subscribeCrosshairMove !== "function") return;
    const byTime = new Map<number, CandlePoint>();
    for (const bar of candles) {
      const t = toUtcSeconds(bar.time);
      if (t !== null) byTime.set(t, bar);
    }
    const handleMove = (param: MouseEventParams<Time>) => {
      const t = param.time;
      setHovered(typeof t === "number" ? (byTime.get(t) ?? null) : null);
    };
    chart.subscribeCrosshairMove(handleMove);
    return () => {
      if (typeof chart.unsubscribeCrosshairMove === "function") {
        chart.unsubscribeCrosshairMove(handleMove);
      }
    };
  }, [candles]);

  const fitContent = () => chartRef.current?.timeScale().fitContent();
  const goToLatest = () => {
    const scale = chartRef.current?.timeScale();
    if (scale && typeof scale.scrollToRealTime === "function") scale.scrollToRealTime();
  };

  // Chronological view of the props (the library sorts too) so the legend's
  // "last bar" is the newest bar by time, and change is vs the prior close —
  // robust even if the caller hands bars out of order.
  const sorted = useMemo(() => {
    return candles
      .map((bar) => ({ t: toUtcSeconds(bar.time), bar }))
      .filter((entry): entry is { t: number; bar: CandlePoint } => entry.t !== null)
      .sort((a, b) => a.t - b.t);
  }, [candles]);

  const lastBar = sorted.length ? sorted[sorted.length - 1].bar : null;
  const shown = hovered ?? lastBar;
  const shownIndex = shown ? sorted.findIndex((entry) => entry.bar.time === shown.time) : -1;
  const prevClose = shownIndex > 0 ? sorted[shownIndex - 1].bar.close : null;
  const change = shown && prevClose !== null ? shown.close - prevClose : null;
  const changePct = change !== null && prevClose ? (change / prevClose) * 100 : null;
  const values = shown ? legendValues(shown) : [];
  const changeColor = change === null ? "#8b93a1" : change >= 0 ? UP : DOWN;

  return (
    <div className="relative h-full w-full min-h-[360px] cursor-crosshair">
      <div ref={containerRef} className="absolute inset-0" data-testid="chart-container" />

      {/* Faint watermark behind the candles, like a pro terminal. */}
      {symbol ? (
        <div
          className="pointer-events-none absolute inset-0 flex select-none items-center justify-center overflow-hidden"
          aria-hidden="true"
        >
          <span className="whitespace-nowrap text-5xl font-bold tracking-tight text-white/[0.035]">
            {symbol}
            {timeframe ? <span className="ml-3 font-medium">{timeframe}</span> : null}
          </span>
        </div>
      ) : null}

      {/* Live OHLC legend (TradingView-style). */}
      <div
        className="pointer-events-none absolute left-3 top-2.5 z-10 flex flex-wrap items-baseline gap-x-3 gap-y-1 leading-none"
        data-testid="chart-legend"
      >
        {symbol ? (
          <span className="text-xs font-semibold tracking-wide text-zinc-200">
            {symbol}
            {timeframe ? <span className="text-zinc-500"> · {timeframe}</span> : null}
          </span>
        ) : null}
        {shown ? (
          <span className="flex flex-wrap items-baseline gap-x-2 font-mono text-[11px] tabular-nums">
            {values.map((v) => (
              <span key={v.label} className="flex items-baseline gap-0.5">
                <span className="text-zinc-500">{v.label}</span>
                <span style={{ color: v.color }}>{v.value}</span>
              </span>
            ))}
            {change !== null ? (
              <span className="flex items-baseline gap-1" style={{ color: changeColor }}>
                <span>{signed(change)}</span>
                {changePct !== null ? <span>({signed(changePct, 2)}%)</span> : null}
              </span>
            ) : null}
          </span>
        ) : null}
      </div>

      {/* View controls. */}
      <div className="absolute right-2 top-2 z-10 flex items-center gap-0.5 rounded-lg border border-zinc-800/80 bg-[#0c1118]/90 p-0.5 backdrop-blur-sm">
        <button
          type="button"
          onClick={fitContent}
          title="Fit content"
          className="rounded-md px-2 py-1 text-[11px] font-medium text-zinc-400 transition hover:bg-zinc-800 hover:text-zinc-100"
          data-testid="chart-fit"
        >
          Fit
        </button>
        <button
          type="button"
          onClick={goToLatest}
          title="Scroll to latest bar"
          className="rounded-md px-2 py-1 text-[11px] font-medium text-zinc-400 transition hover:bg-zinc-800 hover:text-zinc-100"
          data-testid="chart-latest"
        >
          Latest
        </button>
      </div>
    </div>
  );
}
