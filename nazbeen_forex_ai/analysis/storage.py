"""Screenshot storage helpers (secure file handling)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from django.conf import settings


def get_screenshot_upload_path(instance: Any, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return f"screenshots/{uuid.uuid4()}{ext}"


def screenshots_base_dir() -> Path:
    return Path(settings.MEDIA_ROOT) / "screenshots"
