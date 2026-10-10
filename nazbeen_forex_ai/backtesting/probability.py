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
            confidence_interval=[],
            sample_size=len(features),
            reason="Insufficient validated evidence (< 30 samples)",
            metrics={},
        )
    # stub: do not fabricate calibrated probabilities.
    # Audit M-08: an uncalibrated model reports NO confidence interval —
    # any interval here would be a fabricated figure (MASTER_SPEC §7).
    return ProbResult(
        probability=None,
        calibrated=False,
        confidence_interval=[],
        sample_size=len(features),
        reason="Model calibration not performed; returning null (no CI without calibration)",
        metrics={"brier_score": None},
    )
