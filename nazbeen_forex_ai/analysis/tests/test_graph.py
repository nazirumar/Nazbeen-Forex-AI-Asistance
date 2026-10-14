"""LangGraph orchestration tests (Phase 11E, WP4/WP7).

The analysis pipeline is a ten-node LangGraph whose nodes are bound methods of
:class:`ScreenshotAnalysisService` (see ``analysis/graph.py``). These tests lock
the node inventory and wiring, and prove the properties that must survive the
refactor:

- the deterministic engine stays authoritative (an LLM reading can never turn a
  WAIT into BUY/SELL, and LLM candidate levels never become entry/SL/TP);
- a failing configured provider is surfaced loudly and never silently replaced;
- provider/retrieval monkeypatch targets keep working through the graph;
- output validation retries once with a forced WAIT;
- the optional persistence hook receives the validated output.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from nazbeen_forex_ai.analysis import graph, services
from nazbeen_forex_ai.analysis import services as services_module
from nazbeen_forex_ai.analysis.graph import AnalysisGraph, GraphState, analyze_graph
from nazbeen_forex_ai.analysis.llm import BaseLLMProvider, LLMError
from nazbeen_forex_ai.analysis.schemas import LLMChartAssessment, LLMReasoningOutput
from nazbeen_forex_ai.analysis.services import ScreenshotAnalysisService

# ---------------------------------------------------------------------------
# Fixtures (mirror test_llm_service.py)
# ---------------------------------------------------------------------------

EXPECTED_NODES = [
    "inspect_screenshot",
    "retrieve_market_data",
    "validate_market_data",
    "detect_structure",
    "multi_timeframe_bias",
    "reconcile_evidence",
    "evaluate_scenario",
    "assess_risk",
    "validate_output",
    "persist_analysis",
]


def _flat_candles(n: int = 40, price: float = 1.1000) -> list[dict]:
    return [
        {
            "time": datetime(2026, 1, 1, 0, i, tzinfo=timezone.utc).isoformat(),
            "open": price,
            "high": price + 0.0001,
            "low": price - 0.0001,
            "close": price,
            "volume": 10,
        }
        for i in range(n)
    ]


def _md(candles: list[dict] | None = None, source: str = "mock") -> dict:
    return {
        "symbol": "EURUSD",
        "timeframe": "M15",
        "candles": _flat_candles() if candles is None else candles,
        "source": source,
        "retrieved_at": "2026-01-01T00:00:00Z",
        "stale": False,
        "last_bar_age_sec": 0.0,
        "market_state": "open",
    }


def _bullish_claim() -> LLMChartAssessment:
    return LLMChartAssessment(
        summary="Looks bullish.",
        direction="bullish",
        observations=["higher highs"],
        candidate_levels=[1.2345],
        uncertainty=["timestamp unknown"],
    )


class ScriptedVision(BaseLLMProvider):
    provider_name = "scripted"
    model = "scripted-vision-1"

    def __init__(self, assessment: Optional[LLMChartAssessment] = None, error: Exception | None = None):
        self.role = "vision"
        self.assessment = assessment or LLMChartAssessment()
        self.error = error
        self.calls: list[dict] = []

    def inspect_chart(self, prompt, image_bytes=None, image_mime=None):
        self.calls.append({"prompt": prompt, "image_bytes": image_bytes, "image_mime": image_mime})
        if self.error is not None:
            raise self.error
        return self.assessment

    def reason(self, prompt):
        return LLMReasoningOutput()


class ScriptedReasoning(BaseLLMProvider):
    provider_name = "scripted"
    model = "scripted-reasoning-1"

    def __init__(self, output: Optional[LLMReasoningOutput] = None, error: Exception | None = None):
        self.role = "reasoning"
        self.output = output or LLMReasoningOutput()
        self.error = error

    def inspect_chart(self, prompt, image_bytes=None, image_mime=None):
        return LLMChartAssessment()

    def reason(self, prompt):
        if self.error is not None:
            raise self.error
        return self.output


def _patch_providers(monkeypatch, vision: ScriptedVision, reasoning: ScriptedReasoning) -> None:
    def factory(role):
        return vision if role == "vision" else reasoning

    monkeypatch.setattr(services_module, "get_llm_provider", factory)


def _patch_md(monkeypatch, md: dict) -> None:
    monkeypatch.setattr(
        ScreenshotAnalysisService,
        "retrieve_market_data",
        lambda self, symbol, timeframe, count=100: md,
    )
    monkeypatch.setattr(
        ScreenshotAnalysisService,
        "retrieve_aux_timeframes",
        lambda self, symbol, timeframe: {},
    )


# ---------------------------------------------------------------------------
# Node inventory + wiring
# ---------------------------------------------------------------------------

def test_graph_has_10_nodes_in_spec_order():
    g = AnalysisGraph()
    assert g.NODE_NAMES == EXPECTED_NODES
    # Every node is a bound method of the service (single source of truth).
    for name in g.NODE_NAMES:
        assert callable(getattr(g.service, f"node_{name}")), name


def test_graph_state_declares_all_pipeline_channels():
    required = {
        "image_file",
        "user_hints",
        "symbol",
        "timeframe",
        "md",
        "aux_candles",
        "data_synchronized",
        "det_signals",
        "vision",
        "reasoning",
        "setup",
        "decision",
        "direction",
        "risk",
        "combined",
        "output",
    }
    assert required.issubset(set(GraphState.__annotations__))


def test_graph_builder_wires_nodes_in_a_chain(monkeypatch):
    recorded: dict = {"nodes": [], "edges": [], "entry": None}

    class Recorder:
        def __init__(self, state_schema):
            recorded["state_schema"] = state_schema

        def add_node(self, name, fn):
            recorded["nodes"].append((name, fn))

        def add_edge(self, a, b):
            recorded["edges"].append((a, b))

        def set_entry_point(self, name):
            recorded["entry"] = name

    monkeypatch.setattr(graph, "StateGraph", Recorder)
    AnalysisGraph().build()

    assert [n for n, _ in recorded["nodes"]] == EXPECTED_NODES
    assert recorded["entry"] == EXPECTED_NODES[0]
    assert recorded["edges"][-1][1] == graph.END
    assert len(recorded["edges"]) == len(EXPECTED_NODES)  # 9 chain + END


# ---------------------------------------------------------------------------
# End-to-end behavior through the real graph
# ---------------------------------------------------------------------------

def test_graph_runs_end_to_end_and_keeps_output_contract(monkeypatch):
    _patch_md(monkeypatch, _md())
    vision = ScriptedVision(assessment=_bullish_claim())
    reasoning = ScriptedReasoning(
        output=LLMReasoningOutput(
            explanation="Grounded write-up.", key_risks=["thin liquidity"]
        )
    )
    _patch_providers(monkeypatch, vision, reasoning)

    result = analyze_graph(user_hints={"symbol": "EURUSD", "timeframe": "M15"})

    # Mock data is never synchronized → deterministic authority forces WAIT.
    assert result.decision == "WAIT"
    assert result.data_synchronized is False
    assert result.entry_levels == []
    assert result.sl is None and result.tp is None
    assert result.source == "mock"
    assert result.model == "vision=scripted/scripted-vision-1, reasoning=scripted/scripted-reasoning-1"

    types = {e.type for e in result.evidence}
    assert "deterministic_bias" in types
    assert "llm_observation" in types
    # The vision provider actually received the (absent) image arguments.
    assert vision.calls and vision.calls[0]["image_bytes"] is None


def test_llm_bullish_claim_cannot_upgrade_wait(monkeypatch):
    _patch_md(monkeypatch, _md())  # mock → unsynchronized
    _patch_providers(monkeypatch, ScriptedVision(_bullish_claim()), ScriptedReasoning())

    result = analyze_graph(user_hints={"symbol": "EURUSD", "timeframe": "M15"})

    assert result.decision == "WAIT"
    assert result.direction == "neutral"
    assert any("decision remains WAIT" in u for u in result.uncertainty)


def test_vision_provider_failure_is_loud_and_never_mocked(monkeypatch):
    _patch_md(monkeypatch, _md())
    _patch_providers(
        monkeypatch,
        ScriptedVision(error=LLMError("provider down")),
        ScriptedReasoning(),
    )

    result = analyze_graph(user_hints={"symbol": "EURUSD", "timeframe": "M15"})

    assert any("vision provider failed" in e for e in result.errors)
    assert any("not inspected" in u for u in result.uncertainty)
    # A failed provider is never credited in `model`.
    assert "vision=" not in (result.model or "")


def test_reasoning_provider_failure_is_recorded(monkeypatch):
    _patch_md(monkeypatch, _md())
    _patch_providers(
        monkeypatch,
        ScriptedVision(),
        ScriptedReasoning(error=LLMError("reasoning down")),
    )

    result = analyze_graph(user_hints={"symbol": "EURUSD", "timeframe": "M15"})

    assert any("reasoning provider failed" in e for e in result.errors)
    assert any("explanation skipped" in u for u in result.uncertainty)


def test_retrieve_market_data_monkeypatch_target_still_honored(monkeypatch):
    def boom(self, symbol, timeframe, count=100):
        raise RuntimeError("data feed unavailable")

    monkeypatch.setattr(ScreenshotAnalysisService, "retrieve_market_data", boom)
    monkeypatch.setattr(
        ScreenshotAnalysisService,
        "retrieve_aux_timeframes",
        lambda self, symbol, timeframe: {},
    )
    _patch_providers(monkeypatch, ScriptedVision(), ScriptedReasoning())

    result = analyze_graph(user_hints={"symbol": "EURUSD", "timeframe": "M15"})

    assert result.decision == "WAIT"
    assert result.data_synchronized is False
    assert any("data feed unavailable" in e for e in result.errors)
    assert any("retrieval issue" in u for u in result.uncertainty)


def test_validation_failure_retries_once_with_forced_wait(monkeypatch):
    _patch_md(monkeypatch, _md())
    _patch_providers(monkeypatch, ScriptedVision(_bullish_claim()), ScriptedReasoning())

    real_validate = services_module.validate_analysis_output
    calls = {"n": 0}

    def flaky(data):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("simulated schema failure")
        return real_validate(data)

    monkeypatch.setattr(services_module, "validate_analysis_output", flaky)

    result = analyze_graph(user_hints={"symbol": "EURUSD", "timeframe": "M15"})

    assert calls["n"] == 2, "validation must retry exactly once"
    assert result.decision == "WAIT"
    assert result.entry_levels == []
    assert any("schema_validation_error" in e for e in result.errors)


def test_persist_hook_receives_validated_output(monkeypatch):
    _patch_md(monkeypatch, _md())
    _patch_providers(monkeypatch, ScriptedVision(), ScriptedReasoning())

    captured: list = []
    result = analyze_graph(
        user_hints={"symbol": "EURUSD", "timeframe": "M15"},
        persist_hook=captured.append,
    )

    assert len(captured) == 1
    assert captured[0] is result
    assert captured[0].decision == "WAIT"


def test_persist_hook_failure_never_breaks_analysis(monkeypatch):
    _patch_md(monkeypatch, _md())
    _patch_providers(monkeypatch, ScriptedVision(), ScriptedReasoning())

    def boom(_output):
        raise RuntimeError("hook exploded")

    result = analyze_graph(
        user_hints={"symbol": "EURUSD", "timeframe": "M15"}, persist_hook=boom
    )
    assert result.decision == "WAIT"


def test_service_analyze_is_a_facade_over_the_graph(monkeypatch):
    _patch_md(monkeypatch, _md())
    _patch_providers(monkeypatch, ScriptedVision(), ScriptedReasoning())

    result = ScreenshotAnalysisService().analyze(
        image_file=None, user_hints={"symbol": "EURUSD", "timeframe": "M15"}
    )
    assert result.decision == "WAIT"
    assert hasattr(result, "analysis_timestamp")
