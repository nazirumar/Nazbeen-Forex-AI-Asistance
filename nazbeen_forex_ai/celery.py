"""Celery application for Nazbeen Forex AI Asistance.

Expensive background work (analysis runs, model evaluation, walk-forward
testing) executes here — never in the request/response cycle.

Usage::

    celery -A nazbeen_forex_ai worker -l info
    celery -A nazbeen_forex_ai beat -l info
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nazbeen_forex_ai.settings.development")

app = Celery("nazbeen_forex_ai")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True, name="nazbeen_forex_ai.debug_task")
def debug_task(self) -> dict:
    """Minimal task used to verify broker connectivity end to end."""
    return {"result": "ok", "task": self.request.id}
