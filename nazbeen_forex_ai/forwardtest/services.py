"""Forward-test services (Phase 11G §9/§10).

Turns a validated configuration into a **simulated** forward test: on demand (or
on a schedule) the deterministic engine is observed on freshly-fetched candles
and each decision is recorded. Hard rules:

* No fabrication — decisions come from the deterministic engine on candles that
  already exist; a metric that cannot be computed is ``None``.
* No look-ahead — only candles up to the observed bar are used, and a level is
  resolved from bars strictly *after* the observation.
* Analysis-only — nothing here places, routes or simulates a broker order.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from django.core.exceptions import ValidationError

from nazbeen_forex_ai.backtesting.services import (
    MAX_CANDLES,
    MIN_CANDLES,
    PIP_SIZE,
    STRATEGY_VERSION,
    VALID_TIMEFRAMES,
    BacktestExecutionError,
    fetch_candles,
)
from nazbeen_forex_ai.forwardtest.models import ForwardTestObservation, ForwardTestRun
from nazbeen_forex_ai.structure.analysis import evaluate_scenario

SIMULATED_LABEL = (
    "Simulated forward-test observation (analysis-only). No orders are placed; "
    "results are not live trading performance."
)

DEFAULT_CONFIG: Dict[str, Any] = {
    "symbol": "EURUSD",
    "timeframe": "M15",
    "count": 300,
    "sl_pips": 10.0,
    "tp_pips": 20.0,
    "strategy_version": STRATEGY_VERSION,
}


class ForwardTestExecutionError(Exception):
    """Raised when an observation cycle cannot complete safely."""


def _finite(value: float) -> Optional[float]:
    import math

    return value if value is not None and math.isfinite(value) else None


def _as_float(payload: Dict[str, Any], key: str, default: float) -> float:
    raw = payload.get(key, default)
    if raw in (None, ""):
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        raise ValidationError(f"{key} must be a number.")


def _as_int(payload: Dict[str, Any], key: str, default: int) -> int:
    raw = payload.get(key, default)
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ValidationError(f"{key} must be an integer.")


def _parse_iso(raw: Optional[str]) -> Optional[datetime]:
    if raw is None or raw == "":
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def default_config_response() -> Dict[str, Any]:
    return {
        "defaults": dict(DEFAULT_CONFIG),
        "timeframes": sorted(VALID_TIMEFRAMES),
        "limits": {
            "count_min": MIN_CANDLES,
            "count_max": MAX_CANDLES,
            "max_active_runs": MAX_ACTIVE_RUNS,
        },
        "strategy_version": STRATEGY_VERSION,
        "disclaimer": (
            "Simulated forward testing only. Decisions come from the deterministic "
            "engine on fetched candles; the platform places no orders and results "
            "are not live trading performance."
        ),
    }


MAX_ACTIVE_RUNS = 5


def validate_config(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate and normalise a forward-test configuration (never trusts input)."""
    payload = payload if isinstance(payload, dict) else {}
    errors: List[str] = []

    symbol = str(payload.get("symbol", DEFAULT_CONFIG["symbol"]) or "").strip()
    if not symbol:
        errors.append("symbol is required.")
    elif len(symbol) > 32:
        errors.append("symbol must be 32 characters or fewer.")

    timeframe = str(
        payload.get("timeframe", DEFAULT_CONFIG["timeframe"]) or ""
    ).strip().upper()
    if timeframe not in VALID_TIMEFRAMES:
        errors.append(f"timeframe must be one of {', '.join(sorted(VALID_TIMEFRAMES))}.")

    try:
        count = _as_int(payload, "count", DEFAULT_CONFIG["count"])
        sl_pips = _as_float(payload, "sl_pips", DEFAULT_CONFIG["sl_pips"])
        tp_pips = _as_float(payload, "tp_pips", DEFAULT_CONFIG["tp_pips"])
    except ValidationError as e:
        errors.extend(e.messages)
        count = 0
        sl_pips = tp_pips = 0.0

    if not (MIN_CANDLES <= count <= MAX_CANDLES):
        errors.append(f"count must be between {MIN_CANDLES} and {MAX_CANDLES}.")
    if sl_pips <= 0:
        errors.append("sl_pips must be greater than 0.")
    if tp_pips <= 0:
        errors.append("tp_pips must be greater than 0.")

    strategy_version = str(
        payload.get("strategy_version", DEFAULT_CONFIG["strategy_version"])
        or STRATEGY_VERSION
    ).strip() or STRATEGY_VERSION

    if errors:
        raise ValidationError(errors)

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "count": count,
        "sl_pips": sl_pips,
        "tp_pips": tp_pips,
        "strategy_version": strategy_version,
    }


