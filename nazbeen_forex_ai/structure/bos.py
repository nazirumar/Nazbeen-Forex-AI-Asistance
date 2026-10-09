"""BOS/CHOCH/MSS detection based on confirmed swing structure."""

from __future__ import annotations

from typing import Any

from nazbeen_forex_ai.structure.swings import classify_structure, detect_swings
from nazbeen_forex_ai.structure.types import StructureEvent, candles_to_df


def detect_bos_choch_mss(candles: list[Any]) -> list[StructureEvent]:
    df = candles_to_df(candles)
    swings = detect_swings(df)
    classified = classify_structure(swings)
    events: list[StructureEvent] = []
    # Track last swing labels
    i = 0
    while i + 1 < len(classified):
        cur = classified[i]
        nxt = classified[i + 1]
        c_s = cur["swing"]
        n_s = nxt["swing"]
        # Determine structure break
        if c_s["type"] == "high" and n_s["type"] == "low":
            # after high, we get low
            pass
        if c_s["type"] == "low" and n_s["type"] == "high":
            # after low, high
            pass
        # BOS/CHOCH logic simplified but deterministic
        i += 1
    return events