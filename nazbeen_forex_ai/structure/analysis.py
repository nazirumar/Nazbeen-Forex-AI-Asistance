"""Basic multi-timeframe analysis and scenario evaluation."""

from __future__ import annotations

from typing import Any, Literal

from nazbeen_forex_ai.structure.fvg import detect_fvg
from nazbeen_forex_ai.structure.swings import detect_swings
from nazbeen_forex_ai.structure.types import candles_to_df

# Canonical multi-timeframe order (MASTER_SPEC §1), highest timeframe first.
MTF_ORDER = ("H1", "M15", "M5", "M1")


def swing_bias(candles: list[Any]) -> str:
    """Structural bias of one timeframe from confirmed swings.

    Classic structure read (identical math to the historical ``mtf_bias``
    closure — behaviour unchanged): with dense swings (``left=1/right=1``),
    count consecutive swing-high comparisons (HH → bullish point) and
    consecutive swing-low comparisons (HL → bullish point); more bullish than
    bearish points → ``BULLISH``, more bearish → ``BEARISH``, otherwise
    ``NEUTRAL`` ("no structural evidence", never a fabricated direction).

    Only confirmed swings are used: a swing at bar ``i`` needs ``right`` bars
    after it, so the read never looks ahead of the last bar.
    """
    if not candles:
        return "NEUTRAL"
    df = candles_to_df(candles)
    sw = detect_swings(df, left=1, right=1)
    highs = [s for s in sw if s.type == "high"]
    lows = [s for s in sw if s.type == "low"]
    bull = 0
    bear = 0
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


def mtf_bias(candles_h1: list[Any], candles_m15: list[Any], candles_m5: list[Any], candles_m1: list[Any]) -> dict[str, Any]:
    def bias_from_swings(c: list[Any]) -> str:
        # Delegate to the shared, unit-tested swing read (same math).
        return swing_bias(c)

    biases = {
        "H1": bias_from_swings(candles_h1),
        "M15": bias_from_swings(candles_m15),
        "M5": bias_from_swings(candles_m5),
        "M1": bias_from_swings(candles_m1),
    }
    # Real conflicts (audit H-05): every pair of timeframes with a decisive
    # (non-NEUTRAL) bias that disagrees is reported. NEUTRAL means "no
    # structural evidence" and never counts as agreement or conflict.
    order = ["H1", "M15", "M5", "M1"]
    decisive = [(tf, biases[tf]) for tf in order if biases[tf] in ("BULLISH", "BEARISH")]
    conflicts: list[str] = []
    for i in range(len(decisive)):
        for j in range(i + 1, len(decisive)):
            tf_a, bias_a = decisive[i]
            tf_b, bias_b = decisive[j]
            if bias_a != bias_b:
                conflicts.append(f"{tf_a} {bias_a} vs {tf_b} {bias_b}")
    return {**biases, "conflicts": conflicts}


def mtf_structure_alignment(candles_by_tf: dict[str, list[Any]]) -> dict[str, Any]:
    """Multi-timeframe structure alignment (MASTER_SPEC §3.C item 19).

    Per canonical timeframe: ``swing_bias`` of its candles, or ``None`` when
    that timeframe's data is **unavailable** (missing/empty) — an unfetchable
    timeframe is never reported as ``NEUTRAL``/aligned (audit H-05, Phase 11D
    convention).

    - ``aligned``: ``True`` when every decisive (non-NEUTRAL, available)
      timeframe agrees, ``False`` when any decisive pair disagrees, ``None``
      when there is no decisive evidence at all.
    - ``dominant``: the shared bias when aligned, otherwise ``None``.
    - ``conflicts``: the same real pairwise conflict strings as ``mtf_bias``.
    - ``unavailable``: list of timeframes without data.
    """
    structure: dict[str, Any] = {}
    for tf in MTF_ORDER:
        c = candles_by_tf.get(tf) or []
        structure[tf] = swing_bias(c) if c else None

    decisive = [(tf, structure[tf]) for tf in MTF_ORDER if structure[tf] in ("BULLISH", "BEARISH")]
    conflicts: list[str] = []
    for i in range(len(decisive)):
        for j in range(i + 1, len(decisive)):
            tf_a, bias_a = decisive[i]
            tf_b, bias_b = decisive[j]
            if bias_a != bias_b:
                conflicts.append(f"{tf_a} {bias_a} vs {tf_b} {bias_b}")

    if not decisive:
        aligned: bool | None = None
        dominant: str | None = None
    else:
        biases = {b for _, b in decisive}
        aligned = len(biases) == 1
        dominant = next(iter(biases)) if aligned else None

    return {
        "structure": structure,
        "aligned": aligned,
        "dominant": dominant,
        "conflicts": conflicts,
        "unavailable": [tf for tf in MTF_ORDER if structure[tf] is None],
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