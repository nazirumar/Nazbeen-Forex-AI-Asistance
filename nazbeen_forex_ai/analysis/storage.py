"""Screenshot storage helpers (secure file handling — audit H-02).

Screenshots are persisted under ``MEDIA_ROOT/screenshots`` with
**server-generated** names (UUID), so a client can never influence the storage
path (no traversal via crafted filenames). Callers store only the returned
relative path; retrieval re-validates that the resolved path stays inside the
screenshots base directory.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

from django.conf import settings

# Extensions accepted for persisted screenshots (validation happens upstream
# in analysis.validators; this is defense in depth).
ALLOWED_SCREENSHOT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def get_screenshot_upload_path(instance, filename: str) -> str:  # noqa: ANN001
    """Django ``upload_to`` hook: server-side UUID name under screenshots/."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_SCREENSHOT_EXTENSIONS:
        ext = ".png"
    return f"screenshots/{uuid.uuid4().hex}{ext}"


def screenshots_base_dir() -> Path:
    return Path(settings.MEDIA_ROOT) / "screenshots"


def save_screenshot(data: bytes, original_name: str) -> str:
    """Persist screenshot bytes with a server-generated name.

    Returns the storage-relative POSIX path (e.g. ``screenshots/<uuid>.png``).
    Raises OSError on write failure — callers decide whether persistence
    failure should fail the request (it must not fabricate a stored path).
    """
    if not data:
        raise ValueError("cannot persist an empty screenshot")
    rel = get_screenshot_upload_path(None, original_name)
    base = screenshots_base_dir()
    base.mkdir(parents=True, exist_ok=True)
    # rel is server-generated; joining its basename cannot escape `base`.
    target = base / Path(rel).name
    target.write_bytes(data)
    return rel


def resolve_screenshot_path(relative_path: str) -> Optional[Path]:
    """Resolve a stored MEDIA_ROOT-relative path, refusing anything outside
    the screenshots base dir.

    Stored paths look like ``screenshots/<uuid>.png`` (relative to
    ``MEDIA_ROOT``). Returns None for empty, absolute, or traversal-style
    paths — the caller treats that as "not found", never serving an arbitrary
    file.
    """
    if not relative_path:
        return None
    root = Path(settings.MEDIA_ROOT).resolve()
    base = (root / "screenshots").resolve()
    target = (root / os.path.normpath(relative_path)).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return None
    return target
