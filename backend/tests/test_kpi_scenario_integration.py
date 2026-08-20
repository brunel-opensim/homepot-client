"""End-to-end KPI evidence-flow scenario coverage.

Exercises the full write pipeline (device telemetry, state changes, command
queuing/ack/status, agent config-history) through the public API and then
verifies the KPI export reflects the produced evidence: MW-01/02 completion
and round-trip, MW-03/04/05 config outcomes, PF-LAT latency percentiles and
EQ-01 provenance coverage. Also verifies provenance classes stay separated
across the API boundary.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import os
import secrets
import tempfile

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from homepot.app.auth_utils import create_access_token, hash_password
from homepot.config import reload_settings
import homepot.database
from homepot.models import (
    Base,
    Device,
    LifecycleState,
    Site,
    User,
)

EXPORT_URL = "/api/v1/kpi/export"
ADMIN_EMAIL = "admin.scenario@test.local"
WIDE_START = "2020-01-01T00:00:00Z"
WIDE_END = "2099-12-31T23:59:59Z"


@pytest.fixture(autouse=True)
def mock_db_url(monkeypatch):
    """Use a temporary database for these tests.

    The app's async ``DatabaseService`` is created here on the test event
    loop (not inside the TestClient lifespan portal), which avoids a SQLite
    write-lock race between the sync engine and the portal's async engine.
    """
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
    NewSessionLocal = sessionmaker(bind=new_engine, autocommit=False, autoflush=False)

    monkeypatch.setattr(homepot.database, "sync_engine", new_engine)
    monkeypatch.setattr(homepot.database, "SessionLocal", NewSessionLocal)

    asyncio.run(homepot.database.get_database_service())

    yield

    asyncio.run(homepot.database.close_database_service())
    new_engine.dispose()
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(path + suffix):
            try:
                os.unlink(path + suffix)
            except OSError:
                pass


@pytest.fixture
def client():
    """Create a TestClient without the app lifespan (the async DB init race).

    The async database service is pre-created by ``mock_db_url`` above, so
    running the startup lifespan here would only recreate it inside the
    TestClient portal and re-trigger the lock race.
    """
    from homepot.main import app

    return TestClient(app)


def _seed_admin() -> None:
    db = homepot.database.SessionLocal()
    try:
        if not db.query(User).filter(User.email == ADMIN_EMAIL).first():
            db.add(
                User(
                    email=ADMIN_EMAIL,
                    username="admin_scenario",
                    hashed_password=hash_password("pass"),
                    is_admin=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            db.commit()
    finally:
        db.close()


def _seed_site_device(device_id: str, site_id: str, device_source: str) -> str:
    """Create a site + device and return the device's plaintext API key."""
    db = homepot.database.SessionLocal()
    try:
        site = db.query(Site).filter(Site.site_id == site_id).first()
        if not site:
            site = Site(site_id=site_id, name=f"Site {site_id}")
            db.add(site)
            db.commit()
        api_key = secrets.token_urlsafe(32)
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if not device:
            db.add(
                Device(
                    device_id=device_id,
                    name=f"Device {device_id}",
                    device_type="pos_terminal",
                    site_id=site.id,
                    api_key_hash=hash_password(api_key),
                    is_active=True,
                    lifecycle_state=LifecycleState.ACTIVE.value,
                    config={"device_source": device_source},
                )
            )
            db.commit()
        return api_key
    finally:
        db.close()


def _device_headers(device_id: str, api_key: str) -> dict:
    return {"X-Device-ID": device_id, "X-API-Key": api_key}


def _user_headers() -> dict:
    _seed_admin()
    token = create_access_token({"sub": ADMIN_EMAIL})
    return {"Authorization": f"Bearer {token}"}


def _result(bundle: dict, kpi_id: str, provenance: str = "all", **group) -> dict:
    for kpi in bundle["kpis"]:
        if kpi["kpi_id"] != kpi_id or kpi["provenance"] != provenance:
            continue
        if group and kpi.get("group") != group:
            continue
        return kpi
    raise AssertionError(
        f"No KPI {kpi_id} for provenance {provenance} group {group} in {bundle['kpis']}"
    )


