"""Screenshot analysis models."""

from __future__ import annotations

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone

from nazbeen_forex_ai.analysis.storage import get_screenshot_upload_path


class ScreenshotAnalysis(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="screenshots")
    image = models.ImageField(upload_to=get_screenshot_upload_path, blank=True, null=True)
    image_path = models.CharField(max_length=512, blank=True)
    image_data = models.BinaryField(blank=True, null=True)
    symbol = models.CharField(max_length=20, blank=True, null=True)
    timeframe = models.CharField(max_length=10, blank=True, null=True)
    ai_summary = models.TextField(blank=True)
    structured_output = models.JSONField(default=dict)
    disagreements = models.JSONField(default=list)
    mtf_conflicts = models.JSONField(default=list)
    evidence = models.JSONField(default=list)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"ScreenshotAnalysis {self.id}"
