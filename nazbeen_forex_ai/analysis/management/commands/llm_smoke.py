"""Smoke-test the configured LLM providers with one real call each.

Usage (after setting USE_MOCK_LLM=false and the <ROLE>_LLM_* variables):

    uv run python manage.py llm_smoke --role vision --image path/to/chart.png
    uv run python manage.py llm_smoke --role reasoning
    uv run python manage.py llm_smoke --role both --image chart.png

With USE_MOCK_LLM=true the command refuses to run (exit non-zero) unless
``--allow-mock`` is passed — a "smoke test" must never silently exercise the
mock provider and pretend a real provider works. ``--allow-mock`` prints a
clear MOCK banner so a wiring check is never mistaken for a live test.

The API key is never printed; only provider/model/latency and the (redacted)
model output are shown.
"""

from __future__ import annotations

import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from nazbeen_forex_ai.analysis import llm as llm_module
from nazbeen_forex_ai.analysis.llm_errors import LLMError

MAX_PRINT_CHARS = 600


class Command(BaseCommand):
    help = "Run one real call against the configured LLM provider(s) (smoke test)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--role",
            choices=["vision", "reasoning", "both"],
            default="both",
            help="Which configured provider to smoke-test (default: both).",
        )
        parser.add_argument(
            "--image",
            default="",
            help="Path to a chart screenshot PNG/JPG (required for the vision role).",
        )
        parser.add_argument(
            "--allow-mock",
            action="store_true",
            help="Permit running against the mock provider (wiring check only).",
        )

    def handle(self, *args: object, **options: dict) -> None:
        roles = ["vision", "reasoning"] if options["role"] == "both" else [options["role"]]
        use_mock = getattr(settings, "USE_MOCK_LLM", True)

        if use_mock and not options["allow_mock"]:
            raise CommandError(
                "USE_MOCK_LLM=true — the mock provider is active, so this would NOT "
                "test a real provider. Set USE_MOCK_LLM=false and configure "
                "<ROLE>_LLM_PROVIDER/_API_KEY/_MODEL, or pass --allow-mock for a "
                "wiring check."
            )

        for role in roles:
            image_bytes = None
            image_mime = None
            if role == "vision":
                image_path = options["image"]
                if not image_path:
                    raise CommandError(
                        "--image is required when smoke-testing the vision role."
                    )
                path = Path(image_path)
                if not path.is_file():
                    raise CommandError(f"image file not found: {path}")
                image_bytes = path.read_bytes()
                image_mime = "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png"

            try:
                provider = llm_module.get_llm_provider(role)
            except LLMError as exc:
                raise CommandError(f"{role} provider configuration failed: {exc}") from exc

            info = provider.describe()
            self.stdout.write(
                self.style.NOTICE(
                    f"[{'MOCK — NOT A REAL PROVIDER TEST' if info['mock'] else 'REAL PROVIDER'}] "
                    f"role={role} provider={info['provider']} model={info['model']}"
                )
            )

            started = time.monotonic()
            try:
                if role == "vision":
                    result = provider.inspect_chart(
                        "Smoke test: briefly describe what is visible in this chart screenshot.",
                        image_bytes,
                        image_mime,
                    )
                    elapsed = (time.monotonic() - started) * 1000
                    self.stdout.write(
                        f"latency_ms={elapsed:.0f}\n"
                        f"summary={result.summary[:MAX_PRINT_CHARS]}\n"
                        f"direction={result.direction}\n"
                        f"observed_symbol={result.observed_symbol} "
                        f"observed_timeframe={result.observed_timeframe}\n"
                        f"observations={len(result.observations)} "
                        f"candidate_levels={len(result.candidate_levels)} "
                        f"uncertainty={len(result.uncertainty)}"
                    )
                else:
                    result = provider.reason(
                        "Smoke test: in two sentences, explain why a forex analyst must "
                        "verify AI findings against deterministic market data."
                    )
                    elapsed = (time.monotonic() - started) * 1000
                    self.stdout.write(
                        f"latency_ms={elapsed:.0f}\n"
                        f"explanation={result.explanation[:MAX_PRINT_CHARS]}\n"
                        f"key_risks={len(result.key_risks)} uncertainty={len(result.uncertainty)}"
                    )
            except LLMError as exc:
                raise CommandError(f"{role} provider call failed: {exc}") from exc

        self.stdout.write(self.style.SUCCESS("LLM smoke test completed."))
