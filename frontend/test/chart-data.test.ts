/**
 * Chart data conversion tests (Phase 11D §4).
 *
 * These are the alignment-critical guarantees: markers must sit on the exact
 * confirmation candle, zones must carry exactly the backend's price band,
 * and anything unparseable must be dropped rather than invented.
 */

import { describe, expect, it } from "vitest";
import {
  buildDisplacementMarkers,
  buildLiquidityLines,
  buildMarkers,
  buildPremiumDiscountLine,
  buildSetupLevels,
  buildSupportResistanceLines,
  buildSweepMarkers,
  buildZones,
  deriveSetupChecklist,
  planLevels,
  toChartCandles,
  toUtcSeconds,
} from "@/lib/chart-data";
import type { CandlePoint, SetupResult, SetupStep, StructureEvent } from "@/lib/types";
import { candlePoint } from "./helpers";

function event(partial: Partial<StructureEvent>): StructureEvent {
  return {
    type: "BOS",
    direction: "bullish",
    index: 1,
    level: 1.1,
    levels: [1.099, 1.101],
    details: {},
    ...partial,
  } as StructureEvent;
}

describe("toUtcSeconds", () => {
  it("parses ISO-8601 UTC strings to unix seconds", () => {
    expect(toUtcSeconds("2026-01-01T00:15:00Z")).toBe(Date.UTC(2026, 0, 1, 0, 15) / 1000);
    expect(toUtcSeconds("2026-01-01T00:15:00+00:00")).toBe(Date.UTC(2026, 0, 1, 0, 15) / 1000);
  });

  it("returns null for missing or unparseable values", () => {
    expect(toUtcSeconds(null)).toBeNull();
    expect(toUtcSeconds(undefined)).toBeNull();
    expect(toUtcSeconds("not-a-date")).toBeNull();
  });
});

describe("toChartCandles", () => {
  it("sorts ascending, de-duplicates and drops invalid rows", () => {
    const candles: CandlePoint[] = [
      candlePoint(2),
      candlePoint(0),
      candlePoint(1),
      candlePoint(2), // duplicate timestamp — last write wins
      { ...candlePoint(3), time: "garbage" }, // unparseable time → dropped
      { ...candlePoint(4), close: Number.NaN }, // non-finite number → dropped
    ];
    const out = toChartCandles(candles);
    expect(out).toHaveLength(3);
    expect(out.map((c) => c.time)).toEqual([...out.map((c) => c.time)].sort((a, b) => a - b));
    // duplicated point kept exactly once
    expect(out.filter((c) => c.time === toUtcSeconds(candlePoint(2).time))).toHaveLength(1);
  });

  it("produces numeric chart times matching the backend timestamps", () => {
    const [first] = toChartCandles([candlePoint(0)]);
    expect(first.time).toBe(toUtcSeconds(candlePoint(0).time));
  });
});

describe("buildMarkers", () => {
  it("anchors BOS/CHOCH/MSS markers to the confirmation bar, not the formation bar", () => {
    const markers = buildMarkers([
      event({
        type: "BOS",
        direction: "bullish",
        formation_time: "2026-01-01T00:00:00Z",
        confirmed_at: "2026-01-01T00:45:00Z",
      }),
    ]);
    expect(markers).toHaveLength(1);
    expect(markers[0].time).toBe(toUtcSeconds("2026-01-01T00:45:00Z"));
    expect(markers[0].time).not.toBe(toUtcSeconds("2026-01-01T00:00:00Z"));
    expect(markers[0].text).toBe("BOS");
    expect(markers[0].shape).toBe("arrowUp");
    expect(markers[0].position).toBe("belowBar");
  });

  it("renders bearish breaks above the bar with a down arrow", () => {
    const [m] = buildMarkers([
      event({ type: "CHOCH", direction: "bearish", confirmed_at: "2026-01-01T01:00:00Z" }),
    ]);
    expect(m.shape).toBe("arrowDown");
    expect(m.position).toBe("aboveBar");
  });

  it("falls back to end_time and drops events without any anchor", () => {
    const out = buildMarkers([
      event({ type: "MSS", end_time: "2026-01-01T02:00:00Z", confirmed_at: undefined }),
      event({ type: "MSS", confirmed_at: undefined, end_time: undefined }),
    ]);
    expect(out).toHaveLength(1);
    expect(out[0].time).toBe(toUtcSeconds("2026-01-01T02:00:00Z"));
  });

  it("never guesses a direction: neutral/unspecified events are skipped", () => {
    expect(
      buildMarkers([
        event({ direction: "neutral", confirmed_at: "2026-01-01T00:30:00Z" }),
        event({ direction: null, confirmed_at: "2026-01-01T00:30:00Z" }),
      ]),
    ).toHaveLength(0);
  });

  it("returns markers in chronological order regardless of input order", () => {
    const markers = buildMarkers([
      event({ type: "BOS", confirmed_at: "2026-01-01T03:00:00Z" }),
      event({ type: "CHOCH", confirmed_at: "2026-01-01T01:00:00Z" }),
      event({ type: "MSS", confirmed_at: "2026-01-01T02:00:00Z" }),
    ]);
    expect(markers.map((m) => m.text)).toEqual(["CHOCH", "MSS", "BOS"]);
  });
});

