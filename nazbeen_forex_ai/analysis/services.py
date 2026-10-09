"""Screenshot analysis orchestration (LangGraph-style workflow)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from django.conf import settings

from nazbeen_forex_ai.analysis.llm import get_llm_provider, LLMError
from nazbeen_forex_ai.analysis.schemas import (
    ScreenshotAnalysisOutput,
    EvidenceItem,
    DisagreementItem,
    validate_analysis_output,
)
from nazbeen_forex_ai.marketdata.factory import get_market_data_provider
from nazbeen_forex_ai.structure.swings import detect_swings, classify_structure
from nazbeen_forex_ai.structure.fvg import detect_fvg
from nazbeen_forex_ai.structure.analysis import mtf_bias, evaluate_scenario
from nazbeen_forex_ai.structure.types import candles_to_df


def to_candle_dicts(candles) -> List[Dict[str, Any]]:
    out = []
    for c in candles:
        d = c.to_dict() if hasattr(c, "to_dict") else c
        out.append(d)
    return out


class ScreenshotAnalysisService:
    def extract_symbol_timeframe(self, image_meta: Dict[str, Any], user_hints: Dict[str, Any] | None = None) -> Tuple[str | None, str | None]:
        hints = user_hints or {}
        return hints.get("symbol"), hints.get("timeframe")

    def retrieve_market_data(self, symbol: str, timeframe: str, count: int = 100) -> Dict[str, Any]:
        provider = get_market_data_provider()
        try:
            provider.connect()
            info = provider.get_connection_info()
            candles = provider.get_candles(symbol=symbol.upper(), timeframe=timeframe, count=count)
            return {
                "symbol": symbol.upper(),
                "timeframe": timeframe,
                "candles": to_candle_dicts(candles),
                "source": info.get("mode", "unknown"),
                "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "stale": False,
            }
        except Exception as e:
            return {
                "symbol": symbol.upper() if symbol else symbol,
                "timeframe": timeframe,
                "candles": [],
                "source": "unknown",
                "error": str(e),
                "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "stale": True,
            }

    def reconcile(self, deterministic: Dict[str, Any], ai: Dict[str, Any]) -> List[DisagreementItem]:
        disagreements: List[DisagreementItem] = []
        # simple reconciliation: if AI claims synchronized but we have no mt5 sync, flag
        if ai.get("data_synchronized") and not deterministic.get("data_synchronized"):
            disagreements.append(
                DisagreementItem(
                    aspect="data_synchronization",
                    deterministic=deterministic.get("data_synchronized"),
                    ai=ai.get("data_synchronized"),
                    reason="AI claims synchronization; deterministic check could not establish it.",
                    resolved=False,
                )
            )
        return disagreements

    def build_deterministic_signals(self, md: Dict[str, Any]) -> Dict[str, Any]:
        signals: Dict[str, Any] = {}
        if not md.get("candles"):
            return signals
        df = candles_to_df(md["candles"])
        sw = detect_swings(df, left=2, right=2)
        cls = classify_structure(sw)
        fvg = detect_fvg(df)
        bias = mtf_bias([], md["candles"], [], [])
        scen = evaluate_scenario(md["candles"], [], [])
        signals.update(
            {
                "swings_count": len(sw),
                "structure_labels": [c["label"] for c in cls[-10:]],
                "fvg_count": len(fvg),
                "bias_m15": bias.get("M15"),
                "scenario_decision": scen.get("decision"),
                "mtf_conflicts": scen.get("mtf_conflicts", []),
            }
        )
        return signals

    def analyze(self, image_file=None, user_hints: Dict[str, Any] | None = None, **kwargs) -> ScreenshotAnalysisOutput:
        llm = get_llm_provider()
        hints = user_hints or {}
        symbol, timeframe = self.extract_symbol_timeframe({}, hints)
        symbol = symbol or "EURUSD"
        timeframe = timeframe or "M15"

        md: Dict[str, Any] = {}
        try:
            md = self.retrieve_market_data(symbol, timeframe, count=100)
        except Exception as e:
            md = {
                "symbol": symbol.upper() if symbol else symbol,
                "timeframe": timeframe,
                "candles": [],
                "source": "unknown",
                "error": str(e),
                "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "stale": True,
            }

        det_signals = self.build_deterministic_signals(md)
        data_synchronized = md.get("source") in ("mt5", "mock") and bool(md.get("candles"))

        prompt = json.dumps(
            {
                "task": "Analyze forex chart screenshot",
                "constraints": "Never fabricate exact price levels; never claim live sync if unknown.",
                "market_data_present": bool(md.get("candles")),
                "symbol": symbol,
                "timeframe": timeframe,
            }
        )

        try:
            ai_raw = llm.generate_analysis(prompt)
        except LLMError as e:
            ai_raw = {"errors": [str(e)]}

        # enforce safety
        if not data_synchronized and ai_raw.get("data_synchronized", False):
            ai_raw["data_synchronized"] = False
            ai_raw.setdefault("uncertainty", []).append("Synchronization not established; corrected to false.")

        # if no prices, force WAIT and no fabricated levels
        if not data_synchronized:
            ai_raw["decision"] = "WAIT"
            ai_raw["entry_levels"] = []
            ai_raw["sl"] = None
            ai_raw["tp"] = None

        disagreements = self.reconcile({"data_synchronized": data_synchronized}, ai_raw)
        combined = {
            **ai_raw,
            "symbol": symbol,
            "timeframe": timeframe,
            "disagreements": [d.model_dump() if hasattr(d, "model_dump") else d for d in disagreements],
            "deterministic_signals": det_signals,
            "mtf_conflicts": det_signals.get("mtf_conflicts", ai_raw.get("mtf_conflicts", [])),
            "uses_mtf_data": True,
            "data_synchronized": data_synchronized,
            "source": md.get("source", "unknown"),
            "analysis_timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        if md.get("error"):
            combined.setdefault("errors", []).append(md["error"])
            combined.setdefault("uncertainty", []).append("Market data retrieval issue.")
        try:
            return validate_analysis_output(combined)
        except Exception as e:
            combined.setdefault("errors", []).append(f"schema_validation_error: {e}")
            combined["decision"] = "WAIT"
            return validate_analysis_output(combined)
