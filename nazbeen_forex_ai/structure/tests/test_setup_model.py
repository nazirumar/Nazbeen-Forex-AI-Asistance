"""Phase 11E: chronological primary trading model (state machine) tests.

Covers: complete-chain BUY/SELL on the golden fixtures, WAIT fallbacks for
every broken precondition (no sweep, chronology break, invalidated FVG, stale
chain, missing/unavailable M1, M5 conflict), levels derived only from real
candles, strict step chronology, and prefix-consistency (no look-ahead /
no repainting). All fixtures are synthetic test-only data.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from nazbeen_forex_ai.structure.bos import detect_bos_choch_mss
from nazbeen_forex_ai.structure.displacement import detect_displacement
from nazbeen_forex_ai.structure.setup import STEPS, evaluate_primary_setup
from nazbeen_forex_ai.structure.tests import golden as g

STEP_KEYS = [k for k, _ in STEPS]


def _parse(raw):
    return datetime.fromisoformat(raw.replace("Z", "+00:00")) if raw else None


def _steps_by_key(result):
    return {s["key"]: s for s in result["steps"]}


def _bullish():
    return (
        g.golden_bullish_m15(),
        g.golden_bullish_m1(),
        g.golden_bullish_m5(),
        g.golden_bullish_h1(),
    )


# --- complete chains ---------------------------------------------------------


def test_bullish_golden_completes_buy():
    m15, m1, m5, h1 = _bullish()
    res = evaluate_primary_setup(m15, m1, m5, h1)

    assert res["model"] == "ict_primary_setup_v1"
    assert res["direction"] == "bullish"
    assert res["decision"] == "BUY"
    assert res["complete"] is True
    assert res["stale"] is False
    assert res["blocked_by"] == []
    steps = _steps_by_key(res)
    assert list(steps) == STEP_KEYS
    assert all(steps[k]["status"] == "satisfied" for k in STEP_KEYS)

    # Levels are derived from real candle prices of this series.
    assert res["levels"] == {"entry": 1.1016, "invalidation": 1.0994, "target": 1.1032}
    prices = {round(float(c[k]), 6) for c in m15 for k in ("open", "high", "low", "close")}
    assert round(res["levels"]["invalidation"], 6) in prices  # sweep-bar low
    assert round(res["levels"]["target"], 6) in prices  # real swing/pool high

    chain = res["chain"]
    assert chain["sweep_index"] == 15
    assert chain["displacement_index"] == chain["mss_index"] == 16
    assert chain["fvg_confirmed_index"] == 17

    ctx = res["context"]
    assert ctx == {
        "h1_bias": "BULLISH",
        "m5_bias": "BULLISH",
        "m5_blocks": False,
        "h1_conflict": False,
    }


def test_bearish_golden_completes_sell():
    m15 = g.golden_bearish_m15()
    res = evaluate_primary_setup(
        m15, g.golden_bearish_m1(), g.golden_bearish_m5(), g.golden_bearish_h1()
    )

    assert res["direction"] == "bearish"
    assert res["decision"] == "SELL"
    assert res["complete"] is True
    assert res["blocked_by"] == []
    assert all(s["status"] == "satisfied" for s in res["steps"])
    assert res["levels"] == {
        "entry": pytest.approx(2.2 - 1.1016),
        "invalidation": pytest.approx(2.2 - 1.0994),
        "target": pytest.approx(2.2 - 1.1032),
    }
    assert res["chain"]["sweep_index"] == 15


def test_step_chronology_is_strictly_non_decreasing_and_never_future():
    for build in (
        lambda: (_bullish(), "BUY"),
        lambda: ((g.golden_bearish_m15(), g.golden_bearish_m1(),
                  g.golden_bearish_m5(), g.golden_bearish_h1()), "SELL"),
    ):
        (m15, m1, m5, h1), decision = build()
        res = evaluate_primary_setup(m15, m1, m5, h1)
        assert res["decision"] == decision
        times = [_parse(s["time"]) for s in res["steps"]]
        assert all(t is not None for t in times)
        assert times == sorted(times), "checklist must be chronological"
        as_of = _parse(res["as_of"])
        # No step may reference a moment after the series end (no look-ahead).
        assert all(t <= as_of for t in times)
        # The bias must precede the sweep which precedes displacement <= MSS
        # < FVG < retest < M1 (equal times only where the same bar did it).
        assert times[0] <= times[1] <= times[2] <= times[3]
        assert times[3] <= times[4] <= times[5] <= times[6]


def test_no_repainting_across_prefixes():
    """A decision, once taken from a prefix, never disappears as bars arrive."""
    m15_full, m1_full, m5_full, h1_full = _bullish()
    decisions = []
    for k in range(len(m15_full)):
        last = m15_full[k]["time"]
        m1 = [c for c in m1_full if c["time"] <= last]
        m5 = [c for c in m5_full if c["time"] <= last]
        h1 = [c for c in h1_full if c["time"] <= last]
        res = evaluate_primary_setup(m15_full[: k + 1], m1, m5, h1)
        # no future leakage: no step time may exceed the prefix's last bar
        for s in res["steps"]:
            if s["time"]:
                assert s["time"] <= last, f"step {s['key']} looks ahead at k={k}"
        decisions.append(res["decision"])

    # The retest bar (18) and M1 pattern arrive later: prefixes before them
    # can never decide.
    assert decisions[:18] == ["WAIT"] * 18
    # No repaint: WAIT may only appear before the first non-WAIT decision.
    first_action = next((i, d) for i, d in enumerate(decisions) if d != "WAIT")
    assert all(d == first_action[1] for d in decisions[first_action[0]:])
    assert decisions[-1] == "BUY"


# --- WAIT fallbacks ----------------------------------------------------------


def test_ranging_market_is_wait_with_no_levels():
    res = evaluate_primary_setup(
        g.golden_ranging_m15(),
        g.golden_ranging_m1(),
        g.golden_ranging_m5(),
        g.golden_ranging_h1(),
    )
    assert res["direction"] is None
    assert res["decision"] == "WAIT"
    assert res["complete"] is False
    assert res["chain"] is None
    assert res["levels"] == {"entry": None, "invalidation": None, "target": None}
    assert res["blocked_by"] == ["bias_confirmed"]  # first unresolved requirement
    assert all(s["status"] == "missing" for s in res["steps"])
    assert all(s["time"] is None for s in res["steps"])


def test_missing_sweep_never_starts_a_chain():
    m1, m5, h1 = g.golden_bullish_m1(), g.golden_bullish_m5(), g.golden_bullish_h1()
    res = evaluate_primary_setup(g.golden_invalid_no_sweep(), m1, m5, h1)
    assert res["decision"] == "WAIT"
    assert res["chain"] is None
    assert set(res["blocked_by"]) == set(STEP_KEYS)
    steps = _steps_by_key(res)
    assert steps["liquidity_swept"]["status"] == "missing"
    assert steps["liquidity_swept"]["detail"] == "no sweep of the expected side"
    # the other signals still exist and are honestly shown, just unlinked
    assert steps["displacement_confirmed"]["time"] is not None
    assert steps["mss_confirmed"]["time"] is not None


def test_late_sweep_cannot_combine_with_earlier_signals():
    m15 = g.golden_invalid_chronology()
    # The early signals genuinely exist — the WAIT must come from chronology.
    assert any(e.direction == "bullish" for e in detect_displacement(m15))
    assert any(e.type == "MSS" and e.direction == "bullish" for e in detect_bos_choch_mss(m15))

    res = evaluate_primary_setup(
        m15, g.golden_bullish_m1(), g.golden_bullish_m5(), g.golden_bullish_h1()
    )
    assert res["decision"] == "WAIT"
    assert res["chain"] is None
    steps = _steps_by_key(res)
    # bias and the late sweep are satisfied, but nothing after the sweep links
    assert steps["bias_confirmed"]["status"] == "satisfied"
    assert steps["liquidity_swept"]["status"] == "satisfied"
    assert steps["displacement_confirmed"]["status"] == "missing"
    assert "displacement_confirmed" in res["blocked_by"]
    assert "mss_confirmed" in res["blocked_by"]
    assert "fvg_identified" in res["blocked_by"]


def test_invalidated_fvg_marks_step_invalid_not_satisfied():
    res = evaluate_primary_setup(
        g.golden_invalid_fvg(),
        g.golden_bullish_m1(),
        g.golden_bullish_m5(),
        g.golden_bullish_h1(),
    )
    assert res["decision"] == "WAIT"
    assert res["chain"] is None
    steps = _steps_by_key(res)
    assert [steps[k]["status"] for k in STEP_KEYS[:4]] == ["satisfied"] * 4
    assert steps["fvg_identified"]["status"] == "invalid"
    assert "invalidated" in steps["fvg_identified"]["detail"]
    assert set(res["blocked_by"]) == {"fvg_identified", "retest_confirmed", "m1_confirmed"}


def test_stale_chain_is_blocked_with_visible_progress():
    res = evaluate_primary_setup(
        g.golden_invalid_stale(),
        g.golden_bullish_m1(),
        g.golden_bullish_m5(),
        g.golden_bullish_h1(),
    )
    assert res["decision"] == "WAIT"
    assert res["stale"] is True
    assert res["chain"] is None
    steps = _steps_by_key(res)
    assert [steps[k]["status"] for k in STEP_KEYS[:5]] == ["satisfied"] * 5
    assert steps["retest_confirmed"]["status"] == "missing"
    assert steps["retest_confirmed"]["detail"] == "chain is stale"
    assert "stale_chain" in res["blocked_by"]
    # a stale setup never publishes levels
    assert res["levels"]["entry"] is None


def test_m1_contradiction_blocks():
    res = evaluate_primary_setup(
        g.golden_bullish_m15(),
        g.golden_bearish_m1(),  # opposite structure on the entry timeframe
        g.golden_bullish_m5(),
        g.golden_bullish_h1(),
    )
    assert res["decision"] == "WAIT"
    assert res["blocked_by"] == ["m1_confirmed"]
    steps = _steps_by_key(res)
    assert all(steps[k]["status"] == "satisfied" for k in STEP_KEYS[:6])
    assert steps["m1_confirmed"]["status"] == "missing"
    assert "BEARISH" in steps["m1_confirmed"]["detail"]


def test_m1_unavailable_is_unavailable_not_missing():
    res = evaluate_primary_setup(
        g.golden_bullish_m15(), [], g.golden_bullish_m5(), g.golden_bullish_h1()
    )
    assert res["decision"] == "WAIT"
    assert res["blocked_by"] == ["m1_confirmed"]
    assert _steps_by_key(res)["m1_confirmed"]["status"] == "unavailable"


def test_m5_conflict_blocks_even_a_complete_chain():
    res = evaluate_primary_setup(
        g.golden_bullish_m15(),
        g.golden_bullish_m1(),
        g.golden_bearish_m5(),  # decisive opposite validation timeframe
        g.golden_bullish_h1(),
    )
    assert res["decision"] == "WAIT"
    assert res["complete"] is False
    assert res["blocked_by"] == ["m5_conflict"]
    assert res["context"]["m5_bias"] == "BEARISH"
    assert res["context"]["m5_blocks"] is True
    # the chain and its levels are still reported — only the gate stops it
    assert all(s["status"] == "satisfied" for s in res["steps"])
    assert res["levels"]["entry"] is not None
    assert res["chain"] is None  # never published while blocked


def test_h1_conflict_is_context_only():
    res = evaluate_primary_setup(
        g.golden_bullish_m15(),
        g.golden_bullish_m1(),
        g.golden_bullish_m5(),
        g.golden_bearish_h1(),  # higher-timeframe disagreement: recorded only
    )
    assert res["context"]["h1_conflict"] is True
    assert res["context"]["m5_blocks"] is False
    assert res["decision"] == "BUY"


def test_empty_m15_returns_early_without_crashing():
    res = evaluate_primary_setup([], g.golden_bullish_m1())
    assert res["decision"] == "WAIT"
    assert res["blocked_by"] == ["bias_confirmed"]
    assert all(s["detail"] == "no M15 data" for s in res["steps"])


def test_missing_timeframes_do_not_block():
    res = evaluate_primary_setup(g.golden_bullish_m15(), g.golden_bullish_m1())
    assert res["decision"] == "BUY"
    assert res["context"]["m5_bias"] is None
    assert res["context"]["h1_bias"] is None
    assert res["context"]["m5_blocks"] is False
