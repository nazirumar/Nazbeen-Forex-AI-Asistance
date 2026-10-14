/** Shared API response types (Phase 11D).
 *
 * Every type mirrors a real backend response shape (see docs/API.md) — nothing
 * here invents fields the backend does not send.
 */

export type Timeframe = "M1" | "M5" | "M15" | "H1";
export const TIMEFRAMES: Timeframe[] = ["M1", "M5", "M15", "H1"];

export type Bias = "BULLISH" | "BEARISH" | "NEUTRAL";
export type Decision = "BUY" | "SELL" | "WAIT";
export type DataSource = "mock" | "mt5" | "auto";

/* ---------------------------------------------------------------- auth ---- */

export interface UserProfile {
  display_timezone: string;
  created_at?: string;
}

export interface Me {
  id: number;
  username: string;
  email: string;
  date_joined: string;
  profile: UserProfile;
}

export interface AuthResponse {
  token: string;
  user: Omit<Me, "profile"> & { profile?: UserProfile };
}

/* ----------------------------------------------------------- marketdata --- */

export interface Mt5Status {
  connected: boolean;
  mode: DataSource;
  label?: string;
  broker?: string;
  server?: string;
  terminal_name?: string;
  market_state?: "open" | "closed";
  error?: string;
}

export interface SymbolInfo {
  symbol: string;
  description?: string;
  path?: string;
}