describe("buildZones", () => {
  const lastCandle = candlePoint(9);

  it("uses exactly the backend price band and anchors at confirmation time", () => {
    const [zone] = buildZones(
      [
        event({
          type: "FVG",
          direction: "bullish",
          levels: [1.0995, 1.1005],
          confirmed_at: "2026-01-01T00:30:00Z",
        }),
      ],
      [],
      lastCandle,
    );
    expect(zone.top).toBe(1.1005);
    expect(zone.bottom).toBe(1.0995);
    expect(zone.from).toBe(toUtcSeconds("2026-01-01T00:30:00Z"));
    expect(zone.label).toBe("FVG");
    // right edge reaches the latest candle (band remains visible)
    expect(zone.to).toBe(toUtcSeconds(lastCandle.time));
  });

  it("skips zones without a usable price band or timestamp (never invents)", () => {
    const zones = buildZones(
      [
        event({ levels: [], level: null, confirmed_at: "2026-01-01T00:30:00Z" }),
        event({ levels: [1.1, 1.1], confirmed_at: "2026-01-01T00:30:00Z" }), // zero height
        event({ levels: [1.1, 1.2], confirmed_at: undefined, start_time: undefined, formation_time: undefined, time: undefined }),
      ],
      [],
      null,
    );
    expect(zones).toHaveLength(0);
  });

  it("labels order blocks separately from FVGs", () => {
    const zones = buildZones(
      [],
      [event({ type: "ORDERBLOCK", levels: [1.098, 1.099], confirmed_at: "2026-01-01T01:00:00Z" })],
      lastCandle,
    );
    expect(zones).toHaveLength(1);
    expect(zones[0].label).toBe("OB");
  });
});

describe("buildLiquidityLines", () => {
  it("titles lines by the detector's own kind and skips missing levels", () => {
    const lines = buildLiquidityLines([
      event({ type: "LIQUIDITY", level: 1.105, details: { kind: "equal_high" } }),
      event({ type: "LIQUIDITY", level: 1.09, details: { kind: "equal_low" } }),
      event({ type: "LIQUIDITY", level: null, details: {} }),
    ]);
    expect(lines.map((l) => l.title)).toEqual(["BSL (EQH)", "SSL (EQL)"]);
    expect(lines[0].price).toBe(1.105);
    expect(lines[0].lineStyle).toBe("dashed");
  });
});

describe("planLevels", () => {
  it("passes through only numbers the backend actually computed", () => {
    expect(planLevels({ entry_levels: [1.1002], sl: 1.099, tp: 1.102 })).toEqual({
      entry: 1.1002,
      sl: 1.099,
      tp: 1.102,
    });
    expect(planLevels({ entry_levels: [], sl: null, tp: null })).toEqual({
      entry: null,
      sl: null,
      tp: null,
    });
    expect(planLevels(null)).toEqual({ entry: null, sl: null, tp: null });
  });
});

/* ------------------------------------------------ Phase 11E overlays ------ */

function setupResult(over: Partial<SetupResult> = {}): SetupResult {
  return {
    model: "ict_primary_setup_v1",
    direction: "bullish",
    decision: "BUY",
    complete: true,
    stale: false,
    steps: [],
    blocked_by: [],
    chain: null,
    levels: { entry: 1.1005, invalidation: 1.099, target: 1.104 },
    context: { h1_bias: null, m5_bias: null, m5_blocks: false, h1_conflict: false },
    as_of: "2026-01-01T05:00:00Z",
    ...over,
  };
}

