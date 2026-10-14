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
  BacktestMetrics,
  BacktestRun,
  BacktestTrade,
  CandlesResponse,
  EquityPoint,
  ForwardTestObservation,
  ForwardTestRun,
  JournalEntry,
  JournalPerformance,
  Me,
  Mt5Status,
  MtfAlignment,
  SetupResult,
  SetupStep,
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

export function mtfAlignmentFixture(over: Partial<MtfAlignment> = {}): MtfAlignment {
  return {
    structure: { H1: "BULLISH", M15: "BULLISH", M5: "BEARISH", M1: "NEUTRAL" },
    aligned: false,
    dominant: null,
    conflicts: ["H1 BULLISH vs M5 BEARISH"],
    unavailable: [],
    ...over,
  };
}

export function setupStepFixture(over: Partial<SetupStep> = {}): SetupStep {
  return {
    key: "bias_confirmed",
    label: "Bias confirmed",
    status: "missing",
    time: null,
    detail: "",
    ...over,
  };
}

export function setupFixture(over: Partial<SetupResult> = {}): SetupResult {
  return {
    model: "ict_primary_setup_v1",
    direction: "bullish",
    decision: "WAIT",
    complete: false,
    stale: false,
    steps: [
      setupStepFixture({ key: "bias_confirmed", label: "Bias confirmed", status: "satisfied", time: ISO_A }),
      setupStepFixture({ key: "liquidity_swept", label: "Liquidity swept", status: "missing", detail: "no sweep of the expected side" }),
      setupStepFixture({ key: "displacement_confirmed", label: "Displacement confirmed", status: "missing" }),
      setupStepFixture({ key: "mss_confirmed", label: "MSS confirmed", status: "missing" }),
      setupStepFixture({ key: "fvg_identified", label: "FVG identified", status: "missing" }),
      setupStepFixture({ key: "retest_confirmed", label: "Retest confirmed", status: "missing" }),
      setupStepFixture({ key: "m1_confirmed", label: "M1 entry confirmed", status: "unavailable", detail: "M1 data unavailable" }),
    ],
    blocked_by: ["liquidity_swept", "displacement_confirmed", "mss_confirmed", "fvg_identified", "retest_confirmed", "m1_confirmed"],
    chain: null,
    levels: { entry: null, invalidation: null, target: null },
    context: { h1_bias: null, m5_bias: null, m5_blocks: false, h1_conflict: false },
    as_of: "2026-01-01T05:00:00Z",
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
    sweeps: [],
    displacement: [],
    rejections: [],
    engulfings: [],
    support_resistance: [],
    sr_flips: [],
    premium_discount: [],
    mtf_alignment: mtfAlignmentFixture(),
    setup: setupFixture(),
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

export function backtestRunFixture(over: Partial<BacktestRun> = {}): BacktestRun {
  return {
    id: "55555555-5555-5555-5555-555555555555",
    symbol: "EURUSD",
    timeframe: "M15",
    total_trades: 42,
    win_rate: 0.5238,
    profit_factor: 1.35,
    expectancy: 12.5,
    max_drawdown: 88.2,
    net_profit: 525.0,
    metrics: {},
    created_at: "2026-10-09T12:00:00Z",
    status: "completed",
    error: null,
    config: {},
    strategy_version: "phase11e-primary-model",
    is_walk_forward: false,
    note: null,
    data_source: "mock",
    started_at: "2026-10-09T12:00:00Z",
    finished_at: "2026-10-09T12:00:05Z",
    ...over,
  };
}

export function backtestTradeFixture(over: Partial<BacktestTrade> = {}): BacktestTrade {
  return {
    id: "66666666-6666-6666-6666-666666666666",
    index: 0,
    side: "LONG",
    entry_time: "2026-01-01T08:00:00Z",
    exit_time: "2026-01-01T09:00:00Z",
    entry: 1.1,
    exit_price: 1.102,
    sl: 1.099,
    tp: 1.102,
    lots: 1.0,
    result: "WIN",
    pnl: 200.0,
    realized_r: 2.0,
    duration_seconds: 3600,
    exit_reason: "take_profit",
    session: "london",
    weekday: "Thursday",
    ...over,
  };
}

export function backtestMetricsFixture(over: Partial<BacktestMetrics> = {}): BacktestMetrics {
  return {
    sample_size: 2,
    total_trades: 2,
    wins: 1,
    losses: 1,
    break_evens: 0,
    win_rate: 0.5,
    average_realized_r: 0.5,
    gross_profit: 200.0,
    gross_loss: 100.0,
    net_profit: 100.0,
    profit_factor: 2.0,
    expectancy: 50.0,
    max_drawdown: 100.0,
    max_drawdown_pct: 1.0,
    average_trade_duration_seconds: 3600,
    max_consecutive_wins: 1,
    max_consecutive_losses: 1,
    by_session: {},
    by_weekday: {},
    by_setup_type: {},
    assumptions: {
      spread_pips: 1,
      commission_pips: 0.5,
      slippage_pips: 0.5,
      sl_pips: 10,
      tp_pips: 20,
      initial_balance: 10000,
      risk_pct: 1,
      lots: 1,
      contract_size: 100000,
      pip_size: 0.0001,
    },
    is_walk_forward: false,
    ...over,
  };
}

export function forwardTestRunFixture(over: Partial<ForwardTestRun> = {}): ForwardTestRun {
  return {
    id: "77777777-7777-7777-7777-777777777777",
    symbol: "EURUSD",
    timeframe: "M15",
    status: "active",
    config: { symbol: "EURUSD", timeframe: "M15", count: 300 },
    strategy_version: "phase11e-primary-model",
    data_source: "mock",
    last_observed_bar: "2026-01-01T12:00:00Z",
    last_observed_at: "2026-01-01T12:00:05Z",
    observations_count: 2,
    outcomes: { PENDING: 1, WIN: 1, LOSS: 0, BE: 0 },
    error: null,
    note: "Simulated forward test (analysis-only); no orders are placed.",
    simulated: true,
    created_at: "2026-01-01T11:00:00Z",
    started_at: "2026-01-01T11:00:00Z",
    stopped_at: null,
    ...over,
  };
}

export function forwardTestObservationFixture(
  over: Partial<ForwardTestObservation> = {},
): ForwardTestObservation {
  return {
    id: "88888888-8888-8888-8888-888888888888",
    run_id: "77777777-7777-7777-7777-777777777777",
    bar_time: "2026-01-01T12:00:00Z",
    decision: "BUY",
    reason: "Deterministic BUY on closed window; simulated entry requires no confirmation from AI.",
    entry: 1.1,
    sl: 1.099,
    tp: 1.102,
    rr: 2.0,
    snapshot: { bias: { M15: "BULLISH" }, conflicts: [], price: 1.1, simulated: true },
    data_source: "mock",
    simulated: true,
    outcome: "WIN",
    outcome_price: 1.102,
    outcome_r: 2.0,
    resolved_at: "2026-01-01T12:15:00Z",
    created_at: "2026-01-01T12:00:05Z",
    ...over,
  };
}

export function equityPointsFixture(): EquityPoint[] {
  return [
    { time: "2026-01-01T08:00:00Z", equity: 10000, balance: 10000, drawdown: 0 },
    { time: "2026-01-01T09:00:00Z", equity: 10200, balance: 10200, drawdown: 0 },
    { time: "2026-01-01T10:00:00Z", equity: 10100, balance: 10100, drawdown: 100 },
  ];
}

export function journalPerformanceFixture(over: Partial<JournalPerformance> = {}): JournalPerformance {
  return {
    total_entries: 6,
    outcomes: { WIN: 3, LOSS: 2, BE: 1, PENDING: 0 },
    closed: 6,
    open: 0,
    win_rate: 0.6,
    average_rr: 2.1,
    total_pnl: 340.0,
    expectancy: 56.67,
    profit_factor: 1.8,
    max_drawdown: 120.0,
    pnl_sample: 6,
    rr_sample: 4,
    note: "Computed only from recorded journal fields. null means the data required for that statistic was not recorded.",
    ...over,
  };
}

export function meFixture(over: Partial<Me> = {}): Me {
  return {
    id: 7,
    username: "naz",
    email: "naz@example.com",
    date_joined: "2026-10-01T08:30:00Z",
    profile: { display_timezone: "UTC" },
    ...over,
  };
}
