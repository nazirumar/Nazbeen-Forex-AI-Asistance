"""Screenshot analysis orchestration.

Pipeline (MASTER_SPEC §3.A/§3.E, audit H-04/H-05):

1. Validate + read the uploaded screenshot; retrieve MT5/mock market data.
2. Run the deterministic ICT/SMC engine (swings, bias, FVG, scenario).
3. Ask the configured **vision** provider what it observes in the screenshot,
   and the configured **reasoning** provider for a grounded write-up.
4. Reconcile LLM claims against deterministic findings — the deterministic
   engine is authoritative: the LLM can never upgrade WAIT into BUY/SELL and
   its candidate price levels stay unverified observations, never entry/SL/TP.
5. Return a validated :class:`ScreenshotAnalysisOutput`.

Failure policy (MASTER_SPEC §4): if a configured real provider fails, the
failure is recorded in ``errors``/``uncertainty`` and the analysis continues
deterministic-only (decision WAIT unless the engine itself confirmed a setup).
The mock provider is **never** substituted silently for a real provider.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from nazbeen_forex_ai.analysis.llm import (
    LLMError,
    get_llm_provider,
)
from nazbeen_forex_ai.analysis.schemas import (
    DisagreementItem,
    EvidenceItem,
    LLMChartAssessment,
    LLMReasoningOutput,
    ScreenshotAnalysisOutput,
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


def apply_deterministic_authority(
    det_decision: str,
    vision: Optional[LLMChartAssessment],
    data_synchronized: bool,
    has_candles: bool,
) -> Tuple[str, List[str]]:
    """Compute the final decision from deterministic findings alone.

    - The deterministic decision (BUY/SELL/WAIT) is authoritative; an LLM
      reading never changes it (audit H-05).
    - Without synchronized candles the decision is always WAIT and no levels
      are produced (MASTER_SPEC §3.A, audit H-04).
    """
    notes: List[str] = []
    decision = det_decision if det_decision in ("BUY", "SELL", "WAIT") else "WAIT"

    if not (data_synchronized and has_candles):
        if decision != "WAIT":
            notes.append("Market data not synchronized; decision forced to WAIT.")
        decision = "WAIT"

    vision_direction = vision.direction if vision is not None else None
    if decision == "WAIT" and vision_direction in ("bullish", "bearish"):
        notes.append(
            "LLM reading noted but not confirmed by the deterministic engine; "
            "decision remains WAIT."
        )
    if decision == "BUY" and vision_direction == "bearish":
        notes.append(
            "LLM reading disagrees with the deterministic BUY; the deterministic "
            "engine is retained (authoritative)."
        )
    if decision == "SELL" and vision_direction == "bullish":
        notes.append(
            "LLM reading disagrees with the deterministic SELL; the deterministic "
            "engine is retained (authoritative)."
        )
    return decision, notes


def decision_to_direction(decision: str) -> str:
    return {"BUY": "bullish", "SELL": "bearish"}.get(decision, "neutral")


class ScreenshotAnalysisService:
    def extract_symbol_timeframe(
        self, image_meta: Dict[str, Any], user_hints: Dict[str, Any] | None = None
    ) -> Tuple[str | None, str | None]:
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

    def direction_disagreements(
        self,
        det_decision: str,
        det_bias: str | None,
        vision: Optional[LLMChartAssessment],
    ) -> List[DisagreementItem]:
        """Record LLM-vs-deterministic reading mismatches (deterministic wins)."""
        out: List[DisagreementItem] = []
        if vision is None:
            return out
        det_dir = decision_to_direction(det_decision)
        if det_decision == "WAIT" and vision.direction in ("bullish", "bearish"):
            out.append(
                DisagreementItem(
                    aspect="direction",
                    deterministic=f"{det_decision} (bias {det_bias})",
                    ai=vision.direction,
                    reason=(
                        "LLM reports a directional reading the deterministic engine did "
                        "not confirm; decision stays WAIT until deterministic evidence exists."
                    ),
                    resolved=True,
                )
            )
        elif det_decision in ("BUY", "SELL") and vision.direction in ("bullish", "bearish"):
            if vision.direction != det_dir:
                out.append(
                    DisagreementItem(
                        aspect="direction",
                        deterministic=det_decision,
                        ai=vision.direction,
                        reason="LLM direction contradicts the deterministic decision; deterministic retained.",
                        resolved=True,
                    )
                )
        obs_symbol = (vision.observed_symbol or "").upper().replace("/", "")
        if obs_symbol and obs_symbol.replace(" ", "") not in (
            "",
            (self._last_symbol or "").upper(),
        ):
            out.append(
                DisagreementItem(
                    aspect="symbol",
                    deterministic=self._last_symbol,
                    ai=vision.observed_symbol,
                    reason="Screenshot symbol read differs from the analyzed symbol.",
                    resolved=False,
                )
            )
        return out

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

    # -- helpers -------------------------------------------------------------
    _last_symbol: str = ""

    @staticmethod
    def _read_image(image_file) -> Tuple[Optional[bytes], Optional[str]]:
        """Read the uploaded screenshot bytes once, leaving the file rewound."""
        if not image_file:
            return None, None
        try:
            image_file.seek(0)
            data = image_file.read()
            image_file.seek(0)
        except Exception:
            return None, None
        if not data:
            return None, None
        mime = getattr(image_file, "content_type", None) or "image/png"
        return data, str(mime)

    def build_analysis_prompt(
        self, symbol: str, timeframe: str, md: Dict[str, Any], det_signals: Dict[str, Any]
    ) -> str:
        closes = [c.get("close") for c in md.get("candles", [])[-10:]]
        return json.dumps(
            {
                "task": "Analyze a forex chart screenshot (analysis-only; no trading decisions).",
                "symbol": symbol,
                "timeframe": timeframe,
                "deterministic_findings": {
                    "bias_m15": det_signals.get("bias_m15"),
                    "scenario_decision": det_signals.get("scenario_decision"),
                    "fvg_count": det_signals.get("fvg_count"),
                    "swings_count": det_signals.get("swings_count"),
                    "structure_labels": det_signals.get("structure_labels", [])[-5:],
                },
                "recent_closes": closes,
                "market_data_source": md.get("source"),
                "constraints": [
                    "Never fabricate exact price levels.",
                    "Never claim live synchronization if unknown.",
                    "Explain the deterministic findings; do not replace them.",
                ],
            }
        )

    def build_reasoning_prompt(
        self, base_prompt: str, vision: Optional[LLMChartAssessment]
    ) -> str:
        vision_block = (
            {
                "summary": vision.summary,
                "direction": vision.direction,
                "observations": vision.observations,
                "uncertainty": vision.uncertainty,
                "missing_evidence": vision.missing_evidence,
            }
            if vision is not None
            else {"note": "vision assessment unavailable (provider failed)"}
        )
        return json.dumps(
            {
                "base_context": json.loads(base_prompt),
                "vision_assessment": vision_block,
                "task": (
                    "Explain the deterministic findings and both scenarios. "
                    "Report uncertainty and missing evidence."
                ),
            }
        )

    # -- main entry point ----------------------------------------------------
    def analyze(
        self, image_file=None, user_hints: Dict[str, Any] | None = None, **kwargs
    ) -> ScreenshotAnalysisOutput:
        hints = user_hints or {}
        symbol, timeframe = self.extract_symbol_timeframe({}, hints)
        symbol = symbol or "EURUSD"
        timeframe = timeframe or "M15"
        self._last_symbol = symbol.upper()

        image_bytes, image_mime = self._read_image(image_file)

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
        det_decision = det_signals.get("scenario_decision") or "WAIT"
        det_bias = det_signals.get("bias_m15")
        prompt = self.build_analysis_prompt(symbol, timeframe, md, det_signals)

        # -- vision role ------------------------------------------------------
        vision: Optional[LLMChartAssessment] = None
        reasoning: Optional[LLMReasoningOutput] = None
        errors: List[str] = []
        uncertainty: List[str] = []
        model_labels: Dict[str, str] = {}

        try:
            vision_llm = get_llm_provider("vision")
            vision = vision_llm.inspect_chart(prompt, image_bytes, image_mime)
            # Label only after a successful call: `model` must never credit a
            # provider whose call failed (failures are named in `errors`).
            model_labels["vision"] = f"{vision_llm.provider_name}/{vision_llm.model}"
        except LLMError as e:
            # Loud failure (MASTER_SPEC §4): recorded, never mocked over.
            errors.append(f"vision provider failed: {e}")
            uncertainty.append(
                "Vision LLM unavailable; screenshot was not inspected by an AI model."
            )

        # -- reasoning role ---------------------------------------------------
        try:
            reasoning_llm = get_llm_provider("reasoning")
            reasoning = reasoning_llm.reason(self.build_reasoning_prompt(prompt, vision))
            model_labels["reasoning"] = f"{reasoning_llm.provider_name}/{reasoning_llm.model}"
        except LLMError as e:
            errors.append(f"reasoning provider failed: {e}")
            uncertainty.append("Reasoning LLM unavailable; explanation skipped.")

        # -- deterministic authority (audit H-05) -----------------------------
        decision, authority_notes = apply_deterministic_authority(
            det_decision, vision, data_synchronized, bool(md.get("candles"))
        )
        uncertainty.extend(authority_notes)

        # -- evidence: deterministic first, LLM claims tagged "ai" -------------
        evidence: List[EvidenceItem] = []
        if det_signals:
            evidence.append(
                EvidenceItem(
                    type="deterministic_bias",
                    description=f"M15 bias from confirmed swings: {det_bias}",
                    source="deterministic",
                )
            )
            evidence.append(
                EvidenceItem(
                    type="deterministic_scenario",
                    description=(
                        f"Deterministic scenario decision: {det_signals.get('scenario_decision')}"
                    ),
                    source="deterministic",
                )
            )
            evidence.append(
                EvidenceItem(
                    type="deterministic_fvg",
                    description=f"Fair value gaps detected on M15: {det_signals.get('fvg_count')}",
                    source="deterministic",
                )
            )
        if vision is not None:
            for obs in vision.observations[:20]:
                evidence.append(
                    EvidenceItem(type="llm_observation", description=obs, source="ai")
                )
            for level in vision.candidate_levels[:20]:
                evidence.append(
                    EvidenceItem(
                        type="candidate_level",
                        description=(
                            "Candidate price level read from the screenshot — unverified, "
                            "never used as entry/SL/TP."
                        ),
                        price_level=level,
                        source="ai",
                    )
                )
            uncertainty.extend(vision.uncertainty)
            uncertainty.extend(vision.missing_evidence)
        if reasoning is not None:
            uncertainty.extend(reasoning.uncertainty)
            uncertainty.extend(reasoning.missing_evidence)

        # -- disagreements ----------------------------------------------------
        ai_claim = {"data_synchronized": False}
        disagreements = self.reconcile({"data_synchronized": data_synchronized}, ai_claim)
        disagreements.extend(
            self.direction_disagreements(det_decision, det_bias, vision)
        )

        # -- compose ----------------------------------------------------------
        summary = (
            vision.summary
            if vision is not None and vision.summary
            else (
                "Screenshot uploaded; analysis completed from deterministic market "
                "data only (no AI vision assessment available)."
            )
        )
        ai_explanation = ""
        if reasoning is not None:
            ai_explanation = reasoning.explanation
            if reasoning.bullish_scenario or reasoning.bearish_scenario:
                ai_explanation += (
                    f"\n\nBullish scenario: {reasoning.bullish_scenario}"
                    f"\nBearish scenario: {reasoning.bearish_scenario}"
                )
            if reasoning.key_risks:
                ai_explanation += "\nKey risks: " + "; ".join(reasoning.key_risks)

        raw_ai: Dict[str, Any] = {
            "vision": vision.model_dump() if vision is not None else None,
            "reasoning": reasoning.model_dump() if reasoning is not None else None,
            "provider_failures": errors,
        }

        combined = {
            "symbol": symbol,
            "timeframe": timeframe,
            "summary": summary,
            "decision": decision,
            "direction": decision_to_direction(decision),
            # Deterministic engine exposes no price levels; LLM candidates stay
            # in `evidence` as unverified observations (MASTER_SPEC §3.A).
            "entry_levels": [],
            "sl": None,
            "tp": None,
            "risk_reward": None,
            "evidence": [e.model_dump() for e in evidence],
            "disagreements": [d.model_dump() for d in disagreements],
            "mtf_conflicts": det_signals.get("mtf_conflicts", []),
            "uncertainty": uncertainty,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "uses_mtf_data": True,
            "data_synchronized": data_synchronized,
            "deterministic_signals": det_signals,
            "ai_explanation": ai_explanation,
            "raw_ai_response": raw_ai,
            "model": (
                ", ".join(f"{k}={v}" for k, v in model_labels.items())
                if model_labels
                else None
            ),
            "errors": errors,
            "source": md.get("source", "unknown"),
        }
        if md.get("error"):
            combined["errors"].append(md["error"])
            combined["uncertainty"].append("Market data retrieval issue.")
        try:
            return validate_analysis_output(combined)
        except Exception as e:
            combined.setdefault("errors", []).append(f"schema_validation_error: {e}")
            combined["decision"] = "WAIT"
            combined["direction"] = "neutral"
            combined["entry_levels"] = []
            combined["sl"] = None
            combined["tp"] = None
            return validate_analysis_output(combined)
