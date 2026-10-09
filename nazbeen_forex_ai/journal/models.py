"""Trading journal models."""

from __future__ import annotations

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class JournalEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="journal_entries")
    symbol = models.CharField(max_length=20, blank=True, null=True)
    timeframe = models.CharField(max_length=10, blank=True, null=True)
    analysis_session_id = models.UUIDField(blank=True, null=True)
    scenario_decision = models.CharField(max_length=10, blank=True, null=True)
    entry = models.FloatField(blank=True, null=True)
    sl = models.FloatField(blank=True, null=True)
    tp = models.FloatField(blank=True, null=True)
    rr = models.FloatField(blank=True, null=True)
    outcome = models.CharField(max_length=10, choices=[("WIN", "WIN"), ("LOSS", "LOSS"), ("BE", "BE"), ("PENDING", "PENDING")], default="PENDING")
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
