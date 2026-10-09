"""Accounts app: user registration, authentication and profiles."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "nazbeen_forex_ai.accounts"
    verbose_name = "Accounts"

    def ready(self) -> None:
        from nazbeen_forex_ai.accounts import signals  # noqa: F401
