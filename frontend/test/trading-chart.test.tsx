/**
 * Chart rendering tests (Phase 11D §4).
 *
 * Lightweight Charts is mocked at the module boundary; the assertions verify
 * that the component wires **real backend data** into the library correctly:
 * candles sorted+converted, markers anchored to confirmation bars, zones
 * attached through the primitive, and only computed levels drawn as lines.
 */

import { render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TradingChart } from "@/components/chart/trading-chart";
import { ZonesPrimitive } from "@/components/chart/zone-primitive";
import { toUtcSeconds } from "@/lib/chart-data";
import type { CandlePoint, StructureEvent, TradePlan } from "@/lib/types";
import { candlePoint } from "./helpers";

const m = vi.hoisted(() => {
  const setData = vi.fn();
  const setMarkers = vi.fn();
  const createPriceLine = vi.fn(() => ({ line: true }));
  const removePriceLine = vi.fn();
  const attachPrimitive = vi.fn();
  const fitContent = vi.fn();
  const applyOptions = vi.fn();
  const chartRemove = vi.fn();
  const series = {
    setData,
    setMarkers,
    createPriceLine,
    removePriceLine,
    attachPrimitive,
    priceToCoordinate: () => null,
  };
  const chart = {
    addSeries: vi.fn(() => series),
    timeScale: vi.fn(() => ({ fitContent, timeToCoordinate: () => null })),
    remove: chartRemove,
    applyOptions,
  };
  return {
    setData,
    setMarkers,
    createPriceLine,
    removePriceLine,
    attachPrimitive,
    fitContent,
    applyOptions,
    chartRemove,
    chart,
    series,
  };
});

vi.mock("lightweight-charts", () => ({
  createChart: vi.fn(() => m.chart),
  createSeriesMarkers: vi.fn(() => ({ setMarkers: m.setMarkers })),
  CandlestickSeries: Symbol("candlestick"),
  ColorType: { Solid: "solid" },
  CrosshairMode: { Normal: "normal" },
  LineStyle: { Solid: 0, Dashed: 2 },
}));

afterEach(() => {
  vi.clearAllMocks();
});

function ev(partial: Partial<StructureEvent>): StructureEvent {
  return {
    type: "BOS",
    direction: "bullish",
    index: 0,
    level: 1.1,
    levels: [1.099, 1.101],
    details: {},
    ...partial,
  } as StructureEvent;
}

const CANDLES: CandlePoint[] = [candlePoint(2), candlePoint(0), candlePoint(1)];

describe("TradingChart", () => {
  it("sets normalized candle data (sorted, unix seconds)", () => {
    render(<TradingChart candles={CANDLES} />);
    const data = m.setData.mock.calls[0][0] as { time: number }[];
    expect(data).toHaveLength(3);
    expect(data.map((d) => d.time)).toEqual([...data.map((d) => d.time)].sort((a, b) => a - b));
    expect(data[0].time).toBe(toUtcSeconds(CANDLES[1].time));
  });

  it("draws BOS/CHOCH/MSS markers aligned to their confirmation timestamps", () => {
    render(
      <TradingChart
        candles={CANDLES}
        events={[
          ev({ type: "BOS", confirmed_at: "2026-01-01T00:15:00Z" }),
          ev({ type: "CHOCH", direction: "bearish", confirmed_at: "2026-01-01T00:30:00Z" }),
          ev({ type: "FVG", confirmed_at: "2026-01-01T00:45:00Z" }), // not a marker type
        ]}
      />,
    );
    const markers = m.setMarkers.mock.calls[0][0] as { time: number; text: string }[];
    expect(markers.map((mk) => mk.text)).toEqual(["BOS", "CHOCH"]);
    expect(markers[0].time).toBe(toUtcSeconds("2026-01-01T00:15:00Z"));
    expect(markers[1].time).toBe(toUtcSeconds("2026-01-01T00:30:00Z"));
  });

  it("attaches the zones primitive exactly once", () => {
    render(<TradingChart candles={CANDLES} fvgs={[ev({ type: "FVG", levels: [1.1, 1.11] })]} />);
    expect(m.attachPrimitive).toHaveBeenCalledTimes(1);
    expect(m.attachPrimitive.mock.calls[0][0]).toBeInstanceOf(ZonesPrimitive);
  });

  it("creates price lines for liquidity levels and validated plan levels only", () => {
    const plan: TradePlan = {
      decision: "BUY",
      direction: "bullish",
      entry_levels: [1.1002],
      sl: 1.099,
      tp: 1.103,
      rr: 2.4,
      lot_size: 0.08,
      confluence_score: 0,
      reasons: [],
      warnings: [],
    };
    render(
      <TradingChart
        candles={CANDLES}
        liquidity={[ev({ type: "LIQUIDITY", level: 1.105, details: { kind: "equal_high" } })]}
        plan={plan}
      />,
    );
    const lines = (m.createPriceLine.mock.calls as unknown[][]).map(
      (c) => c[0] as { price: number; title: string },
    );
    expect(lines.map((l) => l.title)).toEqual(["BSL (EQH)", "Entry", "SL", "TP"]);
    expect(lines[1].price).toBe(1.1002);
    expect(lines[2].price).toBe(1.099);
    expect(lines[3].price).toBe(1.103);
  });

  it("removes previous price lines when the plan changes", async () => {
    const plan = (sl: number): TradePlan => ({
      decision: "BUY",
      direction: "bullish",
      entry_levels: [1.1],
      sl,
      tp: 1.11,
      rr: 1,
      lot_size: 0.1,
      confluence_score: 0,
      reasons: [],
      warnings: [],
    });
    const { rerender } = render(<TradingChart candles={CANDLES} plan={plan(1.099)} />);
    m.removePriceLine.mockClear();
    rerender(<TradingChart candles={CANDLES} plan={plan(1.098)} />);
    await waitFor(() => expect(m.removePriceLine).toHaveBeenCalledTimes(3));
    const recreated = (m.createPriceLine.mock.calls as unknown[][])
      .slice(-3)
      .map((c) => (c[0] as { price: number }).price);
    expect(recreated).toContain(1.098);
    expect(recreated).not.toContain(1.099);
  });

  it("renders no synthetic data for an empty series", () => {
    render(<TradingChart candles={[]} />);
    expect(m.setData).toHaveBeenCalledWith([]);
    expect(m.setMarkers).toHaveBeenCalledWith([]);
  });

  it("fits content once on first data, preserving user pan afterwards", () => {
    const { rerender } = render(<TradingChart candles={CANDLES} />);
    rerender(<TradingChart candles={[...CANDLES, candlePoint(5)]} />);
    expect(m.fitContent).toHaveBeenCalledTimes(1);
  });
});

