/**
 * Pure data → chart conversions (Phase 11D).
 *
 * These functions are the single place where backend payloads become visual
 * primitives. They are deliberately side-effect free and unit-tested, because
 * **overlay alignment** is the phase's hardest correctness requirement:
 *
 * - every marker/zone timestamp is parsed from the exact ISO-8601 UTC string
 *   the backend derived from a real candle (or from the confirmation bar) —
 *   nothing is re-derived, guessed or rounded to "look right";
 * - anything that cannot be parsed or has no explicit price band is dropped,
 *   never invented;
 * - chart series data is normalized (sorted, de-duplicated) because
 *   Lightweight Charts throws on out-of-order/duplicate points — input order
 *   is never assumed.
 */

import type {
  CandlePoint,
  StructureEvent,
} from "./types";
import type { Time, UTCTimestamp } from "lightweight-charts";

/* ------------------------------------------------------------- candle data - */

export interface ChartCandle {
  time: UTCTimestamp;
  open: number;
  high: number;
  low: number;
  close: number;
}

/** ISO-8601 → unix seconds; null when unparseable (caller must drop it). */
export function toUtcSeconds(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return null;
  return Math.floor(ms / 1000);
}

/**
 * Normalize backend candles for Lightweight Charts: parse times, drop rows
 * with invalid numbers/times, sort ascending and keep one bar per timestamp.
 */
export function toChartCandles(candles: CandlePoint[]): ChartCandle[] {
  const byTime = new Map<number, ChartCandle>();
  for (const c of candles) {
    const t = toUtcSeconds(c.time);
    if (t === null) continue;
    if (![c.open, c.high, c.low, c.close].every((n) => typeof n === "number" && Number.isFinite(n))) {
      continue;
    }
    byTime.set(t, { time: t as UTCTimestamp, open: c.open, high: c.high, low: c.low, close: c.close });
  }
  return [...byTime.values()].sort((a, b) => a.time - b.time);
}

/* ----------------------------------------------------------------- markers - */

export interface ChartMarker {
  time: UTCTimestamp;
  position: "aboveBar" | "belowBar";
  shape: "arrowUp" | "arrowDown";
  color: string;
  text: string;
}

const BULL_COLOR = "#26a69a";
const BEAR_COLOR = "#ef5350";

const MARKER_TYPES = new Set(["BOS", "CHOCH", "MSS"]);

/**
 * Structure break events → series markers.
 *
 * The marker is anchored to `confirmed_at` (the bar at which the break became
 * knowable — never the formation bar, per audit M-05/CRIT-02), falling back to
 * `end_time`. Events without a parseable anchor or an explicit direction are
 * skipped rather than guessed.
 */
export function buildMarkers(events: StructureEvent[]): ChartMarker[] {
  const markers: ChartMarker[] = [];
  for (const e of events) {
    if (!MARKER_TYPES.has(e.type)) continue;
    if (e.direction !== "bullish" && e.direction !== "bearish") continue;
    const anchor = toUtcSeconds(e.confirmed_at ?? e.end_time);
    if (anchor === null) continue;
    const bullish = e.direction === "bullish";
    markers.push({
      time: anchor as UTCTimestamp,
      position: bullish ? "belowBar" : "aboveBar",
      shape: bullish ? "arrowUp" : "arrowDown",
      color: bullish ? BULL_COLOR : BEAR_COLOR,
      text: e.type,
    });
  }
  // Lightweight Charts requires markers in chronological order.
  return markers.sort((a, b) => a.time - b.time);
}

/* ------------------------------------------------------------------ zones - */

export interface ChartZone {
  /** Anchor: first candle time of the detector's span (unix seconds). */
  from: number;
  /**
   * Right edge (unix seconds). Zone rectangles are anchored at the detector's
   * own candle time and rendered through the last candle (standard chart
   * convention for a still-valid price band) — the *price* band itself is
   * exactly the backend's [bottom, top].
   */
  to: number;
  top: number;
  bottom: number;
  color: string;
  label: string;
}

