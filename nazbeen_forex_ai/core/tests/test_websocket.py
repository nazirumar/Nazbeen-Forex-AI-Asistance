"""WebSocket status endpoint tests (Channels, Roadmap Phase 10)."""

from __future__ import annotations

import asyncio

import pytest
from channels.testing import WebsocketCommunicator

from nazbeen_forex_ai.asgi import application


def _connect_and_collect():
    async def scenario():
        communicator = WebsocketCommunicator(application, "/ws/status/")
        connected, _ = await communicator.connect()
        assert connected is True
        first = await communicator.receive_json_from()
        await communicator.send_json_to({"action": "ping"})
        pong = await communicator.receive_json_from()
        await communicator.send_json_to({"action": "shutdown-server"})
        rejected = await communicator.receive_json_from()
        await communicator.disconnect()
        return first, pong, rejected

    return asyncio.run(scenario())


@pytest.mark.django_db
def test_ws_status_pushes_snapshot_on_connect() -> None:
    first, pong, rejected = _connect_and_collect()
    assert first["type"] == "status"
    assert first["status"] in ("ok", "degraded")
    assert set(first["checks"]) == {"database", "cache", "celery"}
    assert "SECRET" not in str(first).upper()


@pytest.mark.django_db
def test_ws_status_ping_pong() -> None:
    _, pong, _ = _connect_and_collect()
    assert pong["type"] == "pong"
    assert pong["time"].endswith("Z")


@pytest.mark.django_db
def test_ws_rejects_unknown_actions() -> None:
    _, _, rejected = _connect_and_collect()
    assert rejected["type"] == "error"
    assert "unknown action" in rejected["detail"]
