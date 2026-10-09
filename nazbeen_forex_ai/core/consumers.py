"""WebSocket consumers (Channels) — read-only operational status.

Analysis-only platform: these consumers expose **no trading actions** and never
accept commands that could affect orders (MASTER_SPEC §7 — LLM/generated text
must never execute trading commands; WebSockets follow the same rule).
"""

from __future__ import annotations

from datetime import datetime, timezone

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings

from nazbeen_forex_ai.core.views import check_cache, check_celery, check_database


def build_status_snapshot() -> dict:
    """Public status snapshot — identical data to GET /api/health/, no secrets."""
    checks = {
        "database": check_database(),
        "cache": check_cache(),
        "celery": check_celery(),
    }
    healthy = all(result in {"ok", "unconfigured", "eager"} for result in checks.values())
    return {
        "type": "status",
        "status": "ok" if healthy else "degraded",
        "service": "nazbeen-forex-ai",
        "version": settings.APP_VERSION,
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": checks,
    }


class StatusConsumer(AsyncJsonWebsocketConsumer):
    """``ws/status/`` — pushes a health snapshot on connect and on `ping`.

    Only `{"action": "ping"}` is accepted; anything else is rejected with an
    error message (no other actions exist by design — read-only surface).
    """

    async def connect(self) -> None:
        await self.accept()
        # Sync checks (DB/cache/broker) must run off the event loop.
        snapshot = await sync_to_async(build_status_snapshot)()
        await self.send_json(snapshot)

    async def receive_json(self, content: dict, **kwargs) -> None:
        action = content.get("action") if isinstance(content, dict) else None
        if action == "ping":
            await self.send_json({"type": "pong", "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
        else:
            await self.send_json(
                {"type": "error", "detail": "unknown action; supported: ping"}
            )

    async def disconnect(self, code: int) -> None:  # noqa: D102
        return None