const FVG_BULL = "rgba(38, 166, 154, 0.16)";
const FVG_BEAR = "rgba(239, 83, 80, 0.16)";
const OB_BULL = "rgba(41, 98, 255, 0.14)";
const OB_BEAR = "rgba(255, 143, 0, 0.14)";

function zoneFromEvent(
  e: StructureEvent,
  lastCandleSec: number | null,
  colorBull: string,
  colorBear: string,
  label: string,
): ChartZone | null {
  // Anchor at confirmation (the gap/OB was only knowable then) — fallback to
  // formation/first span time when the detector only provides one.
  const anchor = toUtcSeconds(e.confirmed_at ?? e.start_time ?? e.formation_time ?? e.time);
  if (anchor === null) return null;
  if (e.levels.length < 2 && (e.level === null || e.level === undefined)) return null;
  const [a, b] = e.levels.length >= 2 ? e.levels : [e.level as number, e.level as number];
  if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
  const top = Math.max(a, b);
  const bottom = Math.min(a, b);
  if (top === bottom) return null; // zero-height band carries no information
  const to = lastCandleSec !== null && lastCandleSec > anchor ? lastCandleSec : anchor;
  const bull = e.direction === "bullish";
  return {
    from: anchor,
    to,
    top,
    bottom,
    color: bull ? colorBull : colorBear,
    label,
  };
}

/** FVG + order-block events → drawable zones, anchored to real candle times. */
export function buildZones(
  fvgs: StructureEvent[],
  orderBlocks: StructureEvent[],
  lastCandle: CandlePoint | null,
): ChartZone[] {
  const lastSec = lastCandle ? toUtcSeconds(lastCandle.time) : null;
  const out: ChartZone[] = [];
  for (const f of fvgs) {
    const z = zoneFromEvent(f, lastSec, FVG_BULL, FVG_BEAR, "FVG");
    if (z) out.push(z);
  }
  for (const o of orderBlocks) {
    const z = zoneFromEvent(o, lastSec, OB_BULL, OB_BEAR, "OB");
    if (z) out.push(z);
  }
  return out;
}

/* ------------------------------------------------------- horizontal levels - */

export interface LevelLine {
  price: number;
  title: string;
  color: string;
  lineStyle: "dashed" | "solid";
}

/**
 * Liquidity events → horizontal lines. `equal_high` (buy-side liquidity) and
 * `equal_low` (sell-side) come straight from the detector's `details.kind`;
 * unknown kinds still render under a neutral title instead of being relabeled.
 */
export function buildLiquidityLines(liquidity: StructureEvent[]): LevelLine[] {
  const out: LevelLine[] = [];
  for (const l of liquidity) {
    if (typeof l.level !== "number" || !Number.isFinite(l.level)) continue;
    const kind = typeof l.details?.kind === "string" ? l.details.kind : "";
    const title = kind === "equal_high" ? "BSL (EQH)" : kind === "equal_low" ? "SSL (EQL)" : "Liquidity";
    out.push({
      price: l.level,
      title,
      color: "#f0b90b",
      lineStyle: "dashed",
    });
  }
  return out;
}

/* --------------------------------------------------------- validated plan - */

export interface PlanLevels {
  entry: number | null;
  sl: number | null;
  tp: number | null;
}

/**
 * Trade-plan levels → chart lines. Only values the backend actually computed
 * are returned; missing numbers stay null so the UI can omit the line instead
 * of drawing an invented level.
 */
export function planLevels(
  plan: { entry_levels?: number[]; sl?: number | null; tp?: number | null } | null,
): PlanLevels {
  if (!plan) return { entry: null, sl: null, tp: null };
  const first = plan.entry_levels && plan.entry_levels.length ? plan.entry_levels[0] : null;
  const num = (v: number | null | undefined): number | null =>
    typeof v === "number" && Number.isFinite(v) ? v : null;
  return { entry: num(first), sl: num(plan.sl), tp: num(plan.tp) };
}

/** Time type re-export so consumers don't import from the chart library. */
export type ChartTime = Time;