describe("buildSweepMarkers / buildDisplacementMarkers", () => {
  it("anchors sweep markers to confirmed_at and maps direction to position/shape", () => {
    const markers = buildSweepMarkers([
      event({ type: "SWEEP", direction: "bullish", confirmed_at: "2026-01-01T00:45:00Z" }),
      event({ type: "SWEEP", direction: "bearish", confirmed_at: "2026-01-01T01:00:00Z" }),
    ]);
    expect(markers).toHaveLength(2);
    expect(markers[0].time).toBe(toUtcSeconds("2026-01-01T00:45:00Z"));
    expect(markers[0].text).toBe("SWEEP");
    expect(markers[0].position).toBe("belowBar");
    expect(markers[0].shape).toBe("arrowUp");
    expect(markers[1].position).toBe("aboveBar");
    expect(markers[1].shape).toBe("arrowDown");
  });

  it("falls back to end_time then time and drops unparseable/neutral entries", () => {
    const out = buildSweepMarkers([
      event({ direction: "bullish", confirmed_at: undefined, end_time: "2026-01-01T02:00:00Z" }),
      event({ direction: "bearish", confirmed_at: undefined, end_time: undefined, time: "2026-01-01T03:00:00Z" }),
      event({ direction: "bullish", confirmed_at: undefined, end_time: undefined, time: undefined }),
      event({ direction: "neutral", confirmed_at: "2026-01-01T00:00:00Z" }),
      event({ direction: null, confirmed_at: "2026-01-01T00:00:00Z" }),
      event({ direction: "bullish", confirmed_at: "not-a-date", end_time: undefined, time: undefined }),
    ]);
    expect(out.map((mk) => mk.time)).toEqual([
      toUtcSeconds("2026-01-01T02:00:00Z"),
      toUtcSeconds("2026-01-01T03:00:00Z"),
    ]);
  });

  it("sorts chronologically regardless of input order and labels displacement DISP", () => {
    const markers = buildDisplacementMarkers([
      event({ direction: "bullish", confirmed_at: "2026-01-01T03:00:00Z" }),
      event({ direction: "bearish", confirmed_at: "2026-01-01T01:00:00Z" }),
    ]);
    expect(markers.map((mk) => mk.text)).toEqual(["DISP", "DISP"]);
    expect(markers[0].time).toBe(toUtcSeconds("2026-01-01T01:00:00Z"));
    expect(markers[0].shape).toBe("arrowDown");
  });
});

describe("buildSetupLevels", () => {
  it("returns [] for null or incomplete setups", () => {
    expect(buildSetupLevels(null)).toEqual([]);
    expect(buildSetupLevels(setupResult({ complete: false }))).toEqual([]);
  });

  it("emits Entry/SL/TP with distinct colors for a complete setup", () => {
    const lines = buildSetupLevels(setupResult());
    expect(lines.map((l) => l.title)).toEqual(["Entry", "SL", "TP"]);
    expect(lines.map((l) => l.price)).toEqual([1.1005, 1.099, 1.104]);
    expect(lines.every((l) => l.lineStyle === "dashed")).toBe(true);
    expect(new Set(lines.map((l) => l.color)).size).toBe(3);
  });

  it("drops individual null/non-finite levels rather than inventing them", () => {
    const lines = buildSetupLevels(
      setupResult({ levels: { entry: 1.1005, invalidation: null, target: Number.NaN } }),
    );
    expect(lines.map((l) => l.title)).toEqual(["Entry"]);
  });
});

describe("buildPremiumDiscountLine / buildSupportResistanceLines", () => {
  it("draws a dashed midpoint line only for finite premium/discount levels", () => {
    const lines = buildPremiumDiscountLine([
      event({ type: "PREMIUM_DISCOUNT", level: 1.1, details: { zone: "premium" } }),
      event({ type: "PREMIUM_DISCOUNT", level: null, details: {} }),
    ]);
    expect(lines).toHaveLength(1);
    expect(lines[0].title).toBe("EQ (mid)");
    expect(lines[0].price).toBe(1.1);
    expect(lines[0].lineStyle).toBe("dashed");
  });

  it("draws one dashed S/R line per finite level and drops null levels", () => {
    const lines = buildSupportResistanceLines([
      event({ type: "SUPPORT_RESISTANCE", level: 1.095 }),
      event({ type: "SUPPORT_RESISTANCE", level: 1.11 }),
      event({ type: "SUPPORT_RESISTANCE", level: null }),
    ]);
    expect(lines.map((l) => l.title)).toEqual(["S/R", "S/R"]);
    expect(lines.map((l) => l.price)).toEqual([1.095, 1.11]);
    expect(lines.every((l) => l.lineStyle === "dashed")).toBe(true);
  });
});

describe("deriveSetupChecklist", () => {
  it("returns the backend steps verbatim and [] when absent", () => {
    const steps: SetupStep[] = [
      {
        key: "bias_confirmed",
        label: "Bias confirmed",
        status: "satisfied",
        time: "2026-01-01T00:15:00Z",
        detail: "M15 structure bias BULLISH as of the sweep bar",
      },
    ];
    expect(deriveSetupChecklist(setupResult({ steps }))).toEqual(steps);
    expect(deriveSetupChecklist(setupResult({ steps: [] }))).toEqual([]);
    expect(deriveSetupChecklist(null)).toEqual([]);
  });
});
