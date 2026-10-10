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
