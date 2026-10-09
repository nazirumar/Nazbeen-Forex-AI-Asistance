"""ASGI entry point — HTTP (Django) + WebSockets (Channels, Roadmap Phase 10)."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nazbeen_forex_ai.settings.development")

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from django.urls import path  # noqa: E402

from nazbeen_forex_ai.core.consumers import StatusConsumer  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": URLRouter(
            [
                path("ws/status/", StatusConsumer.as_asgi()),
            ]
        ),
    }
)
