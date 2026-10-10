/** Display formatting helpers (Phase 11D) — pure functions, unit-tested. */

import type { Timeframe } from "./types";

/** ISO-8601 (UTC) → "2026-10-09 21:04" — always rendered as UTC. */
export function formatUtc(iso: string | null | undefined): string {
  if (!iso) return "—";
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return "—";
  const d = new Date(ms);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())} ` +
    `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`;
}

/** Bar age in seconds → human label: "just now" / "45s" / "12m" / "3h". */
export function formatAge(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds) || seconds < 0) {
    return "unknown";
  }
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 86400)}d`;
}

/** FX price → 5 decimals (pipette precision), tolerant of nullish input. */
export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value.toFixed(5);
}

/** Ratio-style numbers (R:R, lots) → 2 decimals. */
export function formatRatio(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value.toFixed(2);
}

/** Raw chart timestamp shown in the crosshair-style labels. */
export function formatTimeframe(tf: Timeframe | string): string {
  return tf;
}
