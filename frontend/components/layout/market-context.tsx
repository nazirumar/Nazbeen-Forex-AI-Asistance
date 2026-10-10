"use client";

/**
 * Shared symbol/timeframe selection (Phase 11D §3).
 *
 * The topbar selectors own this state; pages (chart, analysis, overview) read
 * it so a single choice drives every panel. The selection is persisted in
 * localStorage — it is a *user preference*, not market data.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Timeframe } from "@/lib/types";

const SYMBOL_KEY = "nazbeen_symbol";
const TIMEFRAME_KEY = "nazbeen_timeframe";
const DEFAULT_SYMBOL = "EURUSD";
const DEFAULT_TIMEFRAME: Timeframe = "M15";

interface MarketContextValue {
  symbol: string;
  setSymbol: (s: string) => void;
  timeframe: Timeframe;
  setTimeframe: (tf: Timeframe) => void;
}

const MarketContext = createContext<MarketContextValue | null>(null);

function readStored(key: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  try {
    return window.localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}

export function MarketProvider({ children }: { children: ReactNode }) {
  const [symbol, setSymbolState] = useState(DEFAULT_SYMBOL);
  const [timeframe, setTimeframeState] = useState<Timeframe>(DEFAULT_TIMEFRAME);

  // Hydrate after mount (localStorage is unavailable during SSR).
  useEffect(() => {
    const s = readStored(SYMBOL_KEY, DEFAULT_SYMBOL);
    if (s) setSymbolState(s);
    const tf = readStored(TIMEFRAME_KEY, DEFAULT_TIMEFRAME);
    if (tf === "M1" || tf === "M5" || tf === "M15" || tf === "H1") {
      setTimeframeState(tf);
    }
  }, []);

  const setSymbol = useCallback((s: string) => {
    setSymbolState(s);
    try {
      window.localStorage.setItem(SYMBOL_KEY, s);
    } catch {
      /* preference persistence is best-effort */
    }
  }, []);

  const setTimeframe = useCallback((tf: Timeframe) => {
    setTimeframeState(tf);
    try {
      window.localStorage.setItem(TIMEFRAME_KEY, tf);
    } catch {
      /* preference persistence is best-effort */
    }
  }, []);

  const value = useMemo(
    () => ({ symbol, setSymbol, timeframe, setTimeframe }),
    [symbol, setSymbol, timeframe, setTimeframe],
  );

  return <MarketContext.Provider value={value}>{children}</MarketContext.Provider>;
}

export function useMarket(): MarketContextValue {
  const ctx = useContext(MarketContext);
  if (!ctx) throw new Error("useMarket must be used inside <MarketProvider>");
  return ctx;
}
