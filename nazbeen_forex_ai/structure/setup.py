"""Primary trading model: a chronological state machine (MASTER_SPEC §3.D).

The model evaluates the seven-step ICT/SMC checklist in order and only ever
reports a `BUY`/`SELL` decision when **one continuous chronological chain**
exists inside a bounded window. Every step carries the real UTC timestamp of
the candle that confirmed it; unrelated historical signals can never combine
into a setup, and any missing, contradictory or stale confirmation yields
`WAIT`.

Bullish sequence (bearish is the exact mirror):

1. ``bias_confirmed``      — M15 structure bias is BULLISH **as of the sweep
                              bar** (the bias must already exist when the
                              liquidity is taken; evaluated on the series
                              truncated at the sweep bar, never later bars).
2. ``liquidity_swept``      — a confirmed SSL pool was wicked through and the
                              bar closed back above it (a sweep).
3. ``displacement_confirmed`` — a bullish displacement candle at/after the sweep.
4. ``mss_confirmed``        — a bullish MSS (counter-trend break with
                              displacement) at/after the displacement.
5. ``fvg_identified``       — a bullish FVG confirmed after the MSS that has
                              **not** been invalidated (close beyond its far
                              edge).
6. ``retest_confirmed``     — price traded back into that FVG after its
                              confirmation and the gap is still valid.
7. ``m1_confirmed``         — M1 structure bias agrees and a bullish M1 entry
                              pattern (engulfing/rejection) occurred at or
                              after the retest, fresh in the M1 series.

Gates (never checklist steps, always reported):

- **H1 context** — recorded in ``context``; a decisive opposite H1 bias is
  reported as ``h1_conflict`` but does not block (spec: H1 is context).
- **M5 validation** — a decisive opposite M5 bias blocks the setup
  (``m5_conflict``): contradictory confirmation ⇒ WAIT.
- **Freshness/staleness** — the chain must end within
  ``max_chain_span_bars`` of the last M15 bar and span at most that many bars
  from sweep to retest; stale ⇒ WAIT.
- **Target** — invalidation is the sweep-bar extreme (a real candle price);
  the target is the nearest opposing confirmed liquidity/SR/swing level beyond
  the entry (the FVG midpoint). If no such level exists the setup cannot be
  completed (``no_target``) — a price is never invented.

All detections reuse the Phase 11E detectors; nothing here reads beyond the
last candle provided (no look-ahead) and every timestamp is a real candle time
(no backdating).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from nazbeen_forex_ai.structure.bos import detect_bos_choch_mss
from nazbeen_forex_ai.structure.displacement import detect_displacement
from nazbeen_forex_ai.structure.fvg import annotate_fvg_lifecycle, detect_fvg
from nazbeen_forex_ai.structure.liquidity import detect_liquidity, detect_sweeps
from nazbeen_forex_ai.structure.patterns import detect_engulfing, detect_rejection
from nazbeen_forex_ai.structure.analysis import swing_bias

MODEL_NAME = "ict_primary_setup_v1"

# Seconds per bar for the M15 chain window.
_M15_SECONDS = 900

# Checklist steps in strict chronological order with display labels.
STEPS: tuple[tuple[str, str], ...] = (
    ("bias_confirmed", "Bias confirmed"),
    ("liquidity_swept", "Liquidity swept"),
    ("displacement_confirmed", "Displacement confirmed"),
    ("mss_confirmed", "MSS confirmed"),
    ("fvg_identified", "FVG identified"),
    ("retest_confirmed", "Retest confirmed"),
    ("m1_confirmed", "M1 entry confirmed"),
)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(raw: Any) -> Optional[datetime]:
    """Parse an ISO string / datetime into an aware UTC datetime (or None)."""
    if isinstance(raw, str):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    elif isinstance(raw, datetime):
        dt = raw
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _step(key: str, status: str, time: Optional[datetime] = None, detail: str = "") -> Dict[str, Any]:
    label = dict(STEPS)[key]
    return {
        "key": key,
        "label": label,
        "status": status,  # satisfied | missing | invalid | unavailable
        "time": _iso(time),
        "detail": detail,
    }


def _empty_steps(detail: str = "no directional evidence") -> List[Dict[str, Any]]:
    return [_step(k, "missing", None, detail) for k, _ in STEPS]


def evaluate_primary_setup(
    candles_m15: list[Any],
    candles_m1: list[Any],
    candles_m5: Optional[list[Any]] = None,
    candles_h1: Optional[list[Any]] = None,
    *,
    tolerance: float = 0.0005,
    swing_left: int = 2,
    swing_right: int = 2,
    max_chain_span_bars: int = 96,
    m1_freshness_bars: int = 120,
    displacement_factor: float = 1.5,
    atr_length: int = 14,
    body_ratio: float = 0.6,
    fvg_threshold_pips: float = 0.1,
    min_body_ratio: float = 1.0,
) -> Dict[str, Any]:
    """Evaluate the chronological setup; see the module docstring for the rules.

    Returns a JSON-safe dict:

    - ``direction``: "bullish"/"bearish" (None when there is no directional
      evidence at all), ``decision``: "BUY"/"SELL" only for a complete fresh
      chain, otherwise "WAIT"; ``complete`` mirrors that.
    - ``steps``: the seven checklist items with status/time/detail.
    - ``blocked_by``: step keys (plus ``stale_chain``/``m5_conflict``/
      ``no_target``) that must be resolved before a decision can exist.
    - ``chain``: the actual linked events (indices + UTC times) when one was
      found — never assembled from unrelated signals.
    - ``levels``: entry (FVG midpoint), invalidation (sweep-bar extreme),
      target (nearest opposing confirmed level beyond entry) — all derived
      from real candle prices; missing values stay ``None``.
    """
    result: Dict[str, Any] = {
        "model": MODEL_NAME,
        "direction": None,
        "decision": "WAIT",
        "complete": False,
        "stale": False,
        "steps": _empty_steps(),
        "blocked_by": [],
        "chain": None,
        "levels": {"entry": None, "invalidation": None, "target": None},
        "context": {
            "h1_bias": None,
            "m5_bias": None,
            "m5_blocks": False,
            "h1_conflict": False,
        },
        "as_of": None,
    }
    if not candles_m15:
        result["blocked_by"] = ["bias_confirmed"]
        result["steps"] = _empty_steps("no M15 data")
        return result

    # --- shared detections on the M15 series --------------------------------
    pools = detect_liquidity(
        candles_m15, tolerance=tolerance, swing_left=swing_left, swing_right=swing_right
    )
    sweeps = detect_sweeps(candles_m15, liquidity=pools, tolerance=tolerance)
    disps = detect_displacement(
        candles_m15, factor=displacement_factor, atr_length=atr_length, body_ratio=body_ratio
    )
    mss_events = [
        e
        for e in detect_bos_choch_mss(candles_m15)
        if e.type == "MSS"
    ]
    fvgs_raw = detect_fvg(candles_m15, threshold_pips=fvg_threshold_pips)
    fvgs = annotate_fvg_lifecycle(candles_m15, fvgs_raw)

    as_of = None
    if candles_m15:
        last = candles_m15[-1]
        as_of = last.get("time") if isinstance(last, dict) else getattr(last, "time", None)
    result["as_of"] = as_of if isinstance(as_of, str) else _iso(as_of)

    # --- direction ----------------------------------------------------------
    bias_full = swing_bias(candles_m15)
    if bias_full == "BULLISH":
        direction = "bullish"
    elif bias_full == "BEARISH":
        direction = "bearish"
    elif sweeps:
        direction = sweeps[-1].direction  # freshest sweep is the only evidence
    else:
        direction = None

    # context (H1 non-blocking, M5 blocking when decisive opposite)
    result["context"]["h1_bias"] = swing_bias(candles_h1) if candles_h1 else None
    result["context"]["m5_bias"] = swing_bias(candles_m5) if candles_m5 else None

    if direction is None:
        result["blocked_by"] = ["bias_confirmed"]
        result["steps"] = _empty_steps("M15 bias NEUTRAL and no sweep evidence")
        return result

    result["direction"] = direction
    bull = direction == "bullish"

    m5_bias = result["context"]["m5_bias"]
    if m5_bias in ("BULLISH", "BEARISH"):
        m5_opposite = (m5_bias == "BULLISH") != bull
        result["context"]["m5_blocks"] = m5_opposite
    h1_bias = result["context"]["h1_bias"]
    if h1_bias in ("BULLISH", "BEARISH"):
        result["context"]["h1_conflict"] = (h1_bias == "BULLISH") != bull

    # --- greedy chronological chain -----------------------------------------
    d_sweeps = [e for e in sweeps if e.direction == direction]
    d_disps = [e for e in disps if e.direction == direction]
    d_mss = [e for e in mss_events if e.direction == direction]
    valid_fvgs = [
        e
        for e in fvgs
        if e.direction == direction
        and (e.details or {}).get("lifecycle", {}).get("state") != "invalidated"
        and (e.details or {}).get("confirmed_index") is not None
    ]

    # Every sweep gets its own attempt record: links found + the first
    # requirement that failed. Attempts are never merged across sweeps, so a
    # checklist can only ever show one sweep's own chronological evidence.
    attempts: List[Dict[str, Any]] = []

    def _attempt(
        sweep: Any,
        fail: Optional[Dict[str, Any]],
        disp: Any = None,
        mss: Any = None,
        fvg: Any = None,
        retest_time: Optional[datetime] = None,
        fvg_time: Optional[datetime] = None,
        stale: bool = False,
    ) -> None:
        attempts.append(
            {
                "sweep": sweep,
                "disp": disp,
                "mss": mss,
                "fvg": fvg,
                "retest_time": retest_time,
                "fvg_time": fvg_time,
                "failure": fail,
                "stale": stale,
            }
        )

    # Step 1: bias as of the sweep bar (chronological: bias precedes the sweep).
    for sweep in d_sweeps:
        sweep_idx = int(sweep.index)
        prefix = candles_m15[: sweep_idx + 1]
        bias_asof = swing_bias(prefix)
        if bias_asof != ("BULLISH" if bull else "BEARISH"):
            failure = {
                "key": "bias_confirmed",
                "status": "missing",
                "detail": f"M15 bias as of the sweep bar is {bias_asof}, not required",
            }
            _attempt(sweep, failure)
            continue

        disp = next((e for e in d_disps if int(e.index) >= sweep_idx), None)
        if disp is None:
            failure = {
                "key": "displacement_confirmed",
                "status": "missing",
                "detail": "no qualifying displacement after the sweep",
            }
            _attempt(sweep, failure)
            continue
        mss = next((e for e in d_mss if int(e.index) >= int(disp.index)), None)
        if mss is None:
            failure = {
                "key": "mss_confirmed",
                "status": "missing",
                "detail": "no MSS after the displacement",
            }
            _attempt(sweep, failure, disp=disp)
            continue
        fvg = next(
            (
                e
                for e in valid_fvgs
                if int(e.details["confirmed_index"]) >= int(mss.index)
            ),
            None,
        )
        if fvg is None:
            # Distinguish "exists but invalidated" from "does not exist".
            invalidated_here = any(
                e.direction == direction
                and int(e.details.get("confirmed_index", -1)) >= int(mss.index)
                for e in fvgs
                if (e.details or {}).get("confirmed_index") is not None
            )
            failure = {
                "key": "fvg_identified",
                "status": "invalid" if invalidated_here else "missing",
                "detail": (
                    "no valid FVG after the MSS (later gaps were invalidated)"
                    if invalidated_here
                    else "no FVG confirmed after the MSS"
                ),
            }
            _attempt(sweep, failure, disp=disp, mss=mss)
            continue
        lifecycle = (fvg.details or {}).get("lifecycle", {})
        if lifecycle.get("state") not in ("retested", "mitigated"):
            failure = {
                "key": "retest_confirmed",
                "status": "missing",
                "detail": "price never traded back into the FVG",
            }
            _attempt(sweep, failure, disp=disp, mss=mss, fvg=fvg)
            continue
        retest_time = _parse_time((lifecycle or {}).get("retest_time"))
        if retest_time is None:
            failure = {
                "key": "retest_confirmed",
                "status": "missing",
                "detail": "retest timestamp unreadable",
            }
            _attempt(sweep, failure, disp=disp, mss=mss, fvg=fvg)
            continue
        fvg_time = fvg.confirmed_at

        # Chain window: sweep → retest span, and freshness of the chain end.
        sweep_time = sweep.confirmed_at
        span_bars = (retest_time - sweep_time).total_seconds() / _M15_SECONDS
        if span_bars > max_chain_span_bars:
            failure = {"key": "liquidity_swept", "status": "missing", "detail": "chain too long"}
            _attempt(sweep, failure, disp=disp, mss=mss, fvg=fvg, retest_time=retest_time, fvg_time=fvg_time)
            continue
        last_time = _parse_time(result["as_of"])
        if last_time is not None and (last_time - retest_time).total_seconds() / _M15_SECONDS > max_chain_span_bars:
            failure = {"key": "retest_confirmed", "status": "missing", "detail": "chain is stale"}
            # Stale chain: remember it for the checklist but keep looking for
            # a fresher one (stale setups can never decide the outcome).
            _attempt(
                sweep,
                failure,
                disp=disp,
                mss=mss,
                fvg=fvg,
                retest_time=retest_time,
                fvg_time=fvg_time,
                stale=True,
            )
            continue

        # Complete walk (retest fresh): recorded with no failure — M1 is
        # checked only on the freshest such candidate below.
        _attempt(
            sweep,
            None,
            disp=disp,
            mss=mss,
            fvg=fvg,
            retest_time=retest_time,
            fvg_time=fvg_time,
        )

    # --- M1 confirmation helper ---------------------------------------------
    def m1_check(retest_time: Optional[datetime]) -> tuple[bool, Optional[datetime], str]:
        if not candles_m1:
            return False, None, "M1 data unavailable"
        m1_bias = swing_bias(candles_m1)
        if m1_bias != ("BULLISH" if bull else "BEARISH"):
            return False, None, f"M1 structure bias is {m1_bias}"
        if retest_time is None:
            return False, None, "requires a confirmed retest"
        last_m1_time: Optional[datetime] = None
        last = candles_m1[-1]
        raw = last.get("time") if isinstance(last, dict) else getattr(last, "time", None)
        last_m1_time = _parse_time(raw)

        patterns: List[Any] = []
        if bull:
            patterns += detect_engulfing(candles_m1, min_body_ratio=min_body_ratio)
            patterns += detect_rejection(candles_m1)
        else:
            patterns += detect_engulfing(candles_m1, min_body_ratio=min_body_ratio)
            patterns += detect_rejection(candles_m1)
        candidates = [p for p in patterns if p.direction == direction]
        fresh = []
        for p in candidates:
            if p.confirmed_at is None or p.confirmed_at < retest_time:
                continue
            if last_m1_time is not None and p.confirmed_at is not None:
                age_bars = (last_m1_time - p.confirmed_at).total_seconds() / 60.0
                if age_bars > m1_freshness_bars:
                    continue
            fresh.append(p)
        if not fresh:
            return False, None, "no fresh M1 entry pattern at/after the retest"
        fresh.sort(key=lambda p: p.confirmed_at)
        return True, fresh[-1].confirmed_at, "M1 bias agrees with a fresh entry pattern"

    # --- select the outcome ---------------------------------------------------
    # Freshest complete chain wins (stale attempts never decide the outcome).
    complete_chain: Optional[Dict[str, Any]] = None
    partial_display: Optional[Dict[str, Any]] = None
    fresh_ok = [a for a in attempts if a["failure"] is None]
    if fresh_ok:
        # Prefer the chain whose retest is most recent.
        fresh_ok.sort(key=lambda a: a["retest_time"])
        candidate = fresh_ok[-1]
        ok, m1_time, m1_detail = m1_check(candidate["retest_time"])
        if ok:
            candidate["m1_time"] = m1_time
            complete_chain = candidate
        else:
            status = "unavailable" if not candles_m1 else "missing"
            m1_failure = {"key": "m1_confirmed", "status": status, "detail": m1_detail}
            candidate["m1_failure"] = m1_failure
            candidate["failure"] = m1_failure
            # still the best partial chain for the checklist display
            partial_display = candidate

    if complete_chain is None and partial_display is None:
        # Best partial attempt: the walk that got the furthest (ties → the
        # earliest sweep, so the display is deterministic).

        def _reach(a: Dict[str, Any]) -> int:
            fail = a.get("failure")
            if not fail:
                return len(STEPS)
            return next(
                (i for i, (k, _) in enumerate(STEPS) if k == fail.get("key")),
                0,
            )

        ranked = sorted(attempts, key=lambda a: -_reach(a))
        partial_display = ranked[0] if ranked else None

    # The failure shown by the checklist belongs to the selected outcome only.
    failure: Dict[str, Any] = (partial_display or {}).get("failure") or {}
    result["stale"] = bool(partial_display is not None and partial_display.get("stale"))

    # When no chain exists at all, the failure recorded by the greedy walk is
    # the honest "first requirement that could not be met".
    best_partial: Optional[Dict[str, Any]] = complete_chain or partial_display

    # --- checklist assembly --------------------------------------------------
    steps: List[Dict[str, Any]] = []
    blocked: List[str] = []

    if complete_chain is None and best_partial is None:
        # No chain even started: evaluate the first two requirements from the
        # freshest evidence so the checklist explains where it stopped.
        c = complete_chain or {}
        steps.append(
            _step(
                "bias_confirmed",
                "missing",
                None,
                failure.get("detail") or "M15 bias not confirmed as of a sweep",
            )
        )
        # remaining steps: own-evidence evaluation (never "satisfied")
        if not d_sweeps:
            steps.append(_step("liquidity_swept", "missing", None, "no sweep of the expected side"))
        else:
            steps.append(
                _step(
                    "liquidity_swept",
                    "missing",
                    d_sweeps[-1].confirmed_at,
                    "sweep exists but no chronological setup follows it",
                )
            )
        steps.append(
            _step(
                "displacement_confirmed",
                "missing",
                d_disps[-1].confirmed_at if d_disps else None,
                "no displacement linked to this setup",
            )
        )
        steps.append(
            _step(
                "mss_confirmed",
                "missing",
                d_mss[-1].confirmed_at if d_mss else None,
                "no MSS linked to this setup",
            )
        )
        if not candles_m1:
            steps.append(_step("m1_confirmed", "unavailable", None, "M1 data unavailable"))
        else:
            steps.append(_step("m1_confirmed", "missing", None, "requires a confirmed retest"))
        # fvg / retest placeholders keep the fixed order:
        fvg_step = _step(
            "fvg_identified",
            "invalid" if any(
                (e.details or {}).get("lifecycle", {}).get("state") == "invalidated"
                for e in fvgs
                if e.direction == direction
            )
            else "missing",
            None,
            failure.get("detail") if failure.get("key") == "fvg_identified" else "no linked FVG",
        )
        retest_step = _step("retest_confirmed", "missing", None, "requires a linked FVG")
        # order: bias, liquidity, displacement, mss, fvg, retest, m1
        steps = [steps[0], steps[1], steps[2], steps[3], fvg_step, retest_step, steps[4]]
        blocked = [s["key"] for s in steps if s["status"] != "satisfied"]
    else:
        c = best_partial or {}
        sweep = c.get("sweep")
        disp = c.get("disp")
        mss = c.get("mss")
        fvg = c.get("fvg")
        # Links actually found by this attempt (partial attempts lack the tail).
        chain_steps = {
            "bias_confirmed": sweep is not None,  # passed the as-of-sweep gate
            "liquidity_swept": sweep is not None,
            "displacement_confirmed": disp is not None,
            "mss_confirmed": mss is not None,
            "fvg_identified": fvg is not None,
            "retest_confirmed": c.get("retest_time") is not None,
            "m1_confirmed": complete_chain is not None,
        }
        failed_key = failure.get("key") if complete_chain is None else None
        fail_index = next((i for i, (k, _) in enumerate(STEPS) if k == failed_key), len(STEPS))

        # bias evidence: last swing at/before the sweep bar
        prefix_sw_time: Optional[datetime] = None
        from nazbeen_forex_ai.structure.swings import detect_swings as _ds
        from nazbeen_forex_ai.structure.types import candles_to_df as _cdf

        try:
            if sweep is not None:
                pre_sw = _ds(_cdf(candles_m15[: int(sweep.index) + 1]), left=1, right=1)
                if pre_sw:
                    prefix_sw_time = pre_sw[-1].time
        except Exception:  # pragma: no cover - display-only fallback
            prefix_sw_time = None

        times: Dict[str, Optional[datetime]] = {
            "bias_confirmed": prefix_sw_time,
            "liquidity_swept": sweep.confirmed_at if sweep is not None else None,
            "displacement_confirmed": disp.confirmed_at if disp is not None else None,
            "mss_confirmed": mss.confirmed_at if mss is not None else None,
            "fvg_identified": fvg.confirmed_at if fvg is not None else None,
            "retest_confirmed": c.get("retest_time"),
            "m1_confirmed": c.get("m1_time"),
        }
        details: Dict[str, str] = {
            "bias_confirmed": f"M15 structure bias {'BULLISH' if bull else 'BEARISH'} as of the sweep bar",
            "liquidity_swept": f"{(sweep.details or {}).get('kind')} swept and closed back"
            if sweep is not None
            else "no sweep of the expected side",
            "displacement_confirmed": "body >= factor x ATR with dominant body",
            "mss_confirmed": "counter-trend break with displacement",
            "fvg_identified": f"FVG state {(fvg.details or {}).get('lifecycle', {}).get('state')}"
            if fvg is not None
            else "no FVG linked to this setup",
            "retest_confirmed": "price returned into the FVG while it stayed valid",
            "m1_confirmed": c.get("m1_failure", {}).get("detail", "M1 agrees with a fresh pattern")
            if "m1_time" not in c
            else "M1 bias agrees with a fresh entry pattern",
        }
        for i, (key, _label) in enumerate(STEPS):
            if chain_steps.get(key) and i < fail_index:
                steps.append(_step(key, "satisfied", times.get(key), details.get(key, "")))
            elif key == failed_key:
                steps.append(
                    _step(key, failure.get("status", "missing"), times.get(key), failure.get("detail", ""))
                )
            elif key == "m1_confirmed" and complete_chain is None and "m1_failure" in c:
                steps.append(
                    _step(
                        key,
                        c["m1_failure"].get("status", "missing"),
                        None,
                        c["m1_failure"].get("detail", ""),
                    )
                )
            elif not candles_m1 and key == "m1_confirmed":
                steps.append(_step(key, "unavailable", None, "M1 data unavailable"))
            else:
                steps.append(_step(key, "missing", None, "requires the previous step confirmed"))

        blocked = [s["key"] for s in steps if s["status"] != "satisfied"]

    # --- gates ---------------------------------------------------------------
    if result["stale"]:
        blocked.append("stale_chain")
    if result["context"]["m5_blocks"]:
        blocked.append("m5_conflict")

    # --- levels (only from a complete chain) ---------------------------------
    if complete_chain is not None:
        sweep = complete_chain["sweep"]
        fvg = complete_chain["fvg"]
        levels = fvg.levels or []
        entry = (float(levels[0]) + float(levels[1])) / 2.0 if len(levels) >= 2 else None
        bar = candles_m15[int(sweep.index)]
        invalidation = float(bar["low"]) if bull else float(bar["high"])
        target = _find_target(
            candles_m15, pools, entry, bull, tolerance=tolerance, swing_left=swing_left,
            swing_right=swing_right,
        )
        result["levels"] = {"entry": entry, "invalidation": invalidation, "target": target}
        if target is None:
            blocked.append("no_target")

    result["steps"] = steps
    result["blocked_by"] = blocked

    if complete_chain is not None and not blocked:
        result["complete"] = True
        result["decision"] = "BUY" if bull else "SELL"
        ch = complete_chain
        result["chain"] = {
            "sweep_index": int(ch["sweep"].index),
            "sweep_time": _iso(ch["sweep"].confirmed_at),
            "displacement_index": int(ch["disp"].index),
            "displacement_time": _iso(ch["disp"].confirmed_at),
            "mss_index": int(ch["mss"].index),
            "mss_time": _iso(ch["mss"].confirmed_at),
            "fvg_confirmed_index": int(ch["fvg"].details["confirmed_index"]),
            "fvg_time": _iso(ch["fvg_time"]),
            "retest_time": _iso(ch["retest_time"]),
            "m1_time": _iso(ch.get("m1_time")),
        }
    return result


def _find_target(
    candles_m15: list[Any],
    pools: list[Any],
    entry: Optional[float],
    bull: bool,
    *,
    tolerance: float,
    swing_left: int,
    swing_right: int,
) -> Optional[float]:
    """Nearest opposing confirmed level beyond the entry (never invented)."""
    if entry is None:
        return None
    candidates: List[float] = []
    for p in pools:
        kind = (p.details or {}).get("kind")
        if p.level is None:
            continue
        opposing = kind in ("bsl", "equal_high") if bull else kind in ("ssl", "equal_low")
        beyond = p.level > entry if bull else p.level < entry
        if opposing and beyond:
            candidates.append(float(p.level))

    # Swing extremes beyond the entry (confirmed swings only).
    from nazbeen_forex_ai.structure.swings import detect_swings as _ds
    from nazbeen_forex_ai.structure.types import candles_to_df as _cdf

    try:
        for s in _ds(_cdf(candles_m15), left=swing_left, right=swing_right):
            if s.price is None:
                continue
            if bull and s.type == "high" and float(s.price) > entry:
                candidates.append(float(s.price))
            if (not bull) and s.type == "low" and float(s.price) < entry:
                candidates.append(float(s.price))
    except Exception:  # pragma: no cover - target search is additive
        pass

    if not candidates:
        return None
    return min(candidates) if bull else max(candidates)
