"""Tests for agent registration, heartbeat, telemetry, provision, and status APIs."""

import asyncio
from datetime import datetime, timedelta, timezone
import os
import tempfile

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from homepot.app.auth_utils import create_access_token, hash_password
from homepot.app.models.AnalyticsModel import DeviceMetrics
from homepot.canonical_ids import _DEVICE_ID_PATTERN
from homepot.config import reload_settings
import homepot.database
import homepot.models
from homepot.models import (
    Base,
    CommandStatus,
    Device,
    DeviceCommand,
    LifecycleState,
    Site,
    User,
)


@pytest.fixture(autouse=True)
def mock_db_url(monkeypatch):
    """Use a temporary SQLite DB so tests do not touch real data."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    db_url = f"sqlite:///{path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DATABASE__URL", db_url)
    reload_settings()

    if homepot.database._db_service is not None:
        try:
            asyncio.run(homepot.database._db_service.close())
        except Exception:
            pass
        homepot.database._db_service = None

    new_engine = create_engine(
        db_url, connect_args={"check_same_thread": False}, pool_pre_ping=True
    )
    Base.metadata.create_all(bind=new_engine)
    new_session_local = sessionmaker(bind=new_engine, autocommit=False, autoflush=False)

    monkeypatch.setattr(homepot.database, "sync_engine", new_engine)
    monkeypatch.setattr(homepot.database, "SessionLocal", new_session_local)

    yield

    new_engine.dispose()
    if os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


def _create_site(site_code: str = "site-agent-1") -> Site:
    """Create and return a site row for endpoint tests."""
    db = homepot.database.SessionLocal()
    try:
        site = Site(site_id=site_code, name="Agent Test Site", location="Lab")
        db.add(site)
        db.commit()
        db.refresh(site)
        return site
    finally:
        db.close()


def _create_device(device_id: str, site_pk: int, api_key: str = "test-api-key") -> str:
    """Create a device row linked to a site primary key."""
    db = homepot.database.SessionLocal()
    try:
        device = Device(
            device_id=device_id,
            name="Agent Device",
            device_type="pos_terminal",
            site_id=site_pk,
            api_key_hash=hash_password(api_key),
            is_active=True,
            lifecycle_state=LifecycleState.ACTIVE.value,
        )
        db.add(device)
        db.commit()
    finally:
        db.close()
    return api_key


def _device_headers(device_id: str, api_key: str) -> dict[str, str]:
    return {"X-Device-ID": device_id, "X-API-Key": api_key}


def _set_device_permissions(device_id: str, permissions: dict[str, bool]) -> None:
    """Set the device_permissions JSON column for a device row."""
    db = homepot.database.SessionLocal()
    try:
        device = db.query(Device).filter(Device.device_id == device_id).first()
        device.device_permissions = permissions
        db.commit()
    finally:
        db.close()


def _grant_monitor(device_id: str) -> None:
    """Grant the Monitor (read-only diagnostics) tier to a device row."""
    _set_device_permissions(
        device_id,
        {
            "command_execution": True,
            "process_monitoring": True,
            "filesystem_access": True,
            "network_monitoring": True,
        },
    )


def _create_commands_for_device(
    device_id: str, count: int = 1, command_type: str = "ping"
) -> None:
    """Insert DeviceCommand rows linked to a device via the async DB service."""
    db = homepot.database.SessionLocal()
    try:
        device_pk = db.query(Device).filter(Device.device_id == device_id).first().id
        for i in range(count):
            db.add(
                DeviceCommand(
                    command_id=f"{device_id}-cmd-{i}",
                    device_id=device_pk,
                    command_type=command_type,
                    payload={"index": i},
                    status=CommandStatus.COMPLETED.value,
                    result={"ok": True},
                )
            )
        db.commit()
    finally:
        db.close()


def test_register_updates_authenticated_device(client: TestClient):
    """POST /api/v1/agent/device-dna should update the provisioned device."""
    site = _create_site("site-agent-1")
    api_key = _create_device("agent-device-1", int(site.id))
    response = client.post(
        "/api/v1/agent/device-dna",
        json={
            "device_id": "agent-device-1",
            "site_id": "site-agent-1",
            "device_name": "Front POS",
            "device_type": "pos_terminal",
            "mac_address": "00:11:22:33:44:55",
            "os_details": "Windows 11",
            "local_ip": "192.168.1.20",
            "wan_ip": "203.0.113.10",
        },
        headers=_device_headers("agent-device-1", api_key),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["device_id"] == "agent-device-1"
    assert payload["data"]["created"] is False


def test_heartbeat_updates_last_heartbeat(client: TestClient):
    """POST /api/v1/agent/heartbeat should update last heartbeat timestamp."""
    site = _create_site("site-heartbeat")
    api_key = _create_device("heartbeat-device-1", int(site.id))

    now = datetime.now(timezone.utc).isoformat()
    response = client.post(
        "/api/v1/agent/heartbeat",
        json={"device_id": "heartbeat-device-1", "timestamp": now},
        headers=_device_headers("heartbeat-device-1", api_key),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["device_id"] == "heartbeat-device-1"
    assert payload["data"]["last_heartbeat_at"] is not None


def test_offline_heartbeat_marks_device_offline(client: TestClient):
    """A heartbeat with online=false marks the device OFFLINE immediately."""
    from homepot.models import Device, DeviceStatus

    site = _create_site("site-heartbeat-offline")
    api_key = _create_device("heartbeat-offline-1", int(site.id))

    now = datetime.now(timezone.utc).isoformat()
    response = client.post(
        "/api/v1/agent/heartbeat",
        json={"device_id": "heartbeat-offline-1", "timestamp": now, "online": False},
        headers=_device_headers("heartbeat-offline-1", api_key),
    )
    assert response.status_code == 200

    db = homepot.database.SessionLocal()
    try:
        device = (
            db.query(Device).filter(Device.device_id == "heartbeat-offline-1").first()
        )
        assert device is not None
        assert device.status == DeviceStatus.OFFLINE.value
        assert device.last_heartbeat_at is None
    finally:
        db.close()


def test_telemetry_single_is_saved(client: TestClient):
    """POST /api/v1/agent/telemetry should persist a single telemetry record."""
    site = _create_site("site-telemetry-single")
    api_key = _create_device("telemetry-device-1", int(site.id))

    response = client.post(
        "/api/v1/agent/telemetry",
        json={
            "device_id": "telemetry-device-1",
            "cpu_usage": 20.1,
            "memory_usage": 55.4,
            "disk_usage": 44.8,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        headers=_device_headers("telemetry-device-1", api_key),
    )

    assert response.status_code == 200
    assert response.json()["data"]["saved_count"] == 1

    db = homepot.database.SessionLocal()
    try:
        metrics_count = db.execute(select(DeviceMetrics)).scalars().all()
        assert len(metrics_count) == 1
    finally:
        db.close()


def test_telemetry_bulk_is_saved(client: TestClient):
    """POST /api/v1/agent/telemetry should persist multiple telemetry records."""
    site = _create_site("site-telemetry-bulk")
    api_key = _create_device("telemetry-device-2", int(site.id))

    now = datetime.now(timezone.utc)
    response = client.post(
        "/api/v1/agent/telemetry",
        json=[
            {
                "device_id": "telemetry-device-2",
                "cpu_usage": 21.0,
                "memory_usage": 56.0,
                "disk_usage": 45.0,
                "timestamp": now.isoformat(),
            },
            {
                "device_id": "telemetry-device-2",
                "cpu_usage": 22.0,
                "memory_usage": 57.0,
                "disk_usage": 46.0,
                "timestamp": (now + timedelta(seconds=30)).isoformat(),
            },
        ],
        headers=_device_headers("telemetry-device-2", api_key),
    )

    assert response.status_code == 200
    assert response.json()["data"]["saved_count"] == 2


def test_metrics_returns_latest_telemetry(client: TestClient):
    """GET /api/v1/agent/{device_id}/metrics should return the latest entry."""
    site = _create_site("site-metrics-latest")
    api_key = _create_device("metrics-device-1", int(site.id))
    _grant_monitor("metrics-device-1")

    post = client.post(
        "/api/v1/agent/telemetry",
        json={
            "device_id": "metrics-device-1",
            "cpu_usage": 30.0,
            "memory_usage": 61.0,
            "disk_usage": 48.0,
            "network_latency_ms": 12.5,
            "uptime_seconds": 3600,
        },
        headers=_device_headers("metrics-device-1", api_key),
    )
    assert post.status_code == 200

    response = client.get(
        "/api/v1/agent/metrics-device-1/metrics",
        headers=_device_headers("metrics-device-1", api_key),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["device_id"] == "metrics-device-1"
    assert data["cpu_percent"] == 30.0
    assert data["memory_percent"] == 61.0
    assert data["disk_percent"] == 48.0
    assert data["network_latency_ms"] == 12.5
    assert data["uptime_seconds"] == 3600
    assert data["timestamp"] is not None


def test_metrics_returns_empty_values_when_no_telemetry(client: TestClient):
    """GET metrics should return null fields when no telemetry exists yet."""
    site = _create_site("site-metrics-empty")
    api_key = _create_device("metrics-device-2", int(site.id))
    _grant_monitor("metrics-device-2")

    response = client.get(
        "/api/v1/agent/metrics-device-2/metrics",
        headers=_device_headers("metrics-device-2", api_key),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["cpu_percent"] is None
    assert data["memory_percent"] is None
    assert data["uptime_seconds"] is None


def test_metrics_rejects_other_devices_and_missing_credentials(client: TestClient):
    """GET metrics should 403 for another device and 401 without credentials."""
    site = _create_site("site-metrics-auth")
    api_key = _create_device("metrics-device-3", int(site.id))
    _create_device("metrics-device-4", int(site.id), api_key="other-key")

    other = client.get(
        "/api/v1/agent/metrics-device-4/metrics",
        headers=_device_headers("metrics-device-3", api_key),
    )
    assert other.status_code == 403

    missing = client.get("/api/v1/agent/metrics-device-3/metrics")
    assert missing.status_code == 401


def test_metrics_history_returns_time_ordered_samples(client: TestClient):
    """GET /api/v1/agent/{device_id}/metrics/history returns samples oldest-first."""
    site = _create_site("site-metrics-history")
    api_key = _create_device("metrics-device-5", int(site.id))
    _grant_monitor("metrics-device-5")

    for i, cpu in enumerate([20.0, 40.0, 60.0]):
        post = client.post(
            "/api/v1/agent/telemetry",
            json={
                "device_id": "metrics-device-5",
                "cpu_usage": cpu,
                "memory_usage": 50.0 + i,
                "disk_usage": 30.0,
                "network_latency_ms": 10.0 + i,
                "uptime_seconds": 1000 + i,
            },
            headers=_device_headers("metrics-device-5", api_key),
        )
        assert post.status_code == 200

    response = client.get(
        "/api/v1/agent/metrics-device-5/metrics/history?limit=10",
        headers=_device_headers("metrics-device-5", api_key),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 3
    assert [sample["cpu_percent"] for sample in data] == [20.0, 40.0, 60.0]
    assert data[-1]["memory_percent"] == 52.0
    assert data[-1]["uptime_seconds"] == 1002


def test_metrics_history_rejects_other_devices(client: TestClient):
    """GET metrics/history should 403 for another device."""
    site = _create_site("site-metrics-history-auth")
    api_key = _create_device("metrics-device-6", int(site.id))
    _create_device("metrics-device-7", int(site.id), api_key="other-key")

    response = client.get(
        "/api/v1/agent/metrics-device-7/metrics/history",
        headers=_device_headers("metrics-device-6", api_key),
    )
    assert response.status_code == 403


def test_provision_returns_credentials_and_hashes_key(client: TestClient):
    """POST /api/v1/devices/provision should return credentials and persist hash."""
    _create_site("site-provision")

    db = homepot.database.SessionLocal()
    try:
        admin = User(
            email="admin@provision.test",
            username="admin_provision",
            hashed_password=hash_password("pass"),
            is_admin=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(admin)
        db.commit()
    finally:
        db.close()

    token = create_access_token({"sub": "admin@provision.test"})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/devices/provision",
        json={
            "sso_token": "sample-sso-token",
            "site_id": "site-provision",
            "user_identity": "setup.user@dealdio.com",
            "device_name": "Provisioned POS",
            "device_type": "pos_terminal",
            "os_details": "Android 13",
        },
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["device_id"]
    assert _DEVICE_ID_PATTERN.fullmatch(payload["data"]["device_id"])
    assert payload["data"]["api_key"]

    created_device_id = payload["data"]["device_id"]
    db = homepot.database.SessionLocal()
    try:
        device = (
            db.execute(select(Device).where(Device.device_id == created_device_id))
            .scalars()
            .first()
        )
        assert device is not None
        assert device.api_key_hash is not None
        assert device.device_type == "pos_terminal"
        assert device.os_details == "Android 13"
    finally:
        db.close()


def test_status_returns_online_when_recent_heartbeat_exists(client: TestClient):
    """GET /api/v1/agent/{device_id}/status should return ONLINE for fresh heartbeat."""
    site = _create_site("site-status")
    api_key = _create_device("status-device-1", int(site.id))

    recent = datetime.now(timezone.utc).isoformat()
    hb_response = client.post(
        "/api/v1/agent/heartbeat",
        json={"device_id": "status-device-1", "timestamp": recent},
        headers=_device_headers("status-device-1", api_key),
    )
    assert hb_response.status_code == 200

    status_response = client.get("/api/v1/agent/status-device-1/status")
    assert status_response.status_code == 200
    assert status_response.json()["data"]["connectivity_state"] == "online"


def test_agent_telemetry_requires_matching_device_credentials(client: TestClient):
    """Agent telemetry must reject missing or mismatched device credentials."""
    site = _create_site("site-agent-auth")
    api_key = _create_device("authenticated-device", int(site.id))
    payload = {
        "device_id": "authenticated-device",
        "cpu_usage": 20.0,
        "memory_usage": 30.0,
        "disk_usage": 40.0,
    }

    missing_credentials = client.post("/api/v1/agent/telemetry", json=payload)
    assert missing_credentials.status_code == 401

    mismatched_device = client.post(
        "/api/v1/agent/telemetry",
        json=payload,
        headers=_device_headers("other-device", api_key),
    )
    assert mismatched_device.status_code == 401


def test_logs_returns_device_log_lines(client: TestClient):
    """GET /api/v1/agent/{device_id}/logs should return the device's log lines."""
    site = _create_site("site-activity-logs")
    api_key = _create_device("activity-log-device", int(site.id))
    _grant_monitor("activity-log-device")

    posted = client.post(
        "/api/v1/agent/logs",
        json={
            "device_id": "activity-log-device",
            "level": "warning",
            "category": "network",
            "message": "WAN link flapping detected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        headers=_device_headers("activity-log-device", api_key),
    )
    assert posted.status_code == 200

    response = client.get(
        "/api/v1/agent/activity-log-device/logs",
        headers=_device_headers("activity-log-device", api_key),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["error_message"] == "WAN link flapping detected"
    assert data[0]["severity"] == "warning"
    assert data[0]["category"] == "network"


def test_logs_rejects_other_devices_and_missing_credentials(client: TestClient):
    """Log reads should 403 for another device and 401 without credentials."""
    site = _create_site("site-activity-auth")
    api_key = _create_device("activity-auth-device-1", int(site.id))
    _create_device("activity-auth-device-2", int(site.id), api_key="other-key")

    other = client.get(
        "/api/v1/agent/activity-auth-device-2/logs",
        headers=_device_headers("activity-auth-device-1", api_key),
    )
    assert other.status_code == 403

    missing = client.get("/api/v1/agent/activity-auth-device-1/logs")
    assert missing.status_code == 401


def test_audit_returns_device_audit_events(client: TestClient):
    """GET /api/v1/agent/{device_id}/audit should return the device's audit events."""
    site = _create_site("site-activity-audit")
    api_key = _create_device("activity-audit-device", int(site.id))
    _grant_monitor("activity-audit-device")

    posted = client.post(
        "/api/v1/agent/audit",
        json={
            "device_id": "activity-audit-device",
            "event_type": "permission_change",
            "description": "Root access granted by owner",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {"permission": "root_access", "granted": True},
        },
        headers=_device_headers("activity-audit-device", api_key),
    )
    assert posted.status_code == 200

    response = client.get(
        "/api/v1/agent/activity-audit-device/audit",
        headers=_device_headers("activity-audit-device", api_key),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["event_type"] == "permission_change"
    assert data[0]["description"] == "Root access granted by owner"
    assert data[0]["event_metadata"]["permission"] == "root_access"


def test_audit_rejects_other_devices_and_missing_credentials(client: TestClient):
    """Audit reads should 403 for another device and 401 without credentials."""
    site = _create_site("site-activity-audit-auth")
    api_key = _create_device("activity-audit-auth-1", int(site.id))
    _create_device("activity-audit-auth-2", int(site.id), api_key="other-key")

    other = client.get(
        "/api/v1/agent/activity-audit-auth-2/audit",
        headers=_device_headers("activity-audit-auth-1", api_key),
    )
    assert other.status_code == 403

    missing = client.get("/api/v1/agent/activity-audit-auth-1/audit")
    assert missing.status_code == 401


def _grant_manage(device_id: str) -> None:
    """Grant the Manage (root_access) permission to a device row."""
    db = homepot.database.SessionLocal()
    try:
        device = db.query(Device).filter(Device.device_id == device_id).first()
        assert device is not None
        device.device_permissions = {
            "root_access": True,
            "command_execution": True,
            "process_monitoring": True,
            "filesystem_access": True,
            "network_monitoring": True,
        }
        db.commit()
    finally:
        db.close()


def _seed_command(
    device_id: str, command_type: str, payload: dict | None = None
) -> None:
    """Insert a command row for a device."""
    db = homepot.database.SessionLocal()
    try:
        device = db.query(Device).filter(Device.device_id == device_id).first()
        assert device is not None
        command = homepot.models.DeviceCommand(
            command_id=f"cmd-{command_type}-{device_id}",
            device_id=device.id,
            command_type=command_type,
            payload=payload or {},
            status="completed",
            result={"ok": True},
        )
        db.add(command)
        db.commit()
    finally:
        db.close()


def test_command_history_returns_device_commands(client: TestClient):
    """GET /api/v1/agent/{device_id}/commands returns the device's commands."""
    site = _create_site("site-activity-commands")
    api_key = _create_device("activity-command-device-1", int(site.id))
    _grant_manage("activity-command-device-1")
    _seed_command("activity-command-device-1", "run_command", {"cmd": "echo hi"})
    _seed_command("activity-command-device-1", "restart")

    response = client.get(
        "/api/v1/agent/activity-command-device-1/commands",
        headers=_device_headers("activity-command-device-1", api_key),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2
    statuses = {item["command_type"] for item in data}
    assert statuses == {"run_command", "restart"}
    run = next(item for item in data if item["command_type"] == "run_command")
    assert run["command_id"].startswith("cmd-run_command-")
    assert run["status"] == "completed"
    assert run["payload"]["cmd"] == "echo hi"
    assert run["sent_at"] is None


def test_command_history_requires_manage_permission(client: TestClient):
    """Command history reads require the Manage (root_access) permission."""
    site = _create_site("site-activity-commands-manage")
    api_key = _create_device("activity-command-device-manage", int(site.id))

    denied = client.get(
        "/api/v1/agent/activity-command-device-manage/commands",
        headers=_device_headers("activity-command-device-manage", api_key),
    )
    assert denied.status_code == 403


def test_command_history_rejects_other_devices_and_missing_credentials(
    client: TestClient,
):
    """Command history reads 403 for another device and 401 without credentials."""
    site = _create_site("site-activity-commands-auth")
    api_key = _create_device("activity-command-auth-1", int(site.id))
    _grant_manage("activity-command-auth-1")
    _create_device("activity-command-auth-2", int(site.id), api_key="other-key")

    other = client.get(
        "/api/v1/agent/activity-command-auth-2/commands",
        headers=_device_headers("activity-command-auth-1", api_key),
    )
    assert other.status_code == 403

    missing = client.get("/api/v1/agent/activity-command-auth-1/commands")
    assert missing.status_code == 401


def test_alerts_returns_device_alerts(client: TestClient):
    """GET /api/v1/agent/{device_id}/alerts returns the device's alerts."""
    site = _create_site("site-activity-alerts")
    api_key = _create_device("activity-alert-device-1", int(site.id))
    _grant_monitor("activity-alert-device-1")

    posted = client.post(
        "/api/v1/agent/alert",
        json={
            "device_id": "activity-alert-device-1",
            "title": "Disk usage high",
            "description": "Disk at 92%",
            "severity": "high",
            "category": "hardware",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        headers=_device_headers("activity-alert-device-1", api_key),
    )
    assert posted.status_code == 200

    response = client.get(
        "/api/v1/agent/activity-alert-device-1/alerts",
        headers=_device_headers("activity-alert-device-1", api_key),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["title"] == "Disk usage high"
    assert data[0]["severity"] == "high"
    assert data[0]["category"] == "hardware"


def test_alerts_requires_monitor_permission(client: TestClient):
    """Alerts reads require the Monitor tier."""
    site = _create_site("site-activity-alerts-monitor")
    api_key = _create_device("activity-alert-device-monitor", int(site.id))

    denied = client.get(
        "/api/v1/agent/activity-alert-device-monitor/alerts",
        headers=_device_headers("activity-alert-device-monitor", api_key),
    )
    assert denied.status_code == 403


def test_alerts_rejects_other_devices_and_missing_credentials(client: TestClient):
    """Alerts reads 403 for another device and 401 without credentials."""
    site = _create_site("site-activity-alerts-auth")
    api_key = _create_device("activity-alert-auth-1", int(site.id))
    _grant_monitor("activity-alert-auth-1")
    _create_device("activity-alert-auth-2", int(site.id), api_key="other-key")

    other = client.get(
        "/api/v1/agent/activity-alert-auth-2/alerts",
        headers=_device_headers("activity-alert-auth-1", api_key),
    )
    assert other.status_code == 403

    missing = client.get("/api/v1/agent/activity-alert-auth-1/alerts")
    assert missing.status_code == 401


def test_diagnostics_require_monitor_permission(client: TestClient):
    """Metrics, logs, and audit reads require the Monitor tier."""
    site = _create_site("site-diagnostics-monitor")
    api_key = _create_device("diagnostics-device-1", int(site.id))
    headers = _device_headers("diagnostics-device-1", api_key)

    assert (
        client.get(
            "/api/v1/agent/diagnostics-device-1/metrics", headers=headers
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/v1/agent/diagnostics-device-1/logs", headers=headers
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/v1/agent/diagnostics-device-1/audit", headers=headers
        ).status_code
        == 403
    )