describe("ZonesPrimitive", () => {
  function fakeAttached() {
    const chart = { timeScale: () => ({ timeToCoordinate: () => 100 }) } as never;
    const series = { priceToCoordinate: (p: number) => (p > 1.05 ? 20 : 40) } as never;
    const requestUpdate = vi.fn();
    const primitive = new ZonesPrimitive([]);
    primitive.attached({ chart, series, requestUpdate } as never);
    return { primitive, requestUpdate };
  }

  function fakeTarget() {
    const fillRect = vi.fn();
    const strokeRect = vi.fn();
    const target = {
      useBitmapCoordinateSpace: (cb: (scope: unknown) => void) =>
        cb({
          context: { fillRect, strokeRect, fillStyle: "", strokeStyle: "", lineWidth: 1 },
          horizontalPixelRatio: 1,
          verticalPixelRatio: 1,
        }),
    };
    return { target: target as never, fillRect, strokeRect };
  }

  it("requests a repaint when zones change", () => {
    const { primitive, requestUpdate } = fakeAttached();
    primitive.setZones([{ from: 1, to: 2, top: 1.11, bottom: 1.1, color: "#fff", label: "FVG" }]);
    expect(requestUpdate).toHaveBeenCalledTimes(1);
  });

  it("draws a rectangle per zone using live chart coordinates", () => {
    const { primitive } = fakeAttached();
    primitive.setZones([
      { from: 1, to: 2, top: 1.11, bottom: 1.1, color: "#fff", label: "FVG" },
      { from: 3, to: 4, top: 1.05, bottom: 1.0, color: "#000", label: "OB" },
    ]);
    const { target, fillRect } = fakeTarget();
    const renderer = primitive.paneViews()[0].renderer()!;
    renderer.draw(target);
    expect(fillRect).toHaveBeenCalledTimes(2);
  });

  it("skips zones whose coordinates are unresolvable (off-screen/missing)", () => {
    const { primitive } = fakeAttached();
    primitive.setZones([{ from: 1, to: 2, top: 1.11, bottom: 1.1, color: "#fff", label: "FVG" }]);
    const fillRect = vi.fn();
    const target = {
      useBitmapCoordinateSpace: (cb: (scope: unknown) => void) =>
        cb({
          context: { fillRect, strokeRect: vi.fn(), fillStyle: "", strokeStyle: "", lineWidth: 1 },
          horizontalPixelRatio: 1,
          verticalPixelRatio: 1,
        }),
    } as never;
    // Make timeToCoordinate fail → nothing drawn, nothing approximated.
    const chart = { timeScale: () => ({ timeToCoordinate: () => null }) } as never;
    const series = { priceToCoordinate: () => 20 } as never;
    const prim = new ZonesPrimitive([{ from: 1, to: 2, top: 1.11, bottom: 1.1, color: "#fff", label: "FVG" }]);
    prim.attached({ chart, series, requestUpdate: vi.fn() } as never);
    prim.paneViews()[0].renderer()!.draw(target);
    expect(fillRect).not.toHaveBeenCalled();
  });

  it("draws nothing when no zones are set", () => {
    const { primitive } = fakeAttached();
    const { target, fillRect } = fakeTarget();
    const renderer = primitive.paneViews()[0].renderer()!;
    renderer.draw(target);
    expect(fillRect).not.toHaveBeenCalled();
  });
});
