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

from django.conf import settings

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
from nazbeen_forex_ai.marketdata.freshness import assess_staleness, market_state
from nazbeen_forex_ai.structure.swings import detect_swings, classify_structure
from nazbeen_forex_ai.structure.fvg import detect_fvg
from nazbeen_forex_ai.structure.analysis import mtf_bias, evaluate_scenario
from nazbeen_forex_ai.structure.types import candles_to_df

# Canonical higher/lower timeframes analyzed alongside the requested one (H-05).
CANONICAL_TIMEFRAMES = ("H1", "M15", "M5", "M1")


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
        state = market_state()
        try:
            provider.connect()
            info = provider.get_connection_info()
            candles = provider.get_candles(symbol=symbol.upper(), timeframe=timeframe, count=count)
            candle_dicts = to_candle_dicts(candles)
            # Freshness (audit H-09): the last-bar age is measured, never assumed.
            fresh = assess_staleness(
                candle_dicts[-1].get("time") if candle_dicts else None,
                timeframe,
                threshold_sec=settings.MT5_STALENESS_THRESHOLD_SEC,
            )
            return {
                "symbol": symbol.upper(),
                "timeframe": timeframe,
                "candles": candle_dicts,
                "source": info.get("mode", "unknown"),
                "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "stale": fresh["stale"],
                "last_bar_age_sec": fresh["last_bar_age_sec"],
                "market_state": state,
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
                "last_bar_age_sec": None,
                "market_state": state,
            }

    def retrieve_aux_timeframes(self, symbol: str, primary_timeframe: str) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch the other canonical timeframes for a real multi-timeframe read (H-05).

        A failed/missing timeframe degrades to ``[]`` (neutral) — never fabricated.
        """
        aux: Dict[str, List[Dict[str, Any]]] = {}
        primary = (primary_timeframe or "").upper()
        for tf in CANONICAL_TIMEFRAMES:
            if tf == primary:
                continue
            try:
                md_tf = self.retrieve_market_data(symbol, tf, count=100)
                aux[tf] = md_tf.get("candles", []) or []
            except Exception:
                aux[tf] = []
        return aux

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

    def build_deterministic_signals(
        self,
        md: Dict[str, Any],
        aux_candles: Dict[str, List[Dict[str, Any]]] | None = None,
    ) -> Dict[str, Any]:
        signals: Dict[str, Any] = {}
        if not md.get("candles"):
            return signals
        aux_candles = aux_candles or {}
        primary_tf = (md.get("timeframe") or "M15").upper()
        # Map each canonical timeframe to its candles; the analyzed timeframe
        # supplies its own data, the others come from the auxiliary fetches.
        by_tf: Dict[str, List[Dict[str, Any]]] = {}
        for tf in CANONICAL_TIMEFRAMES:
            by_tf[tf] = md["candles"] if tf == primary_tf else (aux_candles.get(tf) or [])
        df = candles_to_df(md["candles"])
        sw = detect_swings(df, left=2, right=2)
        cls = classify_structure(sw)
        fvg = detect_fvg(df)
        # Real multi-timeframe bias + conflicts across H1/M15/M5/M1 (audit H-05).
        bias = mtf_bias(by_tf["H1"], by_tf["M15"], by_tf["M5"], by_tf["M1"])
        # Scenario decision stays anchored to the analyzed timeframe's structure.
        scen = evaluate_scenario(md["candles"], by_tf.get("M5", []), by_tf.get("M1", []))
        signals.update(
            {
                "swings_count": len(sw),
                "structure_labels": [c["label"] for c in cls[-10:]],
                "fvg_count": len(fvg),
                "bias_m15": bias.get("M15"),
                "bias_mtf": {tf: bias.get(tf) for tf in CANONICAL_TIMEFRAMES},
                "scenario_decision": scen.get("decision"),
                "mtf_conflicts": bias.get("conflicts", []),
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
        self, symbol: str | None, timeframe: str | None, md: Dict[str, Any], det_signals: Dict[str, Any]
    ) -> str:
        closes = [c.get("close") for c in md.get("candles", [])[-10:]]
        return json.dumps(
            {
                "task": "Analyze a forex chart screenshot (analysis-only; no trading decisions).",
                "symbol": symbol,
                "timeframe": timeframe,
                "deterministic_findings": {
                    "bias_m15": det_signals.get("bias_m15"),
                    "bias_mtf": det_signals.get("bias_mtf"),
                    "mtf_conflicts": det_signals.get("mtf_conflicts", []),
                    "scenario_decision": det_signals.get("scenario_decision"),
                    "fvg_count": det_signals.get("fvg_count"),
                    "swings_count": det_signals.get("swings_count"),
                    "structure_labels": det_signals.get("structure_labels", [])[-5:],
                },
                "recent_closes": closes,
                "market_data_source": md.get("source"),
                "market_state": md.get("market_state"),
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
        raw_symbol, raw_timeframe = self.extract_symbol_timeframe({}, hints)
        # Fabrication guard (audit H-04): never invent the chart identity.
        # Missing symbol/timeframe means unknown → no market-data fetch and the
        # decision stays WAIT. No EURUSD/M15 defaults, ever.
        symbol = (raw_symbol or "").strip() or None
        timeframe = (raw_timeframe or "").strip() or None
        identity_known = bool(symbol and timeframe)
        self._last_symbol = symbol.upper() if symbol else ""

        image_bytes, image_mime = self._read_image(image_file)

        md: Dict[str, Any] = {}
        aux_candles: Dict[str, List[Dict[str, Any]]] = {}
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if identity_known:
            try:
                md = self.retrieve_market_data(symbol, timeframe, count=100)
            except Exception as e:
                md = {
                    "symbol": symbol.upper(),
                    "timeframe": timeframe,
                    "candles": [],
                    "source": "unknown",
                    "error": str(e),
                    "retrieved_at": now_iso,
                    "stale": True,
                    "last_bar_age_sec": None,
                    "market_state": market_state(),
                }
            # Real multi-timeframe read: H1/M15/M5/M1 (audit H-05).
            aux_candles = self.retrieve_aux_timeframes(symbol, timeframe)
        else:
            md = {
                "symbol": None,
                "timeframe": None,
                "candles": [],
                "source": "unknown",
                "retrieved_at": now_iso,
                "stale": True,
                "last_bar_age_sec": None,
                "market_state": market_state(),
            }

        det_signals = self.build_deterministic_signals(md, aux_candles)
        # Synchronization check (audit H-04): only fresh, real MT5 data counts
        # as synchronized. Mock data is simulated — it can never authorize a
        # BUY/SELL decision or price levels — and stale data is not current
        # evidence either. Both are labeled loudly instead.
        data_synchronized = (
            md.get("source") == "mt5"
            and bool(md.get("candles"))
            and not md.get("stale", False)
        )
        det_decision = det_signals.get("scenario_decision") or "WAIT"
        det_bias = det_signals.get("bias_m15")
        prompt = self.build_analysis_prompt(symbol, timeframe, md, det_signals)

        # -- vision role ------------------------------------------------------
        vision: Optional[LLMChartAssessment] = None
        reasoning: Optional[LLMReasoningOutput] = None
        errors: List[str] = []
        uncertainty: List[str] = []
        model_labels: Dict[str, str] = {}

        # Honest labeling of data-quality limits (audits H-04/H-09).
        if not identity_known:
            uncertainty.append(
                "Symbol/timeframe not provided; chart identity unknown — no market "
                "data was fetched and the decision stays WAIT."
            )
        elif md.get("source") == "mock":
            uncertainty.append(
                "Market data source is mock (simulated, not live pricing); "
                "decision forced to WAIT."
            )
        if md.get("stale") and md.get("candles"):
            uncertainty.append(
                "Stale market data: last bar age "
                f"{md.get('last_bar_age_sec')}s exceeds the freshness threshold."
            )
        if md.get("market_state") == "closed":
            uncertainty.append(
                "Market session closed at analysis time; prices are from the "
                "previous session."
            )

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
                    description=(
                        "Multi-timeframe bias from confirmed swings "
                        f"(H1/M15/M5/M1): {det_signals.get('bias_mtf')}"
                    ),
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
                    description=(
                        f"Fair value gaps detected on {timeframe or md.get('timeframe')}: "
                        f"{det_signals.get('fvg_count')}"
                    ),
                    source="deterministic",
                )
            )
            if det_signals.get("mtf_conflicts"):
                evidence.append(
                    EvidenceItem(
                        type="mtf_conflict",
                        description=(
                            "Multi-timeframe bias conflicts: "
                            + "; ".join(det_signals["mtf_conflicts"])
                        ),
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

        # True only when more than one timeframe actually contributed candles —
        # never claimed by default.
        mtf_count = (1 if md.get("candles") else 0) + sum(
            1 for v in aux_candles.values() if v
        )
        uses_mtf_data = mtf_count > 1

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
            "uses_mtf_data": uses_mtf_data,
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
