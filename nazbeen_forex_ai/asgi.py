"""ASGI entry point (Channels support arrives in Phase 10)."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nazbeen_forex_ai.settings.development")

application = get_asgi_application()
