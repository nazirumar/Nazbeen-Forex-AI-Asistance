"""Backtest execution and reporting services (Phase 11G).

This module turns a validated configuration into a **simulated** historical
evaluation using the Phase 11E deterministic strategy, persists every simulated
trade, and computes performance analytics from those recorded trades only.

Hard rules honoured here:

- No look-ahead: the engine evaluates ``candles[:i]`` and enters at the open of
  the next bar (see :mod:`nazbeen_forex_ai.backtesting.engine`).
- No fabrication: every metric is recomputed from the stored trade list; a metric
  that cannot be computed is returned as ``None`` and its sample size reported.
- Analysis-only: nothing here places, simulates orders against, or talks to a
  broker. Simulated trades are completely separate from any broker order.
"""

from __future__ import annotations

import csv
import io
import json
import math
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional

from django.core.exceptions import ValidationError
from django.utils import timezone as dj_timezone

from nazbeen_forex_ai.backtesting.engine import BacktestResult, Trade, run_backtest
from nazbeen_forex_ai.backtesting.models import BacktestRun, BacktestTrade
from nazbeen_forex_ai.backtesting.walkforward import walk_forward
from nazbeen_forex_ai.marketdata.factory import get_market_data_provider
from nazbeen_forex_ai.marketdata.providers import MarketDataProviderError

# --- Constants -------------------------------------------------------------

STRATEGY_VERSION = "phase11e-primary-model"

VALID_TIMEFRAMES = frozenset({"M1", "M5", "M15", "H1"})
MAX_CANDLES = 20000
MIN_CANDLES = 40
PIP_SIZE = 0.0001
CONTRACT_SIZE = 100000.0
MAX_LOTS = 100.0
MIN_LOTS = 0.01

DEFAULT_CONFIG: Dict[str, Any] = {
    "symbol": "EURUSD",
    "timeframe": "M15",
    "start": None,
    "end": None,
    "count": 1000,
    "initial_balance": 10000.0,
    "risk_pct": 1.0,
    "spread_pips": 1.0,
    "commission_pips": 0.5,
    "slippage_pips": 0.5,
    "sl_pips": 10.0,
    "tp_pips": 20.0,
    "max_daily_loss": 0.0,
    "max_drawdown_pct": 0.0,
    "walk_forward": False,
    "train_size": 200,
    "test_size": 100,
    "strategy_version": STRATEGY_VERSION,
}


class BacktestExecutionError(Exception):
    """Raised when a run cannot be executed. Message is safe for the owner."""


def _finite(value: float) -> Optional[float]:
    """Return ``value`` unless it is non-finite (JSON-safe), else ``None``."""
    try:
        if math.isfinite(value):
            return float(value)
    except (TypeError, ValueError):
        return None
    return None


def _as_float(payload: Dict[str, Any], key: str, default: float) -> float:
    raw = payload.get(key, default)
    if raw is None or raw == "":
        return default
    if isinstance(raw, bool):
        raise ValidationError(f"{key} must be a number.")
    try:
        return float(raw)
    except (TypeError, ValueError):
        raise ValidationError(f"{key} must be a number.")


def _as_int(payload: Dict[str, Any], key: str, default: int) -> int:
    raw = payload.get(key, default)
    if raw is None or raw == "":
        return default
    if isinstance(raw, bool):
        raise ValidationError(f"{key} must be an integer.")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValidationError(f"{key} must be an integer.")
    if float(raw) != value:
        raise ValidationError(f"{key} must be an integer.")
    return value


def _parse_iso(raw: Optional[str], field: str) -> Optional[datetime]:
    if raw is None or raw == "":
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        raise ValidationError(f"{field} must be an ISO-8601 timestamp.")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def default_config_response() -> Dict[str, Any]:
    """Default configuration plus documented valid ranges (for the UI)."""
    return {
        "defaults": dict(DEFAULT_CONFIG),
        "timeframes": sorted(VALID_TIMEFRAMES),
        "limits": {
            "count_min": MIN_CANDLES,
            "count_max": MAX_CANDLES,
            "risk_pct_max": 100.0,
            "max_drawdown_pct_max": 100.0,
            "initial_balance_min": 0.0,
        },
        "strategy_version": STRATEGY_VERSION,
        "disclaimer": (
            "Simulated historical evaluation only. Past performance does not "
            "guarantee future results; this platform places no orders."
        ),
    }


