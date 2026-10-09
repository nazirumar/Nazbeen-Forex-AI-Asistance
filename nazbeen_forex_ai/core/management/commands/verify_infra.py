"""Verify Redis and Celery configuration without side effects.

Prints the resolved configuration and, when a broker is reachable, performs a
real ping. Exits non-zero when configuration is broken, so scripts and CI can
rely on it.

    uv run python manage.py verify_infra
    uv run python manage.py verify_infra --ping
"""

from __future__ import annotations

import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Verify Redis/Celery configuration (optionally ping the broker)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--ping",
            action="store_true",
            help="Send a real ping to the Celery broker (requires a running Redis).",
        )

    def handle(self, *args: object, **options: dict) -> None:
        from nazbeen_forex_ai.celery import app as celery_app

        report: dict = {
            "broker_url_configured": bool(settings.CELERY_BROKER_URL),
            "result_backend_configured": bool(settings.CELERY_RESULT_BACKEND),
            "task_always_eager": settings.CELERY_TASK_ALWAYS_EAGER,
            "cache_backend": settings.CACHES["default"]["BACKEND"].rsplit(".", 1)[-1],
            "registered_tasks": sorted(celery_app.tasks.keys()),
        }

        if options["ping"]:
            if not settings.CELERY_BROKER_URL:
                raise CommandError(
                    "CELERY_BROKER_URL is not set; set REDIS_URL or "
                    "CELERY_BROKER_URL before pinging."
                )
            try:
                reply = celery_app.control.ping(timeout=2.0)
            except Exception as exc:  # noqa: BLE001 — report any broker failure
                raise CommandError(f"Broker ping failed: {exc}") from exc
            report["broker_ping"] = reply if reply else "no workers responding"

        self.stdout.write(json.dumps(report, indent=2))
        if not report["broker_url_configured"] and not options["ping"]:
            self.stdout.write(
                self.style.WARNING(
                    "NOTE: no broker configured (REDIS_URL empty). "
                    "Tasks run in-process only when CELERY_TASK_ALWAYS_EAGER=true."
                )
            )
