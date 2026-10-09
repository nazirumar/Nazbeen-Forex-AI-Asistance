"""Nazbeen Forex AI Asistance — Django project package."""

__version__ = "0.1.0"

# Bind the Celery app to shared_task so tasks resolve without explicit imports.
from nazbeen_forex_ai.celery import app as celery_app  # noqa: E402, F401

__all__ = ("celery_app", "__version__")
