"""Tests for local IPC app endpoints used by the real device agent."""

from fastapi.testclient import TestClient

from homepot.agent.utils.local_ipc import LocalAgentState, create_local_ipc_app


def test_local_ipc_status_and_alias() -> None:
    """Both status routes should return the same agent state payload."""
    app = create_local_ipc_app(
        LocalAgentState(
            device_id="device-1",
            status="ONLINE",
            last_heartbeat="2026-04-13T12:00:00+00:00",
            last_telemetry={"cpu_usage": 20.5},
        )
    )
    client = TestClient(app)

    primary = client.get("/status")
    alias = client.get("/ipc/status")

    assert primary.status_code == 200
    assert alias.status_code == 200
    assert primary.json() == alias.json()
    assert primary.json()["device_id"] == "device-1"


def test_local_ipc_telemetry_and_alias() -> None:
    """Both telemetry routes should expose the same last telemetry payload."""
    app = create_local_ipc_app(
        LocalAgentState(
            device_id="device-1",
            status="ONLINE",
            last_telemetry={"cpu_usage": 20.5},
        )
    )
    client = TestClient(app)

    primary = client.get("/last-telemetry")
    alias = client.get("/ipc/last-telemetry")

    assert primary.status_code == 200
    assert alias.status_code == 200
    assert primary.json() == alias.json()
    assert primary.json()["data"]["cpu_usage"] == 20.5
