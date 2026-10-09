"""Probability model (optional) — return null if insufficient evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ProbResult:
    probability: Optional[float]
    calibrated: bool
    confidence_interval: List[float]
    sample_size: int
    reason: str
    metrics: Dict[str, Any]


def evaluate_probability(features: List[Dict[str, Any]]) -> ProbResult:
    if len(features) < 30:
        return ProbResult(
            probability=None,
            calibrated=False,
            confidence_interval=[0.0, 1.0],
            sample_size=len(features),
            reason="Insufficient validated evidence (< 30 samples)",
            metrics={},
        )
    # stub: do not fabricate calibrated probabilities
    return ProbResult(
        probability=None,
        calibrated=False,
        confidence_interval=[0.3, 0.7],
        sample_size=len(features),
        reason="Model calibration not performed; returning null",
        metrics={"brier_score": None},
    )
