"""Basic multi-timeframe analysis and scenario evaluation."""

from __future__ import annotations

from typing import Any, Literal

from nazbeen_forex_ai.structure.fvg import detect_fvg
from nazbeen_forex_ai.structure.swings import classify_structure, detect_swings
from nazbeen_forex_ai.structure.types import candles_to_df


def mtf_bias(candles_h1: list[Any], candles_m15: list[Any], candles_m5: list[Any], candles_m1: list[Any]) -> dict[str, Any]:
    def bias_from_swings(c: list[Any]) -> str:
        df = candles_to_df(c)
        sw = detect_swings(df, left=2, right=2)
        cls = classify_structure(sw)
        if len(cls) < 2:
            return "NEUTRAL"
        # look for last HH vs LL pattern
        last = cls[-1]
        prev = cls[-2]
        # rough
        return "BULLISH" if last["swing"]["type"] == "low" else "BEARISH" if last["swing"]["type"] == "high" else "NEUTRAL"

    return {
        "H1": bias_from_swings(candles_h1),
        "M15": bias_from_swings(candles_m15),
        "M5": bias_from_swings(candles_m5),
        "M1": bias_from_swings(candles_m1),
        "conflicts": [],
    }


def evaluate_scenario(candles_m15: list[Any], candles_m5: list[Any], candles_m1: list[Any]) -> dict[str, Any]:
    bias = mtf_bias([], candles_m15, candles_m5, candles_m1)
    fvg_m15 = detect_fvg(candles_m15, threshold_pips=0.1)
    # simple heuristic
    direction: Literal["BUY", "SELL", "WAIT"] = "WAIT"
    if bias["M15"] == "BULLISH" and fvg_m15:
        # check direction
        if any(x.direction == "bullish" for x in fvg_m15):
            direction = "BUY"
    if bias["M15"] == "BEARISH" and fvg_m15:
        if any(x.direction == "bearish" for x in fvg_m15):
            direction = "SELL"
    return {
        "decision": direction,
        "bias": bias,
        "evidence": {"fvg_m15": [x.to_dict() for x in fvg_m15]},
        "mtf_conflicts": bias["conflicts"],
    }