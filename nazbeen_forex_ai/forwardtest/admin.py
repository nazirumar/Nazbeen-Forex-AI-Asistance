"""Django admin for forward-testing records (read-only inspection)."""

from django.contrib import admin

from nazbeen_forex_ai.forwardtest.models import ForwardTestObservation, ForwardTestRun


class ForwardTestObservationInline(admin.TabularInline):
    model = ForwardTestObservation
    extra = 0
    can_delete = False
    readonly_fields = (
        "bar_time",
        "decision",
        "entry",
        "sl",
        "tp",
        "rr",
        "outcome",
        "outcome_r",
        "simulated",
    )


@admin.register(ForwardTestRun)
class ForwardTestRunAdmin(admin.ModelAdmin):
    list_display = ("id", "symbol", "timeframe", "status", "user", "observations_count", "created_at")
    list_filter = ("status", "symbol", "timeframe", "data_source")
    search_fields = ("symbol", "strategy_version")
    readonly_fields = ("id", "created_at", "started_at", "stopped_at", "last_observed_bar")
    inlines = [ForwardTestObservationInline]