def test_end_to_end_evidence_flow_yields_kpis(client: TestClient) -> None:
    """Telemetry, commands and config events through the API drive every KPI."""
    api_key = _seed_site_device("e2e-pos-001", "site-e2e-1", "physical")
    device_headers = _device_headers("e2e-pos-001", api_key)
    user_headers = _user_headers()

    # 1. Device telemetry: two distinct latency samples.
    for latency in (100.0, 200.0):
        resp = client.post(
            "/api/v1/analytics/device-metrics",
            json={
                "device_id": "e2e-pos-001",
                "network_latency_ms": latency,
                "cpu_percent": 20.0,
                "collection_interval_seconds": 5,
            },
            headers=device_headers,
        )
        assert resp.status_code == 201, resp.text

    # 2. A state transition.
    resp = client.post(
        "/api/v1/analytics/device-state-change",
        json={
            "device_id": "e2e-pos-001",
            "previous_state": "provisioning",
            "new_state": "online",
            "reason": "agent online",
        },
        headers=user_headers,
    )
    assert resp.status_code == 201, resp.text

    # 3. Queue, ack and complete a ping command with a known executed_at.
    resp = client.post(
        "/api/v1/devices/e2e-pos-001/commands",
        json={"command_type": "ping", "payload": {}},
        headers=user_headers,
    )
    assert resp.status_code == 201, resp.text
    cmd_payload = resp.json()
    command_id = cmd_payload["command_id"]
    created_at = datetime.fromisoformat(cmd_payload["created_at"])

    resp = client.post(
        f"/api/v1/devices/e2e-pos-001/commands/{command_id}/ack",
        headers=device_headers,
    )
    assert resp.status_code == 200, resp.text

    executed_at = (created_at + timedelta(seconds=5)).isoformat()
    resp = client.put(
        f"/api/v1/devices/{command_id}/status",
        json={"status": "completed", "executed_at": executed_at},
        headers=device_headers,
    )
    assert resp.status_code == 200, resp.text

    # 4. Config-history: one successful verified change and one rollback.
    resp = client.post(
        "/api/v1/agent/config-history",
        json={
            "device_id": "e2e-pos-001",
            "action": "update_config",
            "parameter_name": "push_command:APPLY_CONFIG",
            "new_value": {"version": "2.0.0"},
            "success": True,
            "change_reason": "apply config",
            "performance_before": {"status": "degraded", "response_time_ms": 90},
            "performance_after": {"status": "healthy", "response_time_ms": 40},
            "was_rolled_back": False,
        },
        headers=device_headers,
    )
    assert resp.status_code == 200, resp.text

    resp = client.post(
        "/api/v1/agent/config-history",
        json={
            "device_id": "e2e-pos-001",
            "action": "update_config",
            "parameter_name": "push_command:APPLY_CONFIG",
            "new_value": {"version": "2.1.0"},
            "success": True,
            "change_reason": "apply config then rollback",
            "performance_before": {"status": "degraded", "response_time_ms": 90},
            "performance_after": {"status": "online", "response_time_ms": 35},
            "was_rolled_back": True,
            "rollback_reason": "unstable",
            "rollback_success": True,
            "rollback_performance": {"status": "healthy", "response_time_ms": 38},
        },
        headers=device_headers,
    )
    assert resp.status_code == 200, resp.text

    # 5. Export and assert the whole evidence chain.
    resp = client.get(
        EXPORT_URL,
        params={"start": WIDE_START, "end": WIDE_END},
        headers=user_headers,
    )
    assert resp.status_code == 200, resp.text
    bundle = resp.json()

    # MW-01: one completed ping out of one terminal command.
    kpi = _result(bundle, "MW-01", "real")
    assert kpi["value"] == 100.0
    assert kpi["numerator"] == 1
    assert kpi["denominator"] == 1

    # MW-02: executed_at was queued +5s, so round-trip ≈ 5s.
    kpi = _result(
        bundle, "MW-02", "real", **{"command_type": "ping", "statistic": "max"}
    )
    assert kpi["value"] is not None
    assert 4.5 <= kpi["value"] <= 6.5
    assert kpi["numerator"] == 1

    # MW-03: both config changes succeeded.
    kpi = _result(bundle, "MW-03", "real")
    assert kpi["value"] == 100.0
    assert kpi["numerator"] == 2
    assert kpi["denominator"] == 2

    # MW-04: both successful changes carry before/after evidence and improved.
    kpi = _result(bundle, "MW-04", "real")
    assert kpi["value"] == 100.0
    assert kpi["numerator"] == 2
    assert kpi["denominator"] == 2
    assert kpi["exclusions"] == 0

    # MW-05: the one attempted rollback was reported successful.
    kpi = _result(bundle, "MW-05", "real")
    assert kpi["value"] == 100.0
    assert kpi["numerator"] == 1
    assert kpi["denominator"] == 1

    # PF-LAT: 100 and 200 ms → p50 150, p95 195, max 200.
    for stat, expected in (("p50", 150.0), ("p95", 195.0), ("max", 200.0)):
        kpi = _result(bundle, "PF-LAT", "real", **{"statistic": stat})
        assert kpi["value"] == expected
        assert kpi["numerator"] == 2

    # EQ-01: every row written through the API carries a provenance class.
    for table in ("device_metrics", "device_state_history", "configuration_history"):
        kpi = _result(bundle, "EQ-01", **{"table": table})
        assert kpi["value"] == 100.0, f"EQ-01 coverage for {table}"


