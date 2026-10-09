"""Tests verifying Celery/Redis configuration (Phase 1 acceptance criteria)."""

from __future__ import annotations

import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


def test_celery_app_is_configured_from_django_settings() -> None:
    from nazbeen_forex_ai.celery import app

    assert app.conf.timezone == "UTC"
    assert app.conf.enable_utc is True
    assert app.conf.task_serializer == "json"
    assert "json" in app.conf.accept_content


def test_debug_task_is_registered_and_runs_eager() -> None:
    from nazbeen_forex_ai.celery import app as celery_app

    assert "nazbeen_forex_ai.debug_task" in celery_app.tasks
    result = celery_app.tasks["nazbeen_forex_ai.debug_task"].apply()
    assert result.successful()
    assert result.result["result"] == "ok"


def test_task_always_eager_in_test_settings() -> None:
    from django.conf import settings

    assert settings.CELERY_TASK_ALWAYS_EAGER is True


@pytest.mark.django_db
def test_verify_infra_reports_configuration(capsys) -> None:
    call_command("verify_infra")
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["broker_url_configured"] is True
    assert report["result_backend_configured"] is True
    assert "nazbeen_forex_ai.debug_task" in report["registered_tasks"]


def test_verify_infra_ping_fails_loudly_without_broker() -> None:
    """--ping must exit non-zero when the broker is unreachable — never
    silently claim success."""
    from unittest.mock import patch

    from nazbeen_forex_ai.celery import app as celery_app

    with patch.object(
        celery_app.control, "ping", side_effect=ConnectionError("refused")
    ):
        with pytest.raises(CommandError):
            call_command("verify_infra", "--ping")
