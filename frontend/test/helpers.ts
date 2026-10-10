/** Shared test helpers (Phase 11D). */

import { vi } from "vitest";

/** JSON fetch response with realistic headers/status. */
export function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Replace global fetch with a vi mock (restores between tests). */
export function stubFetch(): ReturnType<typeof vi.fn> {
  const fn = vi.fn();
  vi.stubGlobal("fetch", fn);
  return fn;
}

/** fetch mock resolving a single queued response (per call). */
export function fetchQueue(responses: (Response | Error)[]): ReturnType<typeof vi.fn> {
  const fn = vi.fn();
  let i = 0;
  fn.mockImplementation(async () => {
    const r = responses[Math.min(i, responses.length - 1)];
    i += 1;
    if (r instanceof Error) throw r;
    return r.clone();
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

/** Read the JSON body of call `n` of a fetch mock (defaults to first call). */
export async function callBody(fn: ReturnType<typeof vi.fn>, n = 0): Promise<unknown> {
  const init = fn.mock.calls[n]?.[1] as RequestInit | undefined;
  const body = init?.body;
  if (typeof body !== "string") return body;
  return JSON.parse(body);
}

/** All Authorization headers seen by a fetch mock. */
export function authHeaders(fn: ReturnType<typeof vi.fn>): (string | undefined)[] {
  return fn.mock.calls.map((call) => {
    const headers = (call[1] as RequestInit | undefined)?.headers as Record<string, string> | undefined;
    return headers?.["Authorization"];
  });
}

/* --------------------------------------------------------- chart fixtures -- */

export function candlePoint(i: number, base = 1.1) {
  const time = new Date(Date.UTC(2026, 0, 1, 0, i * 15)).toISOString();
  const open = base + i * 0.0004;
  return { time, open, high: open + 0.0006, low: open - 0.0006, close: open + 0.0004 };
}

export const ISO_A = "2026-01-01T00:15:00Z";
export const ISO_B = "2026-01-01T00:30:00Z";

/* ------------------------------------------------------- response fixtures */

import type {
  AnalysisResult,
  AnalysisSummary,
  CandlesResponse,
  JournalEntry,
  Mt5Status,
  StructureResponse,
  TradePlan,
} from "@/lib/types";

export function analysisResultFixture(over: Partial<AnalysisResult> = {}): AnalysisResult {
  return {
    symbol: "EURUSD",
    timeframe: "M15",
    summary: "Price swept an intraday low and displaced upward.",
    decision: "BUY",
    direction: "bullish",
    entry_levels: [1.1002],
    sl: 1.099,
    tp: 1.103,
    risk_reward: 2.4,
    evidence: [
      {
        type: "FVG",
        description: "Bullish fair-value gap at 1.0995-1.1005",
        price_level: 1.1,
        timestamp: "2026-01-01T01:00:00Z",
        confidence: 0.8,
        source: "deterministic",
      },
    ],
    disagreements: [
      {
        aspect: "bias",
        deterministic: "BULLISH",
        ai: "neutral",
        reason: "Deterministic authority applied",
        resolved: true,
      },
    ],
    mtf_conflicts: ["H1 BULLISH vs M5 BEARISH"],
    uncertainty: ["Spread not provided"],
    analysis_timestamp: "2026-01-01T02:00:00Z",
    uses_mtf_data: true,
    data_synchronized: true,
    deterministic_signals: { scenario_decision: "BUY" },
    ai_explanation: "Candle structure shows rejection of the lows.",
    model: "gemini-3.8-flash",
    errors: [],
    source: "mock",
    ...over,
  };
}

export function tradePlanFixture(over: Partial<TradePlan> = {}): TradePlan {
  return {
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
    ...over,
  };
}

export function structureFixture(over: Partial<StructureResponse> = {}): StructureResponse {
  const mtf = { H1: "BULLISH", M15: "BULLISH", M5: "BEARISH", M1: "NEUTRAL", conflicts: ["H1 BULLISH vs M5 BEARISH"] };
  return {
    symbol: "EURUSD",
    timeframe: "M15",
    count: 200,
    data_source: "mock",
    market_state: "open",
    stale: false,
    last_bar_age_sec: 30,
    threshold_sec: 1350,
    swings: [],
    events: [],
    fvgs: [],
    order_blocks: [],
    liquidity: [],
    mtf: mtf as unknown as StructureResponse["mtf"],
    ...over,
  };
}

export function candlesFixture(over: Partial<CandlesResponse> = {}): CandlesResponse {
  return {
    symbol: "EURUSD",
    timeframe: "M15",
    count: 2,
    candles: [candlePoint(0), candlePoint(1)],
    data_source: "mock",
    market_state: "open",
    stale: false,
    last_bar_age_sec: 30,
    threshold_sec: 1350,
    ...over,
  };
}

export function statusFixture(over: Partial<Mt5Status> = {}): Mt5Status {
  return {
    connected: true,
    mode: "mock",
    label: "Mock (offline testing)",
    broker: "MOCK",
    server: "MOCK",
    terminal_name: "MockTerminal",
    market_state: "open",
    ...over,
  };
}

export function journalEntryFixture(over: Partial<JournalEntry> = {}): JournalEntry {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    symbol: "EURUSD",
    timeframe: "M15",
    scenario_decision: "WAIT",
    outcome: "PENDING",
    rr: null,
    notes: "setup noted",
    created_at: "2026-10-09T10:00:00Z",
    ...over,
  };
}

export function analysisSummaryFixture(over: Partial<AnalysisSummary> = {}): AnalysisSummary {
  return {
    id: "22222222-2222-2222-2222-222222222222",
    symbol: "EURUSD",
    timeframe: "M15",
    created_at: "2026-10-09T11:00:00Z",
    decision: "WAIT",
    summary: "No confirmed setup.",
    data_source: "mock",
    screenshot_stored: true,
    ...over,
  };
}
