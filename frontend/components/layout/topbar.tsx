"use client";

/**
 * Top navigation (Phase 11D §3).
 *
 * Contains: mobile menu button, symbol selector, timeframe selector, MT5
 * connection indicator, market-data freshness indicator, UTC clock and the
 * user profile menu. Status data is polled from the real backend endpoints —
 * when a poll fails the indicators honestly show "Unknown" instead of a
 * reassuring default.
 */

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatAge, formatUtc } from "@/lib/format";
import type { CandlesResponse, Mt5Status, Timeframe } from "@/lib/types";
import { TIMEFRAMES } from "@/lib/types";
import { useMarket } from "./market-context";

const POLL_MS = 30_000;

async function fetchStatus(): Promise<Mt5Status | null> {
  try {
    return await api<Mt5Status>("/api/mt5/status/");
  } catch {
    return null;
  }
}

async function fetchFreshness(symbol: string, timeframe: Timeframe) {
  try {
    return await api<CandlesResponse>(
      `/api/mt5/candles/?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}&count=1`,
    );
  } catch {
    return null;
  }
}

function StatusDot({ tone }: { tone: "green" | "red" | "gray" | "amber" }) {
  const color =
    tone === "green"
      ? "bg-emerald-400"
      : tone === "red"
        ? "bg-red-400"
        : tone === "amber"
          ? "bg-amber-400"
          : "bg-zinc-500";
  return <span className={`inline-block h-2 w-2 shrink-0 rounded-full ${color}`} aria-hidden />;
}

export function Topbar({ onOpenSidebar }: { onOpenSidebar: () => void }) {
  const router = useRouter();
  const { user, logout } = useAuth();
  const { symbol, setSymbol, timeframe, setTimeframe } = useMarket();

  const [status, setStatus] = useState<Mt5Status | null>(null);
  const [freshness, setFreshness] = useState<CandlesResponse | null>(null);
  const [statusError, setStatusError] = useState(false);
  const [now, setNow] = useState<string>("");
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const refresh = useCallback(async () => {
    const [s, f] = await Promise.all([fetchStatus(), fetchFreshness(symbol, timeframe)]);
    setStatus(s);
    setFreshness(f);
    setStatusError(s === null);
  }, [symbol, timeframe]);

  useEffect(() => {
    void refresh();
    const poll = setInterval(() => void refresh(), POLL_MS);
    return () => clearInterval(poll);
  }, [refresh]);

  useEffect(() => {
    const tick = () => setNow(formatUtc(new Date().toISOString()));
    tick();
    const t = setInterval(tick, 30_000);
    return () => clearInterval(t);
  }, []);

  // Close the profile menu on outside click / Escape.
  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  const connected = status?.connected ?? false;
  const modeLabel = status?.mode === "mt5" ? "MT5" : status?.mode === "mock" ? "Mock" : "—";
  const closed = freshness?.market_state === "closed" || status?.market_state === "closed";
  const ageSec = freshness?.last_bar_age_sec ?? null;
  const stale = freshness?.stale ?? false;
  const freshnessTone = freshness === null ? "gray" : closed ? "gray" : stale ? "amber" : "green";
  const freshnessText =
    freshness === null
      ? "Freshness unknown"
      : `${formatAge(ageSec)}${closed ? " · market closed" : ""}${stale ? " · stale" : ""}`;

  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b border-zinc-800 bg-[#0c1118] px-3 sm:gap-3 sm:px-4">
      {/* Mobile: open drawer */}
      <button
        type="button"
        onClick={onOpenSidebar}
        aria-label="Open navigation menu"
        data-testid="menu-toggle"
        className="rounded-lg p-2 text-zinc-400 transition hover:bg-zinc-800 hover:text-zinc-100 lg:hidden"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5" aria-hidden>
          <path d="M4 7h16M4 12h16M4 17h16" />
        </svg>
      </button>

      {/* Symbol selector */}
      <label className="flex items-center gap-1.5">
        <span className="sr-only">Symbol</span>
        <select
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          data-testid="symbol-select"
          className="rounded-lg border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm font-semibold text-zinc-100 outline-none transition focus:border-cyan-600"
        >
          {[symbol, "EURUSD", "GBPUSD"]
            .filter((s, i, arr) => arr.indexOf(s) === i)
            .map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
        </select>
      </label>

      {/* Timeframe selector */}
      <div
        className="flex items-center rounded-lg border border-zinc-700 bg-zinc-900 p-0.5"
        role="group"
        aria-label="Timeframe"
        data-testid="timeframe-select"
      >
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf}
            type="button"
            onClick={() => setTimeframe(tf)}
            aria-pressed={timeframe === tf}
            className={`rounded-md px-2 py-1 text-xs font-semibold transition ${
              timeframe === tf
                ? "bg-cyan-500/20 text-cyan-300"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            {tf}
          </button>
        ))}
      </div>

      <div className="ml-auto flex items-center gap-2 sm:gap-3">
        {/* MT5 connection indicator */}
        <div
          className="hidden items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900/60 px-2 py-1 text-xs text-zinc-300 sm:flex"
          data-testid="connection-indicator"
          title={status?.error ?? `${status?.broker ?? modeLabel} · ${status?.server ?? "—"}`}
        >
          <StatusDot tone={status === null ? "gray" : connected ? "green" : "red"} />
          {status === null ? (
            <span className="text-zinc-500">Connection unknown</span>
          ) : connected ? (
            <span>
              {modeLabel} <span className="text-zinc-500">connected</span>
            </span>
          ) : (
            <span className="text-red-300">Disconnected</span>
          )}
        </div>

        {/* Market-data freshness indicator */}
        <div
          className="hidden items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900/60 px-2 py-1 text-xs text-zinc-300 md:flex"
          data-testid="freshness-indicator"
        >
          <StatusDot tone={freshnessTone} />
          <span>{freshnessText}</span>
        </div>

        <span className="hidden font-mono text-xs text-zinc-500 lg:inline" data-testid="utc-clock">
          {now} UTC
        </span>

        {/* Profile menu */}
        <div className="relative" ref={menuRef}>
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            data-testid="profile-menu-toggle"
            className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-cyan-600 to-blue-800 text-xs font-bold text-white"
          >
            {(user?.username ?? "?").slice(0, 1).toUpperCase()}
          </button>
          {menuOpen && (
            <div
              role="menu"
              data-testid="profile-menu"
              className="absolute right-0 top-10 z-50 w-56 rounded-xl border border-zinc-700 bg-zinc-900 p-3 shadow-2xl"
            >
              <p className="truncate text-sm font-semibold text-zinc-100">{user?.username ?? "—"}</p>
              <p className="truncate text-xs text-zinc-500">{user?.email || "No email set"}</p>
              <p className="mt-1 text-xs text-zinc-500">
                Timezone: {user?.profile.display_timezone ?? "—"} UTC
              </p>
              <p className="mt-0.5 text-[10px] uppercase tracking-wide text-zinc-600">
                Analysis-only — no trade execution
              </p>
              <button
                type="button"
                role="menuitem"
                data-testid="logout-button"
                onClick={async () => {
                  setMenuOpen(false);
                  await logout();
                  router.replace("/login");
                }}
                className="mt-3 w-full rounded-lg border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:bg-zinc-800"
              >
                Log out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