def test_provenance_classes_stay_separated_via_api(client: TestClient) -> None:
    """Real and simulated devices keep their KPI scopes isolated end-to-end."""
    real_key = _seed_site_device("e2e-real-001", "site-e2e-real", "physical")
    sim_key = _seed_site_device("e2e-sim-001", "site-e2e-sim", "simulation")
    real_headers = _device_headers("e2e-real-001", real_key)
    sim_headers = _device_headers("e2e-sim-001", sim_key)
    user_headers = _user_headers()

    for latency, headers, device_id in (
        (100.0, real_headers, "e2e-real-001"),
        (300.0, sim_headers, "e2e-sim-001"),
    ):
        resp = client.post(
            "/api/v1/analytics/device-metrics",
            json={
                "device_id": device_id,
                "network_latency_ms": latency,
                "collection_interval_seconds": 5,
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text

    def _latency(provenance: str) -> float:
        resp = client.get(
            EXPORT_URL,
            params={"start": WIDE_START, "end": WIDE_END, "provenance": provenance},
            headers=user_headers,
        )
        assert resp.status_code == 200, resp.text
        return _result(resp.json(), "PF-LAT", provenance, **{"statistic": "max"})[
            "value"
        ]

    assert _latency("real") == 100.0
    assert _latency("simulated") == 300.0

    # The unfiltered export reports both provenance classes.
    resp = client.get(
        EXPORT_URL,
        params={"start": WIDE_START, "end": WIDE_END},
        headers=user_headers,
    )
    assert resp.status_code == 200, resp.text
    bundle = resp.json()
    stats = {
        (kpi["provenance"], kpi["group"]["statistic"])
        for kpi in bundle["kpis"]
        if kpi["group"] is not None and "statistic" in kpi["group"]
    }
    assert ("real", "max") in stats
    assert ("simulated", "max") in stats


def test_site_isolation_via_api(client: TestClient) -> None:
    """Exporting one site never leaks evidence from another site."""
    key_a = _seed_site_device("e2e-a-001", "site-e2e-a", "physical")
    key_b = _seed_site_device("e2e-b-001", "site-e2e-b", "physical")
    headers_a = _device_headers("e2e-a-001", key_a)
    headers_b = _device_headers("e2e-b-001", key_b)
    user_headers = _user_headers()

    for latency, headers, device_id in (
        (50.0, headers_a, "e2e-a-001"),
        (900.0, headers_b, "e2e-b-001"),
    ):
        resp = client.post(
            "/api/v1/analytics/device-metrics",
            json={
                "device_id": device_id,
                "network_latency_ms": latency,
                "collection_interval_seconds": 5,
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text

    resp = client.get(
        EXPORT_URL,
        params={
            "start": WIDE_START,
            "end": WIDE_END,
            "site_id": "site-e2e-a",
        },
        headers=user_headers,
    )
    assert resp.status_code == 200, resp.text
    bundle = resp.json()

    kpi = _result(bundle, "PF-LAT", "all", **{"statistic": "max"})
    assert kpi["value"] == 50.0
    assert kpi["numerator"] == 1
