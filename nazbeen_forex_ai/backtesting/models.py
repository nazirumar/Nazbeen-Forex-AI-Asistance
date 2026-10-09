"""Backtesting models."""

from __future__ import annotations

import uuid
from django.db import models
from django.utils import timezone


class BacktestRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
