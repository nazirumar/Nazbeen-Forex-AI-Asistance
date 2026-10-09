"""Image validation and constraints for screenshot uploads.

Strict by design (audit H-01): unsupported extensions, unsupported content
types, non-image content and oversized files are all rejected with a
``ValidationError`` — the caller turns that into a safe HTTP 400.
"""

from __future__ import annotations

import mimetypes
import os
from io import BytesIO
from typing import Any

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB


def validate_image_upload(uploaded_file) -> dict[str, Any]:
    """Validate an uploaded screenshot. Raises ``ValidationError`` on any problem.

    Checks performed, in cheap-to-expensive order:
    1. Presence and non-zero size.
    2. Size against the configured limit (checked before reading content).
    3. File extension whitelist.
    4. Content-type whitelist.
    5. Real image decoding via Pillow (``Image.verify()``) so arbitrary bytes
       with an image extension are rejected.
    """
    if not uploaded_file:
        raise ValidationError("No file provided.")

    file_size = uploaded_file.size or 0
    if file_size <= 0:
        raise ValidationError("Empty file.")
    if file_size > MAX_IMAGE_SIZE_BYTES:
        raise ValidationError(
            f"Image too large. Max {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)}MB allowed."
        )

    name = uploaded_file.name or ""
    ext = os.path.splitext(name.lower())[1]
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(f"Unsupported file extension: {ext}")

    content_type = uploaded_file.content_type or mimetypes.guess_type(name)[0] or ""
    if content_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise ValidationError(f"Unsupported content type: {content_type}")

    # Content verification: the bytes must actually decode as a supported image.
    # Work from an in-memory copy so Pillow never closes the caller's file.
    try:
        uploaded_file.seek(0)
        raw = uploaded_file.read()
        uploaded_file.seek(0)
    except Exception:
        raise ValidationError("Unable to read uploaded file.")
    try:
        with Image.open(BytesIO(raw)) as img:
            img.verify()
            fmt = (img.format or "").lower()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise ValidationError("Invalid or corrupt image file.")

    # The decoded format must match the declared extension.
    ext_to_fmt = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp"}
    if fmt and ext_to_fmt.get(ext) != fmt:
        raise ValidationError(f"Image content ({fmt}) does not match extension ({ext}).")

    return {
        "size_bytes": file_size,
        "content_type": content_type,
        "extension": ext,
        "format": fmt,
    }
