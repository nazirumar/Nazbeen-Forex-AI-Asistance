"""Structured analysis schema definitions and validators."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal, List, Dict, Any, Optional
import base64

# ---------------------------------------------------------------------------
# LLM claim schemas (Phase 11B)
#
# These deliberately constrain what a vision/reasoning model is ALLOWED to
# claim. Note the absence of a `decision` field: the LLM never decides
# BUY/SELL/WAIT. Decisions belong to the deterministic engine and the risk
# service (MASTER_SPEC §3.D/§3.E; audit H-05 — deterministic findings are
# authoritative over LLM interpretations). Candidate price levels are kept as
# observations only and never become actionable entry/SL/TP levels.
# ---------------------------------------------------------------------------


class LLMChartAssessment(BaseModel):
    """What a vision model observed in a chart screenshot."""

    observed_symbol: Optional[str] = Field(default=None, max_length=32)
    observed_timeframe: Optional[str] = Field(default=None, max_length=16)
    summary: str = Field(default="", max_length=2000)
    direction: Literal["bullish", "bearish", "neutral"] = "neutral"
    observations: List[str] = Field(default_factory=list, max_length=50)
    # Candidate prices merely READ from the image; unverified by design.
    candidate_levels: List[float] = Field(default_factory=list, max_length=50)
    uncertainty: List[str] = Field(default_factory=list, max_length=50)
    missing_evidence: List[str] = Field(default_factory=list, max_length=50)
    # Self-reported confidence of the model's own reading — kept as an LLM
    # self-report, never presented as a calibrated probability (MASTER_SPEC §3.F).
    self_reported_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class LLMReasoningOutput(BaseModel):
    """What a reasoning model produced from deterministic findings + context."""

    explanation: str = Field(default="", max_length=4000)
    bullish_scenario: str = Field(default="", max_length=2000)
    bearish_scenario: str = Field(default="", max_length=2000)
    key_risks: List[str] = Field(default_factory=list, max_length=50)
    uncertainty: List[str] = Field(default_factory=list, max_length=50)
    missing_evidence: List[str] = Field(default_factory=list, max_length=50)


class CandleInfo(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float


class MarketDataSnapshot(BaseModel):
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    candles: List[CandleInfo] = Field(default_factory=list)
    source: Literal["mt5", "mock", "unknown"] = "unknown"
    retrieved_at: Optional[str] = None
    stale: bool = False


class EvidenceItem(BaseModel):
    type: str
    description: str
    price_level: Optional[float] = None
    timestamp: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    source: Literal["ai", "deterministic"] = "deterministic"


class DisagreementItem(BaseModel):
    aspect: str
    deterministic: Any = None
    ai: Any = None
    reason: str
    resolved: bool = False


class ScreenshotAnalysisOutput(BaseModel):
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    summary: str = ""
    decision: Literal["BUY", "SELL", "WAIT"] = "WAIT"
    direction: Literal["bullish", "bearish", "neutral"] = "neutral"
    entry_levels: List[float] = Field(default_factory=list)
    sl: Optional[float] = None
    tp: Optional[float] = None
    risk_reward: Optional[float] = None
    evidence: List[EvidenceItem] = Field(default_factory=list)
    disagreements: List[DisagreementItem] = Field(default_factory=list)
    mtf_conflicts: List[str] = Field(default_factory=list)
    uncertainty: List[str] = Field(default_factory=list)
    analysis_timestamp: str = ""
    uses_mtf_data: bool = False
    data_synchronized: bool = False
    deterministic_signals: Dict[str, Any] = Field(default_factory=dict)
    ai_explanation: str = ""
    raw_ai_response: Dict[str, Any] = Field(default_factory=dict)
    model: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    source: Optional[str] = None


def validate_analysis_output(data: dict) -> ScreenshotAnalysisOutput:
    return ScreenshotAnalysisOutput.model_validate(data)
