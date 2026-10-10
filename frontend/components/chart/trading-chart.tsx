"use client";

/**
 * Trading chart wrapper (Phase 11D §4).
 *
 * Renders real OHLC candles from the backend with:
 * - BOS / CHOCH / MSS markers anchored to the engine's confirmation bar;
 * - FVG + order-block zones drawn by `ZonesPrimitive` (timestamp/price aligned);
 * - liquidity levels and validated entry/SL/TP as price lines.
 *
 * The component never synthesizes bars: with no data it renders nothing and
 * the parent page shows its empty state.
 */

import { useEffect, useRef } from "react";
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
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import {
  buildLiquidityLines,
  buildMarkers,
  buildZones,
  planLevels,
  toChartCandles,
  type ChartZone,
  type LevelLine,
} from "@/lib/chart-data";
import type { CandlePoint, StructureEvent, TradePlan } from "@/lib/types";
import { ZonesPrimitive } from "./zone-primitive";

export interface TradingChartProps {
  candles: CandlePoint[];
  events?: StructureEvent[];
  fvgs?: StructureEvent[];
  orderBlocks?: StructureEvent[];
  liquidity?: StructureEvent[];
  plan?: TradePlan | null;
}

const UP = "#26a69a";
const DOWN = "#ef5350";
const LEVEL_COLORS = { entry: "#22d3ee", sl: "#ef5350", tp: "#26a69a" };

export function TradingChart({
  candles,
  events = [],
  fvgs = [],
  orderBlocks = [],
  liquidity = [],
  plan = null,
}: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick", Time> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const primitiveRef = useRef<ZonesPrimitive | null>(null);
  const priceLinesRef = useRef<IPriceLine[]>([]);
  const fittedRef = useRef(false);

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
      grid: { vertLines: { color: "#151b23" }, horzLines: { color: "#151b23" } },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: "#3b4351", labelBackgroundColor: "#1f2733" },
        horzLine: { color: "#3b4351", labelBackgroundColor: "#1f2733" },
      },
      timeScale: { timeVisible: true, secondsVisible: false, borderColor: "#232a33" },
      rightPriceScale: { borderColor: "#232a33" },
      handleScroll: true,
      handleScale: true,
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: UP,
      downColor: DOWN,
      borderVisible: false,
      wickUpColor: UP,
      wickDownColor: DOWN,
      priceLineVisible: false,
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
    markers.setMarkers(buildMarkers(events) as SeriesMarker<Time>[]);
    if (data.length > 0 && !fittedRef.current) {
      chartRef.current?.timeScale().fitContent();
      fittedRef.current = true;
    }
  }, [candles, events]);

  // Zones (FVG / order blocks) redraw through the primitive.
  useEffect(() => {
    const primitive = primitiveRef.current;
    if (!primitive) return;
    const last = candles.length ? candles[candles.length - 1] : null;
    const zones: ChartZone[] = buildZones(fvgs, orderBlocks, last);
    primitive.setZones(zones);
  }, [candles, fvgs, orderBlocks]);

  // Liquidity levels + validated plan levels as price lines.
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
  }, [liquidity, plan]);

  return <div ref={containerRef} className="h-full min-h-[360px] w-full" data-testid="chart-container" />;
}