# --- Observation cycle ------------------------------------------------------


def _fetch_window(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    fetch_config = {
        "symbol": config["symbol"],
        "timeframe": config["timeframe"],
        "count": config["count"],
        "start": None,
        "end": None,
    }
    try:
        return fetch_candles(fetch_config)
    except BacktestExecutionError as exc:
        raise ForwardTestExecutionError(str(exc)) from exc


def _levels(decision: str, price: float, config: Dict[str, Any]) -> Dict[str, Any]:
    sl_pips = config["sl_pips"]
    tp_pips = config["tp_pips"]
    step = PIP_SIZE
    if decision == "BUY":
        return {
            "entry": price,
            "sl": price - sl_pips * step,
            "tp": price + tp_pips * step,
            "rr": _finite(tp_pips / sl_pips),
        }
    if decision == "SELL":
        return {
            "entry": price,
            "sl": price + sl_pips * step,
            "tp": price - tp_pips * step,
            "rr": _finite(tp_pips / sl_pips),
        }
    return {"entry": None, "sl": None, "tp": None, "rr": None}


def _resolve_pending(run: ForwardTestRun, candles: List[Dict[str, Any]]) -> int:
    """Resolve PENDING observations against later candles (SL-first, conservative)."""
    resolved = 0
    pending = run.observations.filter(
        outcome=ForwardTestObservation.Outcome.PENDING, decision__in=["BUY", "SELL"]
    )
    for obs in pending:
        later = []
        for c in candles:
            t = _parse_iso(str(c.get("time")))
            if t is not None and t > obs.bar_time:
                later.append(c)
        if not later:
            continue
        for c in later:
            high = float(c.get("high"))
            low = float(c.get("low"))
            if obs.decision == "BUY":
                if obs.sl is not None and low <= obs.sl:
                    obs.outcome = ForwardTestObservation.Outcome.LOSS
                    obs.outcome_price = obs.sl
                    break
                if obs.tp is not None and high >= obs.tp:
                    obs.outcome = ForwardTestObservation.Outcome.WIN
                    obs.outcome_price = obs.tp
                    break
            elif obs.decision == "SELL":
                if obs.sl is not None and high >= obs.sl:
                    obs.outcome = ForwardTestObservation.Outcome.LOSS
                    obs.outcome_price = obs.sl
                    break
                if obs.tp is not None and low <= obs.tp:
                    obs.outcome = ForwardTestObservation.Outcome.WIN
                    obs.outcome_price = obs.tp
                    break
        else:
            continue
        obs.outcome_r = obs.rr if obs.outcome == ForwardTestObservation.Outcome.WIN else -1.0
        from django.utils import timezone as dj_timezone

        obs.resolved_at = dj_timezone.now()
        obs.save(
            update_fields=["outcome", "outcome_price", "outcome_r", "resolved_at"]
        )
        resolved += 1
    return resolved


def observe_run(run: ForwardTestRun) -> int:
    """Run one observation cycle; return the number of new observations.

    Raises :class:`ForwardTestExecutionError` on provider failure so the caller
    can record a safe failure — a failed cycle never fabricates a decision.
    """
    if run.status != ForwardTestRun.Status.ACTIVE:
        return 0
    config = run.config or {}
    candles = _fetch_window(config)
    if len(candles) < MIN_CANDLES:
        raise ForwardTestExecutionError("Not enough candles to observe.")

    bar_time = _parse_iso(str(candles[-1].get("time")))
    if bar_time is None:
        raise ForwardTestExecutionError("Candle timestamps are unreadable.")

    # Outcome tracking first, so a decision is only recorded once per bar.
    _resolve_pending(run, candles)

    existing = run.observations.filter(bar_time=bar_time).exists()
    if existing:
        # No new bar since the last cycle; checkpoint is unchanged.
        from django.utils import timezone as dj_timezone

        run.last_observed_at = dj_timezone.now()
        run.save(update_fields=["last_observed_at"])
        return 0

    # No look-ahead: evaluate strictly on candles up to and including bar_time.
    window = [c for c in candles if (_parse_iso(str(c.get("time"))) or bar_time) <= bar_time]
    # Exclude the newest (potentially still-forming) bar from the read.
    read_window = window[:-1] if len(window) > 1 else window
    result = evaluate_scenario(read_window, [], [])
    decision = str(result.get("decision", "WAIT"))
    if decision not in ("BUY", "SELL"):
        decision = "WAIT"
    bias = result.get("bias") or {}
    price = float(window[-1].get("close"))
    levels = _levels(decision, price, config)
    reason = _reason(decision, bias, result)

    ForwardTestObservation.objects.create(
        run=run,
        bar_time=bar_time,
        decision=decision,
        reason=reason,
        entry=levels["entry"],
        sl=levels["sl"],
        tp=levels["tp"],
        rr=levels["rr"],
        snapshot={
            "bias": {k: v for k, v in bias.items() if k != "conflicts"},
            "conflicts": bias.get("conflicts", []),
            "price": price,
            "simulated": True,
        },
        data_source=run.data_source,
    )

    from django.utils import timezone as dj_timezone

    run.last_observed_bar = bar_time.isoformat().replace("+00:00", "Z")
    run.last_observed_at = dj_timezone.now()
    run.observations_count = run.observations.count()
    run.save(
        update_fields=[
            "last_observed_bar",
            "last_observed_at",
            "observations_count",
        ]
    )
    return 1


def _reason(decision: str, bias: Dict[str, Any], result: Dict[str, Any]) -> str:
    if decision == "WAIT":
        conflicts = bias.get("conflicts") or []
        if conflicts:
            return "No qualified setup: cross-timeframe conflict (" + "; ".join(conflicts) + ")."
        return "No qualified setup on the closed window; deterministic engine returned WAIT."
    return f"Deterministic {decision} on closed window; simulated entry requires no confirmation from AI."


def journalize_observation(user, observation: ForwardTestObservation):
    """Create a typed journal entry (source=forward_test) from an observation.

    The journal row is explicitly labelled simulated; it never claims a real
    trade. Returns ``None`` if the observation is not owned by ``user``.
    """
    from nazbeen_forex_ai.journal.models import JournalEntry

    if observation.run.user_id != getattr(user, "id", None):
        return None

    scenario = observation.decision if observation.decision in ("BUY", "SELL") else "WAIT"
    if observation.outcome == ForwardTestObservation.Outcome.WIN:
        outcome = "WIN"
    elif observation.outcome == ForwardTestObservation.Outcome.LOSS:
        outcome = "LOSS"
    elif observation.outcome == ForwardTestObservation.Outcome.BE:
        outcome = "BE"
    else:
        outcome = "PENDING"

    return JournalEntry.objects.create(
        user=user,
        symbol=observation.run.symbol,
        timeframe=observation.run.timeframe,
        source="forward_test",
        source_ref=str(observation.id),
        analysis_timestamp=observation.bar_time,
        scenario_decision=scenario,
        entry=observation.entry,
        sl=observation.sl,
        tp=observation.tp,
        rr=observation.rr,
        outcome=outcome,
        notes=SIMULATED_LABEL,
        metrics={"simulated": True, "outcome_r": observation.outcome_r},
        tags=["forward_test", "simulated"],
    )


# --- Serialization ----------------------------------------------------------


def _iso(value: Any) -> Optional[str]:
    return value.isoformat().replace("+00:00", "Z") if value else None


def serialize_observation(obs: ForwardTestObservation) -> Dict[str, Any]:
    return {
        "id": str(obs.id),
        "run_id": str(obs.run_id),
        "bar_time": _iso(obs.bar_time),
        "decision": obs.decision,
        "reason": obs.reason,
        "entry": obs.entry,
        "sl": obs.sl,
        "tp": obs.tp,
        "rr": obs.rr,
        "snapshot": obs.snapshot,
        "data_source": obs.data_source,
        "simulated": obs.simulated,
        "outcome": obs.outcome,
        "outcome_price": obs.outcome_price,
        "outcome_r": obs.outcome_r,
        "resolved_at": _iso(obs.resolved_at),
        "created_at": _iso(obs.created_at),
    }


def serialize_run(run: ForwardTestRun) -> Dict[str, Any]:
    outcomes = {"PENDING": 0, "WIN": 0, "LOSS": 0, "BE": 0}
    for row in run.observations.values("outcome"):
        key = row["outcome"]
        if key in outcomes:
            outcomes[key] += 1
    return {
        "id": str(run.id),
        "symbol": run.symbol,
        "timeframe": run.timeframe,
        "status": run.status,
        "config": run.config,
        "strategy_version": run.strategy_version,
        "data_source": run.data_source,
        "last_observed_bar": run.last_observed_bar or None,
        "last_observed_at": _iso(run.last_observed_at),
        "observations_count": run.observations_count,
        "outcomes": outcomes,
        "error": run.error,
        "note": run.note,
        "simulated": True,
        "created_at": _iso(run.created_at),
        "started_at": _iso(run.started_at),
        "stopped_at": _iso(run.stopped_at),
    }


def get_own_run(user, run_id: Any) -> Optional[ForwardTestRun]:
    try:
        ref = uuid.UUID(str(run_id))
    except (TypeError, ValueError):
        return None
    return ForwardTestRun.objects.filter(user=user, id=ref).first()
