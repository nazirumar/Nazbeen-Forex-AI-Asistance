"""Django admin for backtesting records (read-only inspection)."""

from django.contrib import admin

from nazbeen_forex_ai.backtesting.models import BacktestRun, BacktestTrade


class BacktestTradeInline(admin.TabularInline):
    model = BacktestTrade
    extra = 0
    can_delete = False
    readonly_fields = (
        "index",
        "side",
        "entry_time",
        "exit_time",
        "entry",
        "exit_price",
        "sl",
        "tp",
        "lots",
        "result",
        "pnl",
        "realized_r",
    )


@admin.register(BacktestRun)
class BacktestRunAdmin(admin.ModelAdmin):
    list_display = ("id", "symbol", "timeframe", "status", "user", "net_profit", "created_at")
    list_filter = ("status", "symbol", "timeframe", "is_walk_forward")
    search_fields = ("symbol", "strategy_version")
    readonly_fields = ("id", "created_at", "started_at", "finished_at")
    inlines = [BacktestTradeInline]
