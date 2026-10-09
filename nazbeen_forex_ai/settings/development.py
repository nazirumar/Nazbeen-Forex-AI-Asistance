"""Development settings — used by ``manage.py`` and the local runserver."""

from __future__ import annotations

from nazbeen_forex_ai.config import env_bool

from .base import *  # noqa: F403 — deliberate settings inheritance

DEBUG = env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = list(ALLOWED_HOSTS) + ["testserver"]  # noqa: F405

# Local dev: run Celery tasks in-process so the dashboard works without a
# running worker. Production settings never enable this.
if env_bool("CELERY_TASK_ALWAYS_EAGER", True):
    CELERY_TASK_ALWAYS_EAGER = True  # noqa: F405
