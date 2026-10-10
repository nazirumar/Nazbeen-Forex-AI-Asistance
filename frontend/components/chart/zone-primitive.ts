"use client";

/**
 * Rectangle/line overlays for FVG and order-block zones (Phase 11D §4).
 *
 * Lightweight Charts has no native zone primitive, so this attaches a custom
 * `ISeriesPrimitive` to the candle series. Every frame it resolves each zone
 * through the library's public coordinate APIs
 * (`timeScale().timeToCoordinate()` + `series.priceToCoordinate()`), which
 * means the rectangles are recomputed against the *current* viewport on every
 * repaint (pan, zoom, price-scale resize) — zones stay pinned to the exact
 * candle timestamp and price band the backend reported. Unresolvable
 * coordinates are skipped, never approximated.
 */

import {
  type IChartApi,
  type IPrimitivePaneRenderer,
  type IPrimitivePaneView,
  type ISeriesApi,
  type ISeriesPrimitive,
  type PrimitivePaneViewZOrder,
  type SeriesAttachedParameter,
  type Time,
} from "lightweight-charts";
import type { ChartZone } from "@/lib/chart-data";

/** Resolve the canvas target type without importing `fancy-canvas` directly. */
type DrawTarget = Parameters<IPrimitivePaneRenderer["draw"]>[0];

class ZonesRenderer implements IPrimitivePaneRenderer {
  private readonly _get: () => {
    chart: IChartApi | null;
    series: ISeriesApi<"Candlestick", Time> | null;
    zones: ChartZone[];
  };

  constructor(get: () => { chart: IChartApi | null; series: ISeriesApi<"Candlestick", Time> | null; zones: ChartZone[] }) {
    this._get = get;
  }

  draw(target: DrawTarget): void {
    const { chart, series, zones } = this._get();
    if (!chart || !series || zones.length === 0) return;
    const timeScale = chart.timeScale();
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      for (const z of zones) {
        const x1 = timeScale.timeToCoordinate(z.from as Time);
        const x2 = timeScale.timeToCoordinate(z.to as Time);
        const yTop = series.priceToCoordinate(z.top);
        const yBottom = series.priceToCoordinate(z.bottom);
        if (x1 === null || x2 === null || yTop === null || yBottom === null) continue;
        const left = Math.min(Number(x1), Number(x2)) * scope.horizontalPixelRatio;
        const right = Math.max(Number(x1), Number(x2)) * scope.horizontalPixelRatio;
        const top = Math.min(Number(yTop), Number(yBottom)) * scope.verticalPixelRatio;
        const bottom = Math.max(Number(yTop), Number(yBottom)) * scope.verticalPixelRatio;
        const width = Math.max(right - left, 1);
        const height = Math.max(bottom - top, 1);
        ctx.fillStyle = z.color;
        ctx.fillRect(left, top, width, height);
        ctx.strokeStyle = z.color;
        ctx.lineWidth = 1 * scope.horizontalPixelRatio;
        ctx.strokeRect(left, top, width, height);
      }
    });
  }
}

class ZonesPaneView implements IPrimitivePaneView {
  private readonly _renderer: ZonesRenderer;

  constructor(get: () => { chart: IChartApi | null; series: ISeriesApi<"Candlestick", Time> | null; zones: ChartZone[] }) {
    this._renderer = new ZonesRenderer(get);
  }

  zOrder(): PrimitivePaneViewZOrder {
    return "bottom"; // zones sit behind the candles
  }

  renderer(): IPrimitivePaneRenderer {
    return this._renderer;
  }
}

export class ZonesPrimitive implements ISeriesPrimitive<Time> {
  private _chart: IChartApi | null = null;
  private _series: ISeriesApi<"Candlestick", Time> | null = null;
  private _zones: ChartZone[] = [];
  private _requestUpdate: (() => void) | null = null;
  private readonly _view: ZonesPaneView;

  constructor(initial: ChartZone[] = []) {
    this._zones = initial;
    this._view = new ZonesPaneView(() => ({
      chart: this._chart,
      series: this._series,
      zones: this._zones,
    }));
  }

  /** Replace the drawn zones and request a repaint. */
  setZones(zones: ChartZone[]): void {
    this._zones = zones;
    this._requestUpdate?.();
  }

  attached(param: SeriesAttachedParameter<Time>): void {
    this._chart = param.chart as IChartApi;
    this._series = param.series as ISeriesApi<"Candlestick", Time>;
    this._requestUpdate = param.requestUpdate;
  }

  detached(): void {
    this._chart = null;
    this._series = null;
    this._requestUpdate = null;
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return [this._view];
  }
}
