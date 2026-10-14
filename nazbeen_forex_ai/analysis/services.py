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
from nazbeen_forex_ai.structure.analysis import (
    evaluate_scenario,
    mtf_bias,
    mtf_structure_alignment,
)
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

    # -- LangGraph node methods (Phase 11E, WP4) -----------------------------
    # Each node receives the graph state and returns a partial state update.
    # The pipeline logic deliberately lives here (not in graph.py) so the
    # existing monkeypatch targets keep working: ``services.get_llm_provider``
    # is looked up as a module global and market data is fetched via ``self``.

    def node_inspect_screenshot(self, state: Dict[str, Any]) -> Dict[str, Any]:
        hints = state.get("user_hints") or {}
        raw_symbol, raw_timeframe = self.extract_symbol_timeframe({}, hints)
        # Fabrication guard (audit H-04): never invent the chart identity.
        symbol = (raw_symbol or "").strip() or None
        timeframe = (raw_timeframe or "").strip() or None
        self._last_symbol = symbol.upper() if symbol else ""
        image_bytes, image_mime = self._read_image(state.get("image_file"))
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "identity_known": bool(symbol and timeframe),
            "image_bytes": image_bytes,
            "image_mime": image_mime,
            "errors": [],
            "uncertainty": [],
            "model_labels": {},
            "evidence": [],
            "disagreements": [],
        }

    def node_retrieve_market_data(self, state: Dict[str, Any]) -> Dict[str, Any]:
        symbol = state.get("symbol")
        timeframe = state.get("timeframe")
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        aux_candles: Dict[str, List[Dict[str, Any]]] = {}
        if state.get("identity_known"):
            try:
                md = self.retrieve_market_data(symbol, timeframe, count=100)
            except Exception as e:
                md = {
                    "symbol": symbol.upper() if symbol else symbol,
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
        return {"md": md, "aux_candles": aux_candles}

    def node_validate_market_data(self, state: Dict[str, Any]) -> Dict[str, Any]:
        md = state.get("md") or {}
        # Synchronization check (audit H-04): only fresh, real MT5 data counts
        # as synchronized. Mock data is simulated — it can never authorize a
        # BUY/SELL decision or price levels — and stale data is not current
        # evidence either. Both are labeled loudly instead.
        data_synchronized = (
            md.get("source") == "mt5"
            and bool(md.get("candles"))
            and not md.get("stale", False)
        )
        uncertainty = list(state.get("uncertainty") or [])
        # Honest labeling of data-quality limits (audits H-04/H-09).
        if not state.get("identity_known"):
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
        return {"data_synchronized": data_synchronized, "uncertainty": uncertainty}

    def node_detect_structure(self, state: Dict[str, Any]) -> Dict[str, Any]:
        det_signals = self.build_deterministic_signals(
            state.get("md") or {}, state.get("aux_candles") or {}
        )
        return {"det_signals": det_signals}

    def node_multi_timeframe_bias(self, state: Dict[str, Any]) -> Dict[str, Any]:
        md = state.get("md") or {}
        aux_candles = state.get("aux_candles") or {}
        det_signals = dict(state.get("det_signals") or {})
        primary_tf = (md.get("timeframe") or "M15").upper()
        by_tf: Dict[str, List[Dict[str, Any]]] = {}
        for tf in CANONICAL_TIMEFRAMES:
            by_tf[tf] = md.get("candles") if tf == primary_tf else (aux_candles.get(tf) or [])
        det_signals["mtf_alignment"] = mtf_structure_alignment(by_tf)
        return {
            "det_signals": det_signals,
            "det_decision": det_signals.get("scenario_decision") or "WAIT",
            "det_bias": det_signals.get("bias_m15"),
        }

    def node_reconcile_evidence(self, state: Dict[str, Any]) -> Dict[str, Any]:
        md = state.get("md") or {}
        det_signals = state.get("det_signals") or {}
        prompt = self.build_analysis_prompt(
            state.get("symbol"), state.get("timeframe"), md, det_signals
        )

        errors = list(state.get("errors") or [])
        uncertainty = list(state.get("uncertainty") or [])
        model_labels = dict(state.get("model_labels") or {})
        vision: Optional[LLMChartAssessment] = None
        reasoning: Optional[LLMReasoningOutput] = None

        # -- vision role ------------------------------------------------------
        try:
            vision_llm = get_llm_provider("vision")
            vision = vision_llm.inspect_chart(
                prompt, state.get("image_bytes"), state.get("image_mime")
            )
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

        # -- evidence: deterministic first, LLM claims tagged "ai" -------------
        evidence: List[EvidenceItem] = []
        timeframe = state.get("timeframe") or md.get("timeframe")
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
                        f"Fair value gaps detected on {timeframe}: "
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
        disagreements = self.reconcile(
            {"data_synchronized": state.get("data_synchronized", False)}, ai_claim
        )
        disagreements.extend(
            self.direction_disagreements(
                det_signals.get("scenario_decision") or "WAIT",
                det_signals.get("bias_m15"),
                vision,
            )
        )

        return {
            "vision": vision,
            "reasoning": reasoning,
            "errors": errors,
            "uncertainty": uncertainty,
            "model_labels": model_labels,
            "evidence": [e.model_dump() for e in evidence],
            "disagreements": [d.model_dump() for d in disagreements],
        }

    def _evaluate_primary_model(
        self, md: Dict[str, Any], aux_candles: Dict[str, List[Dict[str, Any]]]
    ) -> Optional[Dict[str, Any]]:
        """Run the chronological primary model on the M15 series (WP3/WP4).

        Returns ``None`` when the primary timeframe is not M15 or the model
        cannot run — the setup is then simply unavailable, never invented.
        """
        try:
            from nazbeen_forex_ai.structure.setup import evaluate_primary_setup

            primary_tf = (md.get("timeframe") or "").upper()
            m15 = md.get("candles") if primary_tf == "M15" else (aux_candles.get("M15") or [])
            if not m15:
                return None
            return evaluate_primary_setup(
                m15,
                aux_candles.get("M1") or [],
                aux_candles.get("M5") or [],
                aux_candles.get("H1") or [],
            )
        except Exception:
            return None

    def node_evaluate_scenario(self, state: Dict[str, Any]) -> Dict[str, Any]:
        md = state.get("md") or {}
        det_signals = state.get("det_signals") or {}
        setup = self._evaluate_primary_model(md, state.get("aux_candles") or {})
        det_decision = det_signals.get("scenario_decision") or "WAIT"
        # The primary model is authoritative when it completes on synchronized
        # data; otherwise the scenario heuristic stands (and authority forces
        # WAIT for unsynchronized data regardless).
        if setup and setup.get("complete") and state.get("data_synchronized"):
            det_decision = setup.get("decision") or det_decision
        # -- deterministic authority (audit H-05) -----------------------------
        decision, authority_notes = apply_deterministic_authority(
            det_decision,
            state.get("vision"),
            state.get("data_synchronized", False),
            bool(md.get("candles")),
        )
        uncertainty = list(state.get("uncertainty") or []) + list(authority_notes)
        return {
            "setup": setup,
            "det_decision": det_decision,
            "decision": decision,
            "direction": decision_to_direction(decision),
            "uncertainty": uncertainty,
        }

    def node_assess_risk(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Trade-plan assessment — only for a synchronized, complete setup.

        Fabrication guard (MASTER_SPEC §3.A): price levels enter the output
        **only** when the data is real/synchronized, the seven-step chain is
        complete and the risk service accepts the plan. Otherwise the analysis
        carries no entry/SL/TP at all.
        """
        md = state.get("md") or {}
        setup = state.get("setup") or {}
        decision = state.get("decision", "WAIT")
        risk: Optional[Dict[str, Any]] = None
        if (
            state.get("data_synchronized")
            and setup.get("complete")
            and decision in ("BUY", "SELL")
        ):
            levels = setup.get("levels") or {}
            entry = levels.get("entry")
            invalidation = levels.get("invalidation")
            target = levels.get("target")
            if all(v is not None for v in (entry, invalidation, target)):
                try:
                    from nazbeen_forex_ai.risk.services import create_trade_plan

                    plan = create_trade_plan(
                        {
                            "bias": "bullish" if decision == "BUY" else "bearish",
                            "entry": entry,
                            "sl": invalidation,
                            "tp": target,
                            "symbol": md.get("symbol") or state.get("symbol") or "EURUSD",
                            "evidence": [],
                        }
                    )
                except Exception:
                    plan = None
                if plan and plan.get("decision") in ("BUY", "SELL"):
                    risk = plan
        return {"risk": risk}

    def node_validate_output(self, state: Dict[str, Any]) -> Dict[str, Any]:
        md = state.get("md") or {}
        det_signals = state.get("det_signals") or {}
        vision = state.get("vision")
        reasoning = state.get("reasoning")
        errors = list(state.get("errors") or [])
        uncertainty = list(state.get("uncertainty") or [])

        risk = state.get("risk")
        entry_levels: List[float] = []
        sl: Optional[float] = None
        tp: Optional[float] = None
        risk_reward: Optional[float] = None
        if risk:
            entry_levels = risk.get("entry_levels") or []
            sl = risk.get("sl")
            tp = risk.get("tp")
            risk_reward = risk.get("rr")

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

        aux_candles = state.get("aux_candles") or {}
        mtf_count = (1 if md.get("candles") else 0) + sum(
            1 for v in aux_candles.values() if v
        )

        combined = {
            "symbol": state.get("symbol"),
            "timeframe": state.get("timeframe"),
            "summary": summary,
            "decision": state.get("decision", "WAIT"),
            "direction": state.get("direction", "neutral"),
            "entry_levels": entry_levels,
            "sl": sl,
            "tp": tp,
            "risk_reward": risk_reward,
            "evidence": state.get("evidence", []),
            "disagreements": state.get("disagreements", []),
            "mtf_conflicts": det_signals.get("mtf_conflicts", []),
            "uncertainty": uncertainty,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "uses_mtf_data": mtf_count > 1,
            "data_synchronized": state.get("data_synchronized", False),
            "deterministic_signals": det_signals,
            "ai_explanation": ai_explanation,
            "raw_ai_response": raw_ai,
            "model": (
                ", ".join(f"{k}={v}" for k, v in (state.get("model_labels") or {}).items())
                if state.get("model_labels")
                else None
            ),
            "errors": errors,
            "source": md.get("source", "unknown"),
        }
        if md.get("error"):
            combined["errors"].append(md["error"])
            combined["uncertainty"].append("Market data retrieval issue.")
        return {"combined": combined}

    def node_persist_analysis(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the composed output and run an optional injected hook.

        Validation retries once with a forced WAIT on failure (so a malformed
        LLM-derived field can never produce a false BUY/SELL); if even the
        forced-WAIT payload fails to validate, the error is raised visibly.
        The persistence hook is optional — absent means a no-op (the view
        persists the record).
        """
        combined = dict(state.get("combined") or {})
        try:
            output = validate_analysis_output(combined)
        except Exception as e:
            combined.setdefault("errors", []).append(f"schema_validation_error: {e}")
            combined["decision"] = "WAIT"
            combined["direction"] = "neutral"
            combined["entry_levels"] = []
            combined["sl"] = None
            combined["tp"] = None
            combined["risk_reward"] = None
            output = validate_analysis_output(combined)
        hook = state.get("persist_hook") or getattr(self, "persist_hook", None)
        if callable(hook):
            try:
                hook(output)
            except Exception:  # pragma: no cover - hook failures never break analysis
                pass
        return {"output": output}

    # -- main entry point ----------------------------------------------------
    def analyze(
        self, image_file=None, user_hints: Dict[str, Any] | None = None, **kwargs
    ) -> ScreenshotAnalysisOutput:
        """Run the LangGraph orchestration pipeline (Phase 11E, WP4).

        Same signature and output contract as before: the compiled graph's
        nodes are bound methods of this service, so provider/retrieval
        monkeypatch targets keep working unchanged.
        """
        from nazbeen_forex_ai.analysis.graph import run_analysis_graph

        return run_analysis_graph(
            self,
            image_file=image_file,
            user_hints=user_hints or {},
            persist_hook=kwargs.get("persist_hook"),
        )
