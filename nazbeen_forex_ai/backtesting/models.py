"""Backtesting models."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class BacktestRun(models.Model):
    """A recorded backtest run.

    Metrics are computed by :mod:`nazbeen_forex_ai.backtesting.engine` from a real
    trade list — never fabricated (audit CRIT-01). ``user`` is optional: runs
    created without an owner are *not* surfaced by the read-only history
    endpoint, so one user can never read another user's runs.
    """

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

    class Meta:
        ordering = ["-created_at"]
