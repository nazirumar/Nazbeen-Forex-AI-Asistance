"""Core app: shared platform services (health checks, common utilities)."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "nazbeen_forex_ai.core"
    verbose_name = "Core"
