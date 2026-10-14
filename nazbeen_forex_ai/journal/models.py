"""Trading journal models."""

from __future__ import annotations

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class JournalEntry(models.Model):
    """Trading journal entry (MASTER_SPEC §3.H).

    Records the full spec context for historical review and performance
    reports. Every spec field is stored verbatim: a value that was never
    recorded stays ``null``/``[]``/``{}`` — nothing here is defaulted or
    fabricated (audit M-15).
    """

    OUTCOME_CHOICES = [
        ("WIN", "WIN"),
        ("LOSS", "LOSS"),
        ("BE", "BE"),
        ("PENDING", "PENDING"),
    ]

    # Phase 11G §10: typed origin so journal rows from manual entry, screenshot
    # analysis, backtests and forward tests are never conflated.
    SOURCE_CHOICES = [
        ("manual", "manual"),
        ("screenshot_analysis", "screenshot_analysis"),
        ("backtest", "backtest"),
        ("forward_test", "forward_test"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="journal_entries")

    # --- link back to the originating analysis (screenshot + snapshot) -------
    screenshot_analysis = models.ForeignKey(
        "analysis.ScreenshotAnalysis",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="journal_entries",
    )
    analysis_session_id = models.UUIDField(blank=True, null=True)

    # --- identity -----------------------------------------------------------
    symbol = models.CharField(max_length=20, blank=True, null=True)
    timeframe = models.CharField(max_length=10, blank=True, null=True)
    # Phase 11G §10: origin discriminator (recorded, never inferred silently).
    source = models.CharField(max_length=24, choices=SOURCE_CHOICES, default="manual")
    # Optional opaque reference to the origin row (e.g. a BacktestRun or forward
    # test id). Kept as a string so journal does not hard-depend on those apps.
    source_ref = models.CharField(max_length=64, blank=True, default="")

    # --- spec §3.H recorded context ----------------------------------------
    analysis_timestamp = models.DateTimeField(blank=True, null=True)
    market_snapshot = models.JSONField(default=dict)
    detected_structures = models.JSONField(default=dict)
    model_version = models.CharField(max_length=200, blank=True)
    strategy_version = models.CharField(max_length=100, blank=True)
    # Estimated probability is an optional, externally-calibrated figure; it is
    # never invented here (audit M-08). Null = "not available".
    estimated_probability = models.FloatField(blank=True, null=True)

    # --- suggested scenario / levels ---------------------------------------
    scenario_decision = models.CharField(max_length=10, blank=True, null=True)
    entry = models.FloatField(blank=True, null=True)
    sl = models.FloatField(blank=True, null=True)  # invalidation
    tp = models.FloatField(blank=True, null=True)
    rr = models.FloatField(blank=True, null=True)

    # --- outcome evaluation + notes ----------------------------------------
    outcome = models.CharField(max_length=10, choices=OUTCOME_CHOICES, default="PENDING")
    pnl = models.FloatField(blank=True, null=True)
    notes = models.TextField(blank=True)
    tags = models.JSONField(default=list)
    metrics = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class MentorMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mentor_messages")
    role = models.CharField(max_length=10, choices=[("user", "user"), ("assistant", "assistant")])
    content = models.TextField()
    context_summary = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]
