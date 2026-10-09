"""Structured analysis schema definitions and validators."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal, List, Dict, Any, Optional
import base64

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