def validate_config(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate and normalise a backtest configuration.

    Raises :class:`~django.core.exceptions.ValidationError` with a list of safe
    messages. Never trusts client input, never silently coerces an invalid value.
    """
    payload = payload if isinstance(payload, dict) else {}
    errors: List[str] = []

    symbol = str(payload.get("symbol", DEFAULT_CONFIG["symbol"]) or "").strip()
    if not symbol:
        errors.append("symbol is required.")
    elif len(symbol) > 32:
        errors.append("symbol must be 32 characters or fewer.")

    timeframe = str(payload.get("timeframe", DEFAULT_CONFIG["timeframe"]) or "").strip().upper()
    if timeframe not in VALID_TIMEFRAMES:
        errors.append(f"timeframe must be one of {', '.join(sorted(VALID_TIMEFRAMES))}.")

    try:
        start = _parse_iso(payload.get("start"), "start")
        end = _parse_iso(payload.get("end"), "end")
    except ValidationError as e:
        errors.extend(e.messages)
        start = end = None
    if start and end and end <= start:
        errors.append("end must be after start.")

    try:
        count = _as_int(payload, "count", DEFAULT_CONFIG["count"])
        initial_balance = _as_float(payload, "initial_balance", DEFAULT_CONFIG["initial_balance"])
        risk_pct = _as_float(payload, "risk_pct", DEFAULT_CONFIG["risk_pct"])
        spread_pips = _as_float(payload, "spread_pips", DEFAULT_CONFIG["spread_pips"])
        commission_pips = _as_float(payload, "commission_pips", DEFAULT_CONFIG["commission_pips"])
        slippage_pips = _as_float(payload, "slippage_pips", DEFAULT_CONFIG["slippage_pips"])
        sl_pips = _as_float(payload, "sl_pips", DEFAULT_CONFIG["sl_pips"])
        tp_pips = _as_float(payload, "tp_pips", DEFAULT_CONFIG["tp_pips"])
        max_daily_loss = _as_float(payload, "max_daily_loss", DEFAULT_CONFIG["max_daily_loss"])
        max_drawdown_pct = _as_float(payload, "max_drawdown_pct", DEFAULT_CONFIG["max_drawdown_pct"])
        train_size = _as_int(payload, "train_size", DEFAULT_CONFIG["train_size"])
        test_size = _as_int(payload, "test_size", DEFAULT_CONFIG["test_size"])
    except ValidationError as e:
        errors.extend(e.messages)
        count = initial_balance = risk_pct = spread_pips = commission_pips = 0
        slippage_pips = sl_pips = tp_pips = max_daily_loss = max_drawdown_pct = 0.0
        train_size = test_size = 0

    walk_forward = bool(payload.get("walk_forward", DEFAULT_CONFIG["walk_forward"]))
    strategy_version = str(
        payload.get("strategy_version", DEFAULT_CONFIG["strategy_version"]) or STRATEGY_VERSION
    ).strip() or STRATEGY_VERSION

    if not (MIN_CANDLES <= count <= MAX_CANDLES):
        errors.append(f"count must be between {MIN_CANDLES} and {MAX_CANDLES}.")
    if initial_balance <= 0:
        errors.append("initial_balance must be greater than 0.")
    if not (0 < risk_pct <= 100):
        errors.append("risk_pct must be greater than 0 and at most 100.")
    for name, value in (
        ("spread_pips", spread_pips),
        ("commission_pips", commission_pips),
        ("slippage_pips", slippage_pips),
    ):
        if value < 0:
            errors.append(f"{name} must be 0 or greater.")
    if sl_pips <= 0:
        errors.append("sl_pips must be greater than 0.")
    if tp_pips <= 0:
        errors.append("tp_pips must be greater than 0.")
    if max_daily_loss < 0:
        errors.append("max_daily_loss must be 0 or greater.")
    if not (0 <= max_drawdown_pct <= 100):
        errors.append("max_drawdown_pct must be between 0 and 100.")
    if walk_forward:
        if train_size < 1 or test_size < 1:
            errors.append("train_size and test_size must be at least 1 for walk-forward runs.")
        elif train_size + test_size > MAX_CANDLES:
            errors.append("train_size + test_size is too large.")

    if errors:
        raise ValidationError(errors)

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "start": start.isoformat().replace("+00:00", "Z") if start else None,
        "end": end.isoformat().replace("+00:00", "Z") if end else None,
        "count": count,
        "initial_balance": initial_balance,
        "risk_pct": risk_pct,
        "spread_pips": spread_pips,
        "commission_pips": commission_pips,
        "slippage_pips": slippage_pips,
        "sl_pips": sl_pips,
        "tp_pips": tp_pips,
        "max_daily_loss": max_daily_loss,
        "max_drawdown_pct": max_drawdown_pct,
        "walk_forward": walk_forward,
        "train_size": train_size,
        "test_size": test_size,
        "strategy_version": strategy_version,
    }


def compute_lots(config: Dict[str, Any]) -> float:
    """Risk-based position sizing (documented assumption).

    ``risk_amount / (sl_pips * pip_value_per_lot)`` where
    ``pip_value_per_lot = pip_size * contract_size`` (10.0 for a 0.0001 pip on a
    100 000-unit lot). Bounded to ``[MIN_LOTS, MAX_LOTS]``.
    """
    risk_amount = config["initial_balance"] * config["risk_pct"] / 100.0
    pip_value_per_lot = PIP_SIZE * CONTRACT_SIZE
    denominator = config["sl_pips"] * pip_value_per_lot
    if denominator <= 0:
        return MIN_LOTS
    lots = risk_amount / denominator
    return round(max(MIN_LOTS, min(MAX_LOTS, lots)), 2)


# --- Candles ---------------------------------------------------------------


def _candle_dicts(candles: Iterable[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for c in candles:
        if hasattr(c, "to_dict"):
            out.append(c.to_dict())
        elif isinstance(c, dict):
            out.append(c)
    return out


def fetch_candles(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fetch validated historical candles via the configured provider.

    MOCK data is labelled by the provider and never presented as live
    (``data_source`` is recorded on the run). Raises
    :class:`BacktestExecutionError` with a safe message on provider failure or
    when the requested range yields no/insufficient candles.
    """
    provider = get_market_data_provider()
    try:
        provider.connect()
    except MarketDataProviderError as exc:
        raise BacktestExecutionError("Market data provider is unavailable.") from exc

    anchor = _parse_iso(config.get("end"), "end") or _parse_iso(config.get("start"), "start")
    try:
        raw = _candle_dicts(
            provider.get_candles(
                symbol=config["symbol"],
                timeframe=config["timeframe"],
                start=anchor,
                count=config["count"],
            )
        )
    except MarketDataProviderError as exc:
        raise BacktestExecutionError(
            f"No market data for {config['symbol']} {config['timeframe']}."
        ) from exc
    except Exception as exc:  # noqa: BLE001 — surface a safe message, log detail
        raise BacktestExecutionError("Failed to retrieve historical candles.") from exc

    start_dt = _parse_iso(config.get("start"), "start")
    end_dt = _parse_iso(config.get("end"), "end")
    if start_dt or end_dt:
        filtered = []
        for c in raw:
            try:
                t = _parse_iso(str(c.get("time")), "time")
            except ValidationError:
                continue
            if start_dt and t < start_dt:
                continue
            if end_dt and t > end_dt:
                continue
            filtered.append(c)
        raw = filtered

    if len(raw) < MIN_CANDLES:
        raise BacktestExecutionError(
            f"Not enough historical candles to backtest ({len(raw)} < {MIN_CANDLES})."
        )
    return raw


# --- Execution -------------------------------------------------------------


def _engine_kwargs(config: Dict[str, Any], lots: float) -> Dict[str, Any]:
    return {
        "commission_pips": config["commission_pips"],
        "slippage_pips": config["slippage_pips"],
        "spread_pips": config["spread_pips"],
        "sl_pips": config["sl_pips"],
        "tp_pips": config["tp_pips"],
        "pip_size": PIP_SIZE,
        "contract_size": CONTRACT_SIZE,
        "lots": lots,
        "initial_balance": config["initial_balance"],
        "max_daily_loss": config["max_daily_loss"],
        "max_drawdown_pct": config["max_drawdown_pct"],
    }


def execute_run(run: BacktestRun) -> BacktestRun:
    """Execute a queued run and persist its trades/metrics. Idempotent per run."""
    config = run.config or {}
    run.status = BacktestRun.Status.RUNNING
    run.started_at = dj_timezone.now()
    run.error = ""
    run.save(update_fields=["status", "started_at", "error"])

    try:
        candles = fetch_candles(config)
        lots = compute_lots(config)
        kwargs = _engine_kwargs(config, lots)

        if config.get("walk_forward"):
            wf = walk_forward(
                candles,
                train_size=int(config.get("train_size", DEFAULT_CONFIG["train_size"])),
                test_size=int(config.get("test_size", DEFAULT_CONFIG["test_size"])),
                step=int(config.get("test_size", DEFAULT_CONFIG["test_size"])) or 1,
                **kwargs,
            )
            result = wf.overall
            is_walk_forward = bool(wf.is_walk_forward)
            note = wf.note
        else:
            result = run_backtest(candles, **kwargs)
            is_walk_forward = False
            note = ""

        _persist_trades(run, result)
        metrics = compute_metrics(run, result, lots)
        _apply_metrics(run, result, metrics)
        run.is_walk_forward = is_walk_forward
        run.note = note
        run.status = BacktestRun.Status.COMPLETED
        run.finished_at = dj_timezone.now()
        run.error = ""
        run.save()
        return run
    except BacktestExecutionError as exc:
        run.status = BacktestRun.Status.FAILED
        run.error = str(exc)
        run.finished_at = dj_timezone.now()
        run.save(update_fields=["status", "error", "finished_at"])
        return run
    except Exception:  # noqa: BLE001 — never leak internals; record a safe failure
        run.status = BacktestRun.Status.FAILED
        run.error = "Backtest failed during evaluation."
        run.finished_at = dj_timezone.now()
        run.save(update_fields=["status", "error", "finished_at"])
        raise


def _persist_trades(run: BacktestRun, result: BacktestResult) -> None:
    run.trades.all().delete()
    rows: List[BacktestTrade] = []
    for idx, t in enumerate(result.trades):
        rows.append(
            BacktestTrade(
                run=run,
                index=idx,
                side=t.side,
                entry_time=_to_dt(t.entry_time),
                exit_time=_to_dt(t.exit_time),
                entry=float(t.entry),
                exit_price=float(t.exit_price) if t.exit_price is not None else None,
                sl=float(t.sl),
                tp=float(t.tp),
                lots=float(t.lots),
                result=t.result,
                pnl=float(t.pnl),
                realized_r=_realized_r(t),
                duration_seconds=_duration_seconds(t),
                exit_reason=_exit_reason(t),
                session=_session_for(_to_dt(t.entry_time)),
                weekday=_weekday_for(_to_dt(t.entry_time)),
                commission=float(t.commission),
                slippage=float(t.slippage),
                spread_cost=float(t.spread_cost),
            )
        )
    if rows:
        BacktestTrade.objects.bulk_create(rows)


def _to_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif hasattr(value, "to_pydatetime"):
        dt = value.to_pydatetime()
    else:
        dt = _parse_iso(str(value), "time")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _realized_r(t: Trade) -> Optional[float]:
    risk_money = abs(float(t.entry) - float(t.sl)) * CONTRACT_SIZE * float(t.lots)
    if risk_money <= 0:
        return None
    return float(t.pnl) / risk_money


def _duration_seconds(t: Trade) -> Optional[int]:
    entry, exit_ = _to_dt(t.entry_time), _to_dt(t.exit_time)
    if entry is None or exit_ is None:
        return None
    return int((exit_ - entry).total_seconds())


def _exit_reason(t: Trade) -> str:
    if t.exit_price is None:
        return "unknown"
    if t.result == "WIN":
        return "take_profit"
    if t.result == "LOSS":
        return "stop_loss"
    return "end_of_data"


def _session_for(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    hour = dt.hour  # UTC
    if 0 <= hour < 7:
        return "asian"
    if 7 <= hour < 12:
        return "london"
    if 12 <= hour < 21:
        return "new_york"
    return "late"


_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _weekday_for(dt: Optional[datetime]) -> Optional[int]:
    if dt is None:
        return None
    return dt.weekday()


def _weekday_name(idx: Optional[int]) -> str:
    if idx is None or not (0 <= idx < 7):
        return "Unknown"
    return _WEEKDAYS[idx]


# --- Metrics ---------------------------------------------------------------


def _group_stats(trades: List[BacktestTrade]) -> Dict[str, Any]:
    total = len(trades)
    wins = sum(1 for t in trades if t.result == "WIN")
    losses = sum(1 for t in trades if t.result == "LOSS")
    net = float(sum(t.pnl for t in trades))
    return {
        "trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": _finite(100.0 * wins / total) if total else None,
        "net_profit": net,
    }


def _max_streak(trades: List[BacktestTrade], result: str) -> int:
    best = cur = 0
    for t in trades:
        if t.result == result:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def compute_metrics(
    run: BacktestRun, result: BacktestResult, lots: float
) -> Dict[str, Any]:
    """Recompute the §6 metric set from stored trades. ``None`` when not computable."""
    trades = list(run.trades.order_by("index"))
    total = len(trades)
    wins = sum(1 for t in trades if t.result == "WIN")
    losses = sum(1 for t in trades if t.result == "LOSS")
    break_evens = sum(1 for t in trades if t.result == "BREAK_EVEN")
    pnls = [t.pnl for t in trades]
    gross_profit = float(sum(p for p in pnls if p > 0))
    gross_loss = float(-sum(p for p in pnls if p < 0))
    net_profit = float(sum(pnls))

    pf_note = ""
    if gross_loss > 0:
        profit_factor: Optional[float] = _finite(gross_profit / gross_loss)
    elif gross_profit > 0:
        profit_factor = None  # no losing trades: ratio undefined
        pf_note = "No losing trades in the sample — profit factor is undefined."
    else:
        profit_factor = None

    r_values = [t.realized_r for t in trades if t.realized_r is not None]
    durations = [t.duration_seconds for t in trades if t.duration_seconds is not None]
    initial = float(run.config.get("initial_balance", 0.0) or 0.0)
    max_dd = float(result.max_drawdown)

    by_session: Dict[str, Any] = {}
    by_weekday: Dict[str, Any] = {}
    by_setup: Dict[str, Any] = {}
    for t in trades:
        by_session.setdefault(t.session or "unknown", []).append(t)
        by_weekday.setdefault(_weekday_name(t.weekday), []).append(t)
        by_setup.setdefault(t.side or "unknown", []).append(t)

    return {
        "sample_size": total,
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "break_evens": break_evens,
        "win_rate": _finite(100.0 * wins / total) if total else None,
        "average_realized_r": _finite(sum(r_values) / len(r_values)) if r_values else None,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "net_profit": net_profit,
        "profit_factor": profit_factor,
        "profit_factor_note": pf_note,
        "expectancy": _finite(net_profit / total) if total else None,
        "max_drawdown": max_dd,
        "max_drawdown_pct": _finite(max_dd / initial * 100.0) if initial > 0 else None,
        "average_trade_duration_seconds": (
            _finite(sum(durations) / len(durations)) if durations else None
        ),
        "max_consecutive_wins": _max_streak(trades, "WIN"),
        "max_consecutive_losses": _max_streak(trades, "LOSS"),
        "by_session": {k: _group_stats(v) for k, v in by_session.items()},
        "by_weekday": {k: _group_stats(v) for k, v in by_weekday.items()},
        "by_setup_type": {k: _group_stats(v) for k, v in by_setup.items()},
        "assumptions": {
            "spread_pips": run.config.get("spread_pips"),
            "commission_pips": run.config.get("commission_pips"),
            "slippage_pips": run.config.get("slippage_pips"),
            "sl_pips": run.config.get("sl_pips"),
            "tp_pips": run.config.get("tp_pips"),
            "initial_balance": initial,
            "risk_pct": run.config.get("risk_pct"),
            "lots": lots,
            "contract_size": CONTRACT_SIZE,
            "pip_size": PIP_SIZE,
        },
        "is_walk_forward": bool(run.is_walk_forward),
    }


def _apply_metrics(run: BacktestRun, result: BacktestResult, metrics: Dict[str, Any]) -> None:
    run.total_trades = result.total_trades
    run.win_rate = _finite(result.win_rate) or 0.0
    run.profit_factor = _finite(result.profit_factor) or 0.0
    run.expectancy = _finite(result.expectancy) or 0.0
    run.max_drawdown = _finite(result.max_drawdown) or 0.0
    run.net_profit = _finite(result.net_profit) or 0.0
    run.metrics = metrics


# --- Equity / balance curve ------------------------------------------------


def equity_curve(run: BacktestRun) -> List[Dict[str, Any]]:
    """Equity/balance curve derived from the stored simulated trades.

    Equity and balance are identical here because positions are opened and
    closed fully (no floating P&L); both are reported for compatibility.
    """
    trades = list(run.trades.order_by("index"))
    initial = float(run.config.get("initial_balance", 0.0) or 0.0)
    points: List[Dict[str, Any]] = []
    equity = initial
    peak = initial
    start_time = run.started_at or run.created_at
    points.append(
        {
            "time": start_time.isoformat().replace("+00:00", "Z") if start_time else None,
            "equity": equity,
            "balance": equity,
            "drawdown": 0.0,
        }
    )
    for t in trades:
        equity += t.pnl
        peak = max(peak, equity)
        points.append(
            {
                "time": t.exit_time.isoformat().replace("+00:00", "Z") if t.exit_time else None,
                "equity": equity,
                "balance": equity,
                "drawdown": float(peak - equity),
            }
        )
    return points


# --- Serialization / export ------------------------------------------------


def _iso(value: Any) -> Optional[str]:
    return value.isoformat().replace("+00:00", "Z") if value else None


def serialize_trade(t: BacktestTrade) -> Dict[str, Any]:
    return {
        "id": str(t.id),
        "index": t.index,
        "side": t.side,
        "entry_time": _iso(t.entry_time),
        "exit_time": _iso(t.exit_time),
        "entry": t.entry,
        "exit_price": t.exit_price,
        "sl": t.sl,
        "tp": t.tp,
        "lots": t.lots,
        "result": t.result,
        "pnl": t.pnl,
        "realized_r": t.realized_r,
        "duration_seconds": t.duration_seconds,
        "exit_reason": t.exit_reason,
        "session": t.session,
        "weekday": _weekday_name(t.weekday),
    }


def serialize_run(run: BacktestRun) -> Dict[str, Any]:
    """Full run representation. Backward compatible with the Phase 11F fields."""
    return {
        "id": str(run.id),
        "symbol": run.symbol,
        "timeframe": run.timeframe,
        "status": run.status,
        "error": run.error or None,
        "total_trades": run.total_trades,
        "win_rate": run.win_rate,
        "profit_factor": run.profit_factor,
        "expectancy": run.expectancy,
        "max_drawdown": run.max_drawdown,
        "net_profit": run.net_profit,
        "metrics": run.metrics,
        "config": run.config,
        "strategy_version": run.strategy_version,
        "is_walk_forward": run.is_walk_forward,
        "note": run.note or None,
        "data_source": run.data_source or None,
        "started_at": _iso(run.started_at),
        "finished_at": _iso(run.finished_at),
        "created_at": _iso(run.created_at),
    }


TRADE_COLUMNS = [
    "index",
    "side",
    "entry_time",
    "exit_time",
    "entry",
    "exit_price",
    "sl",
    "tp",
    "lots",
    "result",
    "pnl",
    "realized_r",
    "duration_seconds",
    "exit_reason",
    "session",
    "weekday",
]


def export_run(run: BacktestRun, fmt: str) -> tuple[str, str, str]:
    """Return ``(content, content_type, filename)`` for the requested format."""
    trades = [serialize_trade(t) for t in run.trades.order_by("index")]
    if fmt == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=TRADE_COLUMNS)
        writer.writeheader()
        for row in trades:
            writer.writerow({k: row.get(k) for k in TRADE_COLUMNS})
        return buffer.getvalue(), "text/csv", f"backtest-{run.id}.csv"
    payload = {"run": serialize_run(run), "trades": trades}
    return json.dumps(payload, indent=2), "application/json", f"backtest-{run.id}.json"
