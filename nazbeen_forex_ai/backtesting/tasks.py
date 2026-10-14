"""Celery tasks for backtest execution (Phase 11G).

The heavy simulation runs off the request/response cycle. Routed to the "heavy"
queue by ``CELERY_TASK_ROUTES`` (``nazbeen_forex_ai.backtesting.*``). In
development and tests Celery runs eagerly, so the task completes inline.

Task ownership: the run's ``user`` is part of the persisted row, so a task can
only ever touch the run it was handed. A failure is captured on the run (status
``failed`` + safe message) and never silently produces a result.
"""

from __future__ import annotations

import logging

from celery import shared_task

from nazbeen_forex_ai.backtesting.models import BacktestRun
from nazbeen_forex_ai.backtesting.services import execute_run

logger = logging.getLogger(__name__)


@shared_task(name="nazbeen_forex_ai.backtesting.run_backtest_task")
def run_backtest_task(run_id: str) -> str:
    """Execute a queued :class:`BacktestRun`; return its final status."""
    try:
        run = BacktestRun.objects.get(pk=run_id)
    except BacktestRun.DoesNotExist:
        logger.warning("run_backtest_task: run %s no longer exists", run_id)
        return "missing"

    try:
        execute_run(run)
    except Exception:  # noqa: BLE001 — execute_run already recorded a safe failure
        logger.exception("run_backtest_task: unexpected failure for run %s", run_id)
    run.refresh_from_db()
    return run.status