export interface CandlePoint {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface Freshness {
  market_state: "open" | "closed";
  stale: boolean;
  last_bar_age_sec: number | null;
  threshold_sec: number;
}

export interface CandlesResponse extends Freshness {
  symbol: string;
  timeframe: string;
  count: number;
  candles: CandlePoint[];
  data_source: DataSource;
}

/* ------------------------------------------------------------ structure --- */

export type StructureEventType = "BOS" | "CHOCH" | "MSS";

export interface StructureEvent {
  type: StructureEventType | string;
  direction: "bullish" | "bearish" | "neutral" | null;
  index: number | null;
  level: number | null;
  levels: number[];
  details: Record<string, unknown>;
  start_time?: string;
  end_time?: string;
  formation_time?: string;
  confirmed_at?: string;
  /** Attached by the API for index-only events (liquidity). */
  time?: string;
}

export interface SwingLabel {
  swing: {
    type: "high" | "low";
    index: number;
    time: string;
    price: number;
    confirmed: boolean;
  };
  label: string;
}

export interface MtfView {
  H1: Bias | null;
  M15: Bias | null;
  M5: Bias | null;
  M1: Bias | null;
  /** Real disagreement strings from the backend (audit H-05). */
  conflicts: string[];
}

/** Explicit structure alignment block (Phase 11E; `mtf_structure_alignment`). */
export interface MtfAlignment {
  structure: { H1: Bias | null; M15: Bias | null; M5: Bias | null; M1: Bias | null };
  /** `true` all decisive TFs agree, `false` any disagree, `null` no evidence. */
  aligned: boolean | null;
  dominant: Bias | null;
  conflicts: string[];
  /** Timeframes without data — never reported as NEUTRAL. */
  unavailable: string[];
}

export type SetupStepStatus = "satisfied" | "missing" | "invalid" | "unavailable";

/** One checklist item of the primary trading model (`structure/setup.py`). */
export interface SetupStep {
  key: string;
  label: string;
  status: SetupStepStatus;
  time: string | null;
  detail: string;
}

export interface SetupLevels {
  entry: number | null;
  invalidation: number | null;
  target: number | null;
}

export interface SetupContext {
  h1_bias: Bias | null;
  m5_bias: Bias | null;
  m5_blocks: boolean;
  h1_conflict: boolean;
}

/** The linked real events of a complete chain (never assembled from noise). */
export interface SetupChain {
  sweep_index: number;
  sweep_time: string | null;
  displacement_index: number;
  displacement_time: string | null;
  mss_index: number;
  mss_time: string | null;
  fvg_confirmed_index: number;
  fvg_time: string | null;
  retest_time: string | null;
  m1_time: string | null;
}

/** Primary trading model result (`evaluate_primary_setup`) — the `setup` key. */
export interface SetupResult {
  model: string;
  direction: "bullish" | "bearish" | null;
  decision: Decision;
  complete: boolean;
  stale: boolean;
  steps: SetupStep[];
  blocked_by: string[];
  chain: SetupChain | null;
  levels: SetupLevels;
  context: SetupContext;
  as_of: string | null;
}

export interface StructureResponse extends Freshness {
  symbol: string;
  timeframe: string;
  count: number;
  data_source: DataSource;
  swings: SwingLabel[];
  events: StructureEvent[];
  fvgs: StructureEvent[];
  order_blocks: StructureEvent[];
  liquidity: StructureEvent[];
  mtf: MtfView;
  /* --- Phase 11E additive detector outputs (empty arrays stay empty) --- */
  sweeps: StructureEvent[];
  displacement: StructureEvent[];
  rejections: StructureEvent[];
  engulfings: StructureEvent[];
  support_resistance: StructureEvent[];
  sr_flips: StructureEvent[];
  premium_discount: StructureEvent[];
  mtf_alignment: MtfAlignment;
  setup: SetupResult;
}

/* ----------------------------------------------------------------- risk --- */

export interface TradePlan {
  decision: Decision;
  direction: string | null;
  entry_levels: number[];
  sl: number | null;
  tp: number | null;
  rr: number | null;
  lot_size: number | null;
  confluence_score: number | null;
  reasons: string[];
  warnings: string[];
}

/* ------------------------------------------------------------- analysis --- */

export interface EvidenceItem {
  type: string;
  description: string;
  price_level?: number | null;
  timestamp?: string | null;
  confidence?: number | null;
  source: "ai" | "deterministic";
}

export interface DisagreementItem {
  aspect: string;
  deterministic: unknown;
  ai: unknown;
  reason: string;
  resolved: boolean;
}

export interface AnalysisResult {
  symbol: string | null;
  timeframe: string | null;
  summary: string;
  decision: Decision;
  direction: "bullish" | "bearish" | "neutral";
  entry_levels: number[];
  sl: number | null;
  tp: number | null;
  risk_reward: number | null;
  evidence: EvidenceItem[];
  disagreements: DisagreementItem[];
  mtf_conflicts: string[];
  uncertainty: string[];
  analysis_timestamp: string;
  uses_mtf_data: boolean;
  data_synchronized: boolean;
  deterministic_signals: Record<string, unknown>;
  ai_explanation: string;
  model: string | null;
  errors: string[];
  source: string | null;
}

export interface UploadResponse {
  analysis_id?: string;
  result: AnalysisResult;
  screenshot_stored: boolean;
}

export interface AnalysisDetail {
  analysis: AnalysisResult;
}

export interface AnalysisSummary {
  id: string;
  symbol: string | null;
  timeframe: string | null;
  created_at: string;
  decision: Decision | null;
  summary: string;
  data_source: string | null;
  screenshot_stored: boolean;
}

/* -------------------------------------------------------------- journal --- */

export interface JournalEntry {
  id: string;
  symbol: string | null;
  timeframe: string | null;
  scenario_decision: string | null;
  outcome: "WIN" | "LOSS" | "BE" | "PENDING";
  rr: number | null;
  notes: string;
  created_at: string;
}

/* ------------------------------------------------------------- backtests --- */

/** A recorded backtest run (`GET /api/backtests/`, Phase 11F). */
export interface BacktestRun {
  id: string;
  symbol: string | null;
  timeframe: string | null;
  total_trades: number;
  win_rate: number | null;
  profit_factor: number | null;
  expectancy: number | null;
  max_drawdown: number | null;
  net_profit: number | null;
  metrics: Record<string, unknown>;
  created_at: string | null;
  /* --- Phase 11G execution/reporting fields (additive) --- */
  status?: "queued" | "running" | "completed" | "failed";
  error?: string | null;
  config?: Record<string, unknown>;
  strategy_version?: string;
  is_walk_forward?: boolean;
  note?: string | null;
  data_source?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface BacktestRunsResponse {
  count: number;
  runs: BacktestRun[];
}

export interface BacktestRunResponse {
  run: BacktestRun;
}

/** One simulated trade (`GET /api/backtests/runs/<id>/trades/`). */
export interface BacktestTrade {
  id: string;
  index: number;
  side: "LONG" | "SHORT";
  entry_time: string | null;
  exit_time: string | null;
  entry: number;
  exit_price: number | null;
  sl: number;
  tp: number;
  lots: number;
  result: "WIN" | "LOSS" | "BREAK_EVEN";
  pnl: number;
  realized_r: number | null;
  duration_seconds: number | null;
  exit_reason: string;
  session: string;
  weekday: string;
}

export interface BacktestTradesResponse {
  count: number;
  trades: BacktestTrade[];
}

export interface EquityPoint {
  time: string | null;
  equity: number;
  balance: number;
  drawdown: number;
}

export interface EquityResponse {
  points: EquityPoint[];
}

/** §6 metrics (`GET /api/backtests/runs/<id>/metrics/`). null = not computable. */
export interface BacktestMetrics {
  sample_size: number;
  total_trades: number;
  wins: number;
  losses: number;
  break_evens: number;
  win_rate: number | null;
  average_realized_r: number | null;
  gross_profit: number;
  gross_loss: number;
  net_profit: number;
  profit_factor: number | null;
  profit_factor_note?: string;
  expectancy: number | null;
  max_drawdown: number;
  max_drawdown_pct: number | null;
  average_trade_duration_seconds: number | null;
  max_consecutive_wins: number;
  max_consecutive_losses: number;
  by_session?: Record<string, BacktestGroupStats>;
  by_weekday?: Record<string, BacktestGroupStats>;
  by_setup_type?: Record<string, BacktestGroupStats>;
  assumptions?: Record<string, number | null>;
  is_walk_forward?: boolean;
}

export interface BacktestGroupStats {
  trades: number;
  wins: number;
  losses: number;
  win_rate: number | null;
  net_profit: number;
}

export interface BacktestMetricsResponse {
  metrics: BacktestMetrics;
  status: string;
}

/* ----------------------------------------------------------- forwardtests --- */

export type ForwardTestStatus = "active" | "stopped" | "failed";
export type ForwardDecision = "BUY" | "SELL" | "WAIT";
export type ForwardOutcome = "PENDING" | "WIN" | "LOSS" | "BE";

/** A simulated forward test (`GET /api/forwardtests/runs/`, Phase 11G §9). */
export interface ForwardTestRun {
  id: string;
  symbol: string;
  timeframe: string;
  status: ForwardTestStatus;
  config: Record<string, unknown>;
  strategy_version?: string;
  data_source?: string | null;
  last_observed_bar?: string | null;
  last_observed_at?: string | null;
  observations_count: number;
  outcomes: Record<string, number>;
  error?: string | null;
  note?: string | null;
  /** Forward-test results are always simulated (never real order outcomes). */
  simulated: boolean;
  created_at: string | null;
  started_at?: string | null;
  stopped_at?: string | null;
}

export interface ForwardTestRunsResponse {
  count: number;
  runs: ForwardTestRun[];
}

export interface ForwardTestRunResponse {
  run: ForwardTestRun;
}

/** One recorded decision (`GET /api/forwardtests/runs/<id>/observations/`). */
export interface ForwardTestObservation {
  id: string;
  run_id: string;
  bar_time: string | null;
  decision: ForwardDecision;
  reason: string;
  entry: number | null;
  sl: number | null;
  tp: number | null;
  rr: number | null;
  snapshot: Record<string, unknown>;
  data_source?: string | null;
  simulated: boolean;
  outcome: ForwardOutcome;
  outcome_price: number | null;
  outcome_r: number | null;
  resolved_at: string | null;
  created_at: string | null;
}

export interface ForwardTestObservationsResponse {
  count: number;
  observations: ForwardTestObservation[];
}

/* ------------------------------------------------------------- analytics --- */

/** Recorded-only journal performance (`GET /api/journal/performance/`). */
export interface JournalPerformance {
  total_entries: number;
  outcomes: Record<string, number>;
  closed: number;
  open: number;
  win_rate: number | null;
  average_rr: number | null;
  total_pnl: number | null;
  expectancy: number | null;
  profit_factor: number | null;
  max_drawdown: number | null;
  pnl_sample: number;
  rr_sample: number;
  note: string;
}
