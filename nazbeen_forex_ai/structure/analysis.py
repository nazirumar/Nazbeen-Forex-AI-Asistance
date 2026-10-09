"""Basic multi-timeframe analysis and scenario evaluation."""

from __future__ import annotations

from typing import Any, Literal

from nazbeen_forex_ai.structure.fvg import detect_fvg
from nazbeen_forex_ai.structure.swings import detect_swings
from nazbeen_forex_ai.structure.types import candles_to_df


def mtf_bias(candles_h1: list[Any], candles_m15: list[Any], candles_m5: list[Any], candles_m1: list[Any]) -> dict[str, Any]:
    def bias_from_swings(c: list[Any]) -> str:
        if not c:
            return "NEUTRAL"
        df = candles_to_df(c)
        # left=1/right=1 gives enough swing density for a bias read on short series.
        sw = detect_swings(df, left=1, right=1)
        highs = [s for s in sw if s.type == "high"]
        lows = [s for s in sw if s.type == "low"]
        bull = 0
        bear = 0
        # Classic structure read: compare consecutive swing highs (HH/LH) and
        # consecutive swing lows (HL/LL). Higher-high/higher-low = bullish.
        for series in (highs, lows):
            for a, b in zip(series, series[1:]):
                if b.price > a.price:
                    bull += 1
                elif b.price < a.price:
                    bear += 1
        if bull > bear:
            return "BULLISH"
        if bear > bull:
            return "BEARISH"
        return "NEUTRAL"

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