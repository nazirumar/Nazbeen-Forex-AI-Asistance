"""Real LangGraph orchestration for screenshot analysis (Phase 11E, WP4).

``ScreenshotAnalysisService.analyze()`` is a façade over a compiled
``StateGraph``. The ten nodes are bound methods of the service (defined in
``services.py``), and this module only declares the typed state and wires the
nodes together — so the pipeline logic has a single home and the existing
monkeypatch targets (``services.get_llm_provider``,
``ScreenshotAnalysisService.retrieve_market_data``) keep working unchanged.

Deterministic authority (audit H-05) is preserved: the LLM never upgrades a
``WAIT`` into ``BUY``/``SELL`` and never supplies entry/SL/TP. Provider failures
are recorded and the run degrades to deterministic-only — the mock provider is
never silently substituted for a configured real one (MASTER_SPEC §4).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from nazbeen_forex_ai.analysis.schemas import (
    LLMChartAssessment,
    LLMReasoningOutput,
    ScreenshotAnalysisOutput,
)
from nazbeen_forex_ai.analysis.services import ScreenshotAnalysisService


class GraphState(TypedDict, total=False):
    """Typed state threaded through the analysis graph.

    Every node returns a partial update that is merged into this state; keys are
    populated in the order the nodes run (see :data:`AnalysisGraph.NODE_NAMES`).
    """

    # inputs
    image_file: Any
    user_hints: Dict[str, Any]
    persist_hook: Any

    # inspect_screenshot
    image_bytes: Optional[bytes]
    image_mime: Optional[str]
    symbol: Optional[str]
    timeframe: Optional[str]
    identity_known: bool

    # retrieve_market_data
    md: Dict[str, Any]
    aux_candles: Dict[str, List[Dict[str, Any]]]

    # validate_market_data
    data_synchronized: bool
    uncertainty: List[str]

    # detect_structure / multi_timeframe_bias
    det_signals: Dict[str, Any]
    det_decision: str
    det_bias: Optional[str]

    # reconcile_evidence
    vision: Optional[LLMChartAssessment]
    reasoning: Optional[LLMReasoningOutput]
    errors: List[str]
    model_labels: Dict[str, str]
    evidence: List[Dict[str, Any]]
    disagreements: List[Dict[str, Any]]

    # evaluate_scenario / assess_risk
    setup: Optional[Dict[str, Any]]
    decision: str
    direction: str
    risk: Optional[Dict[str, Any]]

    # validate_output / persist_analysis
    combined: Dict[str, Any]
    output: Optional[ScreenshotAnalysisOutput]


class AnalysisGraph:
    """Builds and runs the analysis ``StateGraph`` for one service instance."""

    #: Node names in execution order (MASTER_SPEC §3.E decomposition).
    NODE_NAMES: List[str] = [
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

    def __init__(self, service: Optional[ScreenshotAnalysisService] = None) -> None:
        self.service = service or ScreenshotAnalysisService()

    def node_method(self, name: str):
        """Return the bound service method implementing node ``name``."""
        return getattr(self.service, f"node_{name}")

    def build(self) -> StateGraph:
        """Construct the (uncompiled) graph wiring the ten nodes in a chain."""
        graph = StateGraph(GraphState)
        for name in self.NODE_NAMES:
            graph.add_node(name, self.node_method(name))
        graph.set_entry_point(self.NODE_NAMES[0])
        for upstream, downstream in zip(self.NODE_NAMES, self.NODE_NAMES[1:]):
            graph.add_edge(upstream, downstream)
        graph.add_edge(self.NODE_NAMES[-1], END)
        return graph

    def run(self, state: Dict[str, Any]) -> ScreenshotAnalysisOutput:
        """Compile and invoke the graph, returning the validated output."""
        app = self.build().compile()
        final = app.invoke(state)
        return final["output"]


def run_analysis_graph(
    service: ScreenshotAnalysisService,
    image_file: Any = None,
    user_hints: Optional[Dict[str, Any]] = None,
    persist_hook: Any = None,
) -> ScreenshotAnalysisOutput:
    """Run the orchestration for ``service`` and return the output contract."""
    graph = AnalysisGraph(service)
    return graph.run(
        {
            "image_file": image_file,
            "user_hints": user_hints or {},
            "persist_hook": persist_hook,
        }
    )


def analyze_graph(
    image_file: Any = None,
    user_hints: Optional[Dict[str, Any]] = None,
    persist_hook: Any = None,
) -> ScreenshotAnalysisOutput:
    """Convenience entry point: build a default service and run the graph."""
    return run_analysis_graph(
        ScreenshotAnalysisService(),
        image_file=image_file,
        user_hints=user_hints,
        persist_hook=persist_hook,
    )
