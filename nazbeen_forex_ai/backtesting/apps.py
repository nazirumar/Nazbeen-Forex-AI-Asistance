from django.apps import AppConfig


class BacktestingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "nazbeen_forex_ai.backtesting"
    verbose_name = "Backtesting"
