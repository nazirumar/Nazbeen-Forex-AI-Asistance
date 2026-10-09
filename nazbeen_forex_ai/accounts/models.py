"""Accounts app models."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    """Per-user settings. Kept separate from ``auth.User`` (composition over
    monkey-patching). Every timestamp is UTC; ``display_timezone`` only affects
    how timestamps are *shown* to the user (MASTER_SPEC §3.B)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    display_timezone = models.CharField(
        max_length=64,
        default="UTC",
        help_text="IANA timezone used for displaying timestamps, e.g. Europe/London.",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Profile<{self.user.username}>"
