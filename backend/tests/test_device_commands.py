"""Tests for device command management."""

from fastapi.testclient import TestClient


# Use the client fixture from conftest.py
def test_device_command_flow(client: TestClient):
    """Test the full flow of device management.

    1. Create Site
    2. Create Device (get API Key)
    3. Queue Command
    4. Retrieve Pending Commands (as Device)
    """
    # 1. Create Site
    site_id = "test-site-cmd-flow"
    site_data = {
        "site_id": site_id,
        "name": "Command Flow Test Site",
        "location": "Test Lab",
    }
    response = client.post("/api/v1/sites/", json=site_data)
    # Handle case where site might already exist from previous runs (though DB should be fresh in tests)
    if response.status_code != 409:
        assert response.status_code == 200

    # 2. Create Device
    device_id = "test-device-cmd-flow"
    device_data = {
        "device_id": device_id,
        "name": "Command Flow Device",
        "device_type": "pos_terminal",
    }
    response = client.post(f"/api/v1/devices/sites/{site_id}/devices", json=device_data)
    assert response.status_code == 200
    data = response.json()
    assert "api_key" in data
    api_key = data["api_key"]

    # 3. Queue Command
    command_payload = {
        "command_type": "REBOOT",
        "payload": {"reason": "integration_test"},
    }
    response = client.post(
        f"/api/v1/devices/{device_id}/commands", json=command_payload
    )
    assert response.status_code == 201
    cmd_data = response.json()
    command_id = cmd_data["command_id"]
    assert cmd_data["status"] == "pending"

    # 4. Get Pending Commands (As Device)
    headers = {"X-Device-ID": device_id, "X-API-Key": api_key}
    response = client.get("/api/v1/devices/pending", headers=headers)
    assert response.status_code == 200
    pending_cmds = response.json()

    # Verify our command is in the list
    found = False
    for cmd in pending_cmds:
        if cmd["command_id"] == command_id:
            found = True
            assert cmd["command_type"] == "REBOOT"
            break
    assert found, "Queued command not found in pending list"


def test_device_auth_failure(client: TestClient):
    """Test that invalid credentials are rejected."""
    headers = {"X-Device-ID": "non-existent-device", "X-API-Key": "invalid-key"}
    response = client.get("/api/v1/devices/pending", headers=headers)
    assert response.status_code == 401
