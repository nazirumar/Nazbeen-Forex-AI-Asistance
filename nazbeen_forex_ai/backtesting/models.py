"""Backtesting models (Phase 6; extended in Phase 11F and 11G).

``BacktestRun`` records a simulated historical evaluation. Metrics are computed by
:mod:`nazbeen_forex_ai.backtesting.engine` from a real trade list — never
fabricated (audit CRIT-01). ``user`` is optional: runs created without an owner
are *not* surfaced by the history endpoints, so one user can never read another
user's runs.

Phase 11G adds the **execution/reporting surface**: a run now carries its
configuration snapshot, lifecycle status, failure reason and walk-forward
labelling, and each simulated trade is persisted as a ``BacktestTrade`` row so
trades, metrics and the equity curve can be inspected per run. All additions are
backward compatible with the Phase 11F read-only history endpoint.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class BacktestRun(models.Model):
    """A recorded, simulated backtest run (analysis-only — never broker orders)."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="backtest_runs",
    )
    symbol = models.CharField(max_length=20)
    timeframe = models.CharField(max_length=10)
    total_trades = models.IntegerField(default=0)
    win_rate = models.FloatField(default=0.0)
    profit_factor = models.FloatField(default=0.0)
    expectancy = models.FloatField(default=0.0)
    max_drawdown = models.FloatField(default=0.0)
    net_profit = models.FloatField(default=0.0)
    metrics = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)

    # --- Phase 11G execution/reporting fields (additive) --------------------
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.COMPLETED
    )
    error = models.TextField(blank=True, default="")
    config = models.JSONField(default=dict, blank=True)
    strategy_version = models.CharField(max_length=60, blank=True, default="")
    is_walk_forward = models.BooleanField(default=False)
    note = models.TextField(blank=True, default="")
    data_source = models.CharField(max_length=16, blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover - admin/debug helper
        return f"BacktestRun {self.symbol} {self.timeframe} ({self.status})"


class BacktestTrade(models.Model):
    """One simulated trade belonging to a :class:`BacktestRun`.

    Every figure is a record of the simulation — nothing is invented. Exits are
    resolved bar-by-bar by the engine; when SL and TP both sit inside one candle
    the engine assumes the stop-loss first (conservative).
    """

    class Side(models.TextChoices):
        LONG = "LONG", "Long"
        SHORT = "SHORT", "Short"

    class Result(models.TextChoices):
        WIN = "WIN", "Win"
        LOSS = "LOSS", "Loss"
        BREAK_EVEN = "BREAK_EVEN", "Break even"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        BacktestRun, on_delete=models.CASCADE, related_name="trades"
    )
    index = models.IntegerField(default=0)
    side = models.CharField(max_length=5, choices=Side.choices)
    entry_time = models.DateTimeField()
    exit_time = models.DateTimeField(null=True, blank=True)
    entry = models.FloatField()
    exit_price = models.FloatField(null=True, blank=True)
    sl = models.FloatField()
    tp = models.FloatField()
    lots = models.FloatField(default=0.0)
    result = models.CharField(max_length=10, choices=Result.choices)
    pnl = models.FloatField(default=0.0)
    realized_r = models.FloatField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    exit_reason = models.CharField(max_length=12, blank=True, default="")
    session = models.CharField(max_length=16, blank=True, default="")
    weekday = models.IntegerField(null=True, blank=True)
    commission = models.FloatField(default=0.0)
    slippage = models.FloatField(default=0.0)
    spread_cost = models.FloatField(default=0.0)

    class Meta:
        ordering = ["index"]

    def __str__(self) -> str:  # pragma: no cover - admin/debug helper
        return f"Trade {self.index} {self.side} {self.result}"
