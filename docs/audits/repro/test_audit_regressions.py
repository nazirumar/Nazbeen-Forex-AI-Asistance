"""Reproducible bug-documentation tests — AUDIT ARTIFACT, NOW REMEDIATED.

These tests demonstrated the confirmed defects found during the Phase 10 full
audit. **Phase 11A has since fixed every bug below**, and all 15 tests were
migrated into the application test packages where they now run as permanent
regressions:

    structure/tests/test_audit_regressions.py   (6 tests)
    marketdata/tests/test_audit_regressions.py  (2 tests)
    risk/tests/test_audit_regressions.py        (2 tests)
    analysis/tests/test_audit_regressions.py    (2 tests)
    backtesting/tests/test_audit_regressions.py (3 tests)

This file is kept as the historical audit index and still passes against the
fixed code. Two adaptations were made during migration (documented in
docs/PHASE_REPORTS/PHASE_11A.md):

1. The unknown-symbol test asserts the fixed API directly
   (``get_symbol_spec(...) is None`` + WAIT) instead of probing the shape of a
   spec object that no longer exists by design.
2. The backtest cost/outcome tests inject a deterministic signal strategy,
   because the corrected structure detectors form no FVG setups on smooth
   sawtooth data — an honest outcome, but it would leave the engine mechanics
   untested without an injected signal source.

Every test asserts the CORRECT behavior; the pre-fix actual value is noted in
each docstring.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from django.urls import reverse
from rest_framework.test import APIClient


def _c(i: int, o: float, h: float, l: float, cl: float) -> dict:
    return {
        "time": datetime(2026, 1, 1, 0, i, tzinfo=timezone.utc).isoformat(),
        "open": o,
        "high": h,
        "low": l,
        "close": cl,
        "volume": 10,
    }


# --------------------------------------------------------------------------
# Structure engine
# --------------------------------------------------------------------------

def test_bug_orderblocks_module_imports() -> None:
    """BUG H-1 (structure): `from __future__ import __annotations__` is invalid.

    Actual: SyntaxError: future feature __annotations__ is not defined.
    """
    import nazbeen_forex_ai.structure.orderblocks  # noqa: F401


def test_bug_fvg_gap_up_is_labelled_bullish() -> None:
    """BUG C-1 (structure): textbook bullish FVG (c0.high < c2.low) is labelled 'bearish'.

    Actual: [('bearish', [1.1002, 1.1006])].
    """
    from nazbeen_forex_ai.structure.fvg import detect_fvg

    gap_up = [
        _c(0, 1.1001, 1.1002, 1.0999, 1.1001),
        _c(1, 1.1001, 1.1010, 1.1000, 1.1009),
        _c(2, 1.1008, 1.1012, 1.1006, 1.1011),
    ]
    events = detect_fvg(gap_up)
    assert len(events) == 1
    assert events[0].direction == "bullish", f"expected bullish, got {events[0].direction}"
    assert events[0].levels == [1.1002, 1.1006]


def test_bug_fvg_gap_down_is_labelled_bearish() -> None:
    """BUG C-1 (structure): textbook bearish FVG (c0.low > c2.high) is labelled 'bullish'.

    Actual: [('bullish', [1.099, 1.11])].
    """
    from nazbeen_forex_ai.structure.fvg import detect_fvg

    gap_down = [
        _c(0, 1.1002, 1.1010, 1.1000, 1.1002),
        _c(1, 1.1001, 1.1002, 1.0996, 1.0997),
        _c(2, 1.0997, 1.0990, 1.0985, 1.0986),
    ]
    events = detect_fvg(gap_down)
    assert len(events) == 1
    assert events[0].direction == "bearish", f"expected bearish, got {events[0].direction}"


def test_bug_fvg_start_time_not_after_end_time() -> None:
    """BUG M-5 (structure): one branch emits start_time 2 bars AFTER end_time.

    Actual for gap-down fixture: start_time = T2, end_time = T0.
    """
    from nazbeen_forex_ai.structure.fvg import detect_fvg

    gap_down = [
        _c(0, 1.1002, 1.1010, 1.1000, 1.1002),
        _c(1, 1.1001, 1.1002, 1.0996, 1.0997),
        _c(2, 1.0997, 1.0990, 1.0985, 1.0986),
    ]
    for e in detect_fvg(gap_down):
        assert e.start_time <= e.end_time, f"start {e.start_time} > end {e.end_time}"


def test_bug_bos_detects_close_above_swing_high() -> None:
    """BUG C-2 (structure): detect_bos_choch_mss is a stub that always returns [].

    Fixture: confirmed swing high 1.1050 followed by a close at 1.1060 (clear break).
    Actual: [] — spec items BOS/CHOCH/MSS produce no output anywhere.
    """
    from nazbeen_forex_ai.structure.bos import detect_bos_choch_mss

    candles = [
        _c(0, 1.1010, 1.1020, 1.1005, 1.1015),
        _c(1, 1.1015, 1.1050, 1.1010, 1.1045),   # swing high 1.1050 (left=1.., right below)
        _c(2, 1.1045, 1.1048, 1.1030, 1.1035),
        _c(3, 1.1035, 1.1040, 1.1025, 1.1030),
        _c(4, 1.1030, 1.1062, 1.1028, 1.1060),   # close 1.1060 > swing high 1.1050
        _c(5, 1.1060, 1.1065, 1.1055, 1.1062),
        _c(6, 1.1062, 1.1070, 1.1058, 1.1066),
    ]
    events = detect_bos_choch_mss(candles)
    assert len(events) >= 1, "expected at least one BOS/CHOCH event, got []"


def test_bug_mtf_bias_bullish_on_rising_structure() -> None:
    """BUG H-4 (structure): mtf_bias returns the TYPE of the last swing, not structure.

    Fixture: rising highs + rising lows (textbook uptrend).
    Actual (traced): 'BEARISH' because the last confirmed swing is a high.
    """
    from nazbeen_forex_ai.structure.analysis import mtf_bias

    candles = [
        _c(0, 1.1000, 1.1010, 1.0990, 1.1005),
        _c(1, 1.1005, 1.1020, 1.1000, 1.1015),
        _c(2, 1.1015, 1.1005, 1.0985, 1.0990),
        _c(3, 1.0990, 1.0995, 1.0975, 1.0980),
        _c(4, 1.0980, 1.1030, 1.0990, 1.1025),
        _c(5, 1.1025, 1.1060, 1.1020, 1.1055),
        _c(6, 1.1055, 1.1075, 1.1040, 1.1070),
        _c(7, 1.1070, 1.1055, 1.1030, 1.1035),
        _c(8, 1.1035, 1.1045, 1.1025, 1.1040),
        _c(9, 1.1040, 1.1085, 1.1060, 1.1080),
    ]
    bias = mtf_bias([], candles, [], [])
    assert bias["M15"] == "BULLISH", f"expected BULLISH on rising structure, got {bias['M15']}"


# --------------------------------------------------------------------------
# Market data
# --------------------------------------------------------------------------

def test_bug_mock_tick_works_after_connect() -> None:
    """BUG M-4 (marketdata): MockMarketDataProvider.get_tick raises NameError: utcnow.

    `utcnow` is defined in providers.py but never imported in mock.py.
    Actual: NameError name 'utcnow' is not defined  (=> HTTP 500 in mock mode,
    which is the default on any machine without MT5, e.g. CI).
    """
    from nazbeen_forex_ai.marketdata.mock import MockMarketDataProvider

    p = MockMarketDataProvider()
    p.connect()
    tick = p.get_tick("EURUSD")
    assert tick["mode"] == "mock"


def test_bug_mock_rejects_unknown_timeframe() -> None:
    """BUG M6 (marketdata): unknown timeframe silently returns M15 candles
    while the API echoes the requested timeframe label (mislabeling).

    Actual: returns 10 candles spaced 15 minutes for timeframe='M30'.
    """
    from nazbeen_forex_ai.marketdata.mock import MockMarketDataProvider

    p = MockMarketDataProvider()
    p.connect()
    with pytest.raises(Exception):
        p.get_candles(symbol="EURUSD", timeframe="M30", count=10)


# --------------------------------------------------------------------------
# Risk
# --------------------------------------------------------------------------

def test_bug_position_size_eurusd_exact() -> None:
    """BUG H-2 (risk): pip value divides by entry for USD-quoted pairs.

    $10,000 balance, 1% risk (= $100), 10-pip stop on EURUSD must be 1.00 lot
    (100 / (10 pips * $10/pip/lot)). Actual: 1.1 lots (+10% over-risk; +27% at 1.27 on GBPUSD).
    """
    from nazbeen_forex_ai.risk.calculations import get_symbol_spec, position_size

    spec = get_symbol_spec("EURUSD")
    lots = position_size(account_balance=10000.0, risk_percent=1.0, entry=1.1000, sl=1.0990, symbol_spec=spec)
    assert lots == 1.0, f"expected 1.0 lots, got {lots}"


def test_bug_unknown_symbol_yields_wait_not_fabricated_spec() -> None:
    """BUG M-2 (risk): symbols outside the 7-major table silently got EURUSD-like specs.

    Actual (pre-fix): XAUUSD (contract 100, XAU pip 0.1) was sized with
    contract_size=100000, pip 0.0001 -> fabricated contract data.
    Fixed behavior (Phase 11A): get_symbol_spec returns None and the trade plan
    returns WAIT — asserted below in the fixed-API form.
    """
    from nazbeen_forex_ai.risk.calculations import get_symbol_spec, position_size
    from nazbeen_forex_ai.risk.scenarios import evaluate_trade_plan

    spec = get_symbol_spec("XAUUSD")
    assert spec is None, f"XAUUSD must be rejected (None), got {spec!r}"
    assert position_size(10000.0, 1.0, 2000.0, 1999.0, spec) == 0.0
    res = evaluate_trade_plan(
        bias="BULLISH", entry=2000.0, sl=1990.0, tp=2030.0,
        spread_pips=0.5, symbol="XAUUSD", account_balance=10000.0,
    )
    assert res.decision == "WAIT"


# --------------------------------------------------------------------------
# Analysis / upload security
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_bug_upload_rejects_non_image_content() -> None:
    """BUG F-1/F-2 (analysis): view swallows ValidationError 'to be permissive for tests'.

    Upload of b'not an image' named x.png with Content-Type image/png must be 400.
    Actual: 201 (validation dead; content never verified — validators.py ends in `pass`).
    """
    from io import BytesIO

    from django.contrib.auth import get_user_model

    client = APIClient()
    get_user_model().objects.create_user("repro_up", password="Repro-2026!")
    client.force_authenticate(user=get_user_model().objects.get(username="repro_up"))
    resp = client.post(
        reverse("analysis:upload"),
        {"image": (BytesIO(b"not an image at all"), "x.png")},
        format="multipart",
    )
    assert resp.status_code == 400, f"expected 400, got {resp.status_code}"


@pytest.mark.django_db
def test_bug_upload_rejects_oversized_file() -> None:
    """BUG F-1 (analysis): 5MB validator exists but is bypassed.

    Actual: a 6MB payload is accepted (201); correct: 400.
    """
    from io import BytesIO

    from django.contrib.auth import get_user_model

    client = APIClient()
    get_user_model().objects.create_user("repro_big", password="Repro-2026!")
    client.force_authenticate(user=get_user_model().objects.get(username="repro_big"))
    payload = BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * (6 * 1024 * 1024))
    resp = client.post(
        reverse("analysis:upload"),
        {"image": (payload, "big.png")},
        format="multipart",
    )
    assert resp.status_code == 400, f"expected 400 for 6MB file, got {resp.status_code}"


# --------------------------------------------------------------------------
# Backtesting
# --------------------------------------------------------------------------

def _oscillating_candles(n: int = 240) -> list[dict]:
    out = []
    for i in range(n):
        base = 1.1000 + 0.01 * ((i % 20) / 20.0) * (1 if (i // 20) % 2 == 0 else -1)
        candle = _c(0, base, base + 0.0015, base - 0.0015, base + 0.0005)
        # Phase 11C fixture repair (documented, not a weakening): the old
        # `_c(i % 60, ...)` cycling fabricated out-of-order timestamps — the
        # exact defect the new walk-forward chronology validation rejects.
        # Timestamps now strictly increase; no assertion changed, prices and
        # counts untouched: test strength identical.
        candle["time"] = (
            datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=i)
        ).isoformat()
        out.append(candle)
    return out


def _deterministic_strategy(window):
    """Migration adaptation: the corrected structure detectors form no FVG
    setups on smooth sawtooth data, so an injected signal source is used to
    exercise the engine's cost/outcome mechanics directly."""
    if len(window) % 12 != 0:
        return "WAIT"
    return "BUY" if (len(window) // 12) % 2 == 0 else "SELL"


def test_bug_backtest_applies_cost_parameters() -> None:
    """BUG H-1 (backtesting): commission/slippage/spread params are accepted but never applied.

    Actual (pre-fix): Trade.commission/.slippage/.spread_cost stay 0.0 for every trade
    (engine.py never references the parameters after the signature).
    """
    from nazbeen_forex_ai.backtesting.engine import run_backtest

    result = run_backtest(
        _oscillating_candles(),
        commission_pips=5.0,
        slippage_pips=1.0,
        spread_pips=2.0,
        strategy=_deterministic_strategy,
    )
    assert result.total_trades > 0, "engine generated no trades (itself a finding)"
    assert any(t.commission > 0 or t.slippage > 0 or t.spread_cost > 0 for t in result.trades), (
        "cost parameters were ignored: every trade has zero cost"
    )


def test_bug_backtest_outcomes_are_not_dummy() -> None:
    """BUG C-1 (backtesting): pnl is hardcoded to 1.0 ('dummy outcome').

    Actual (pre-fix): every trade wins => win_rate == 100%, gross_loss == 0, drawdown == 0 —
    fabricated performance figures (MASTER_SPEC §7).
    """
    from nazbeen_forex_ai.backtesting.engine import run_backtest

    result = run_backtest(_oscillating_candles(), strategy=_deterministic_strategy)
    assert result.total_trades > 0, "engine generated no trades (itself a finding)"
    assert result.gross_loss > 0 or result.win_rate < 100.0, (
        f"impossible performance: win_rate={result.win_rate}%, gross_loss={result.gross_loss} (pnl hardcoded to 1.0)"
    )


def test_bug_walkforward_overall_is_aggregate_of_windows() -> None:
    """BUG M2 (backtesting): `overall` re-runs the engine on the last test window
    instead of aggregating window results (all_trades is dead code).

    Actual (pre-fix): overall.total_trades == trades(candles[-test_size:]) != sum(window trades).
    A deterministic strategy is injected so the aggregation is exercised with
    real trades rather than a vacuous 0 == 0.
    """
    from nazbeen_forex_ai.backtesting.walkforward import walk_forward

    candles = _oscillating_candles(500)
    wf = walk_forward(candles, train_size=200, test_size=100, step=100, strategy=_deterministic_strategy)
    window_total = sum(w["result"].total_trades for w in wf.windows)
    assert window_total > 0
    assert wf.overall.total_trades == window_total, (
        f"overall={wf.overall.total_trades} != sum(windows)={window_total} — 'overall' is not an aggregation"
    )
