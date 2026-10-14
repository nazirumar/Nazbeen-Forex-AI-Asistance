"""Celery tasks for forward testing (Phase 11G §9).

Routed to the "heavy" queue by ``CELERY_TASK_ROUTES``. In development and tests
Celery runs eagerly. A failure is captured on the run (status ``failed`` + safe
message); a failed cycle never fabricates a decision.
"""

from __future__ import annotations

import logging

from celery import shared_task

from nazbeen_forex_ai.forwardtest.models import ForwardTestRun
from nazbeen_forex_ai.forwardtest.services import (
    ForwardTestExecutionError,
    observe_run,
)

logger = logging.getLogger(__name__)


@shared_task(name="nazbeen_forex_ai.forwardtest.observe_run_task")
def observe_run_task(run_id: str) -> str:
    """Run one observation cycle for a forward test; return its final status."""
    try:
        run = ForwardTestRun.objects.get(pk=run_id)
    except (ForwardTestRun.DoesNotExist, ValueError):
        logger.warning("observe_run_task: run %s no longer exists", run_id)
        return "missing"

    try:
        observe_run(run)
    except ForwardTestExecutionError as exc:
        run.status = ForwardTestRun.Status.FAILED
        run.error = str(exc)[:500]
        run.save(update_fields=["status", "error"])
        logger.warning("observe_run_task: run %s failed safely: %s", run_id, exc)
    except Exception:  # noqa: BLE001 — never leak internals; record a safe failure
        run.status = ForwardTestRun.Status.FAILED
        run.error = "Forward-test observation failed."
        run.save(update_fields=["status", "error"])
        logger.exception("observe_run_task: unexpected failure for run %s", run_id)

    run.refresh_from_db()
    return run.status
