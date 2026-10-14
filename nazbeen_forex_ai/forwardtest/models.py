"""Models for forward testing (Phase 11G §9).

A :class:`ForwardTestRun` observes the deterministic engine as new bars arrive and
records each decision as a :class:`ForwardTestObservation`. Results are
**simulated** and labelled as such — the platform never places orders.

* Dedupe: one observation per ``(run, bar_time)`` so a re-run cannot record the
  same bar twice.
* Outcome tracking: an observation with levels is resolved later from subsequent
  candles, conservatively assuming the stop-loss is hit first when a single bar
  touches both stop and target.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ForwardTestRun(models.Model):
    """A simulated forward test observing the deterministic engine."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        STOPPED = "stopped", "Stopped"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forward_test_runs",
    )
    symbol = models.CharField(max_length=20)
    timeframe = models.CharField(max_length=10)
    config = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.ACTIVE
    )
    data_source = models.CharField(max_length=16, blank=True, default="")
    strategy_version = models.CharField(max_length=60, blank=True, default="")
    # Checkpoint: latest processed bar (ISO-8601 string) and observation count.
    last_observed_bar = models.CharField(max_length=40, blank=True, default="")
    last_observed_at = models.DateTimeField(null=True, blank=True)
    observations_count = models.IntegerField(default=0)
    error = models.TextField(blank=True, default="")
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover - admin/debug helper
        return f"ForwardTestRun {self.symbol} {self.timeframe} ({self.status})"


class ForwardTestObservation(models.Model):
    """One simulated engine decision observed on a single bar."""

    class Decision(models.TextChoices):
        BUY = "BUY", "Buy"
        SELL = "SELL", "Sell"
        WAIT = "WAIT", "Wait"

    class Outcome(models.TextChoices):
        PENDING = "PENDING", "Pending"
        WIN = "WIN", "Win"
        LOSS = "LOSS", "Loss"
        BE = "BE", "Break even"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        ForwardTestRun, on_delete=models.CASCADE, related_name="observations"
    )
    bar_time = models.DateTimeField()
    decision = models.CharField(max_length=6, choices=Decision.choices)
    reason = models.TextField(blank=True, default="")
    entry = models.FloatField(null=True, blank=True)
    sl = models.FloatField(null=True, blank=True)
    tp = models.FloatField(null=True, blank=True)
    rr = models.FloatField(null=True, blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    data_source = models.CharField(max_length=16, blank=True, default="")
    # Forward-test results are always simulated (never real order outcomes).
    simulated = models.BooleanField(default=True)
    outcome = models.CharField(
        max_length=8, choices=Outcome.choices, default=Outcome.PENDING
    )
    outcome_price = models.FloatField(null=True, blank=True)
    outcome_r = models.FloatField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["bar_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "bar_time"], name="uniq_forward_observation_bar"
            )
        ]

    def __str__(self) -> str:  # pragma: no cover - admin/debug helper
        return f"Observation {self.bar_time} {self.decision} ({self.outcome})"
