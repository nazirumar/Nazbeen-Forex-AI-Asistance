/**
 * Chart data conversion tests (Phase 11D §4).
 *
 * These are the alignment-critical guarantees: markers must sit on the exact
 * confirmation candle, zones must carry exactly the backend's price band,
 * and anything unparseable must be dropped rather than invented.
 */

import { describe, expect, it } from "vitest";
import {
  buildLiquidityLines,
  buildMarkers,
  buildZones,
  planLevels,
  toChartCandles,
  toUtcSeconds,
} from "@/lib/chart-data";
import type { CandlePoint, StructureEvent } from "@/lib/types";
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
