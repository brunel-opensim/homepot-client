"""Tests for evidence provenance and collection metadata preservation.

The KPI evaluation roadmap requires every telemetry and event row to carry
an immutable provenance class (real/controlled/simulated) so historical rows
never silently inherit a device's current classification, plus collection
metadata (the configured collection interval) for telemetry completeness
KPIs.
"""

import asyncio
import os
import tempfile

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from homepot.app.auth_utils import create_access_token, hash_password
from homepot.app.models.AnalyticsModel import (
    DeviceMetrics,
    DeviceStateHistory,
    ErrorLog,
    JobOutcome,
)
from homepot.config import reload_settings
import homepot.database
from homepot.models import Base, Device, LifecycleState, Provenance, Site


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


def _create_site(site_code: str = "site-prov-1") -> Site:
    """Create and return a site row for provenance tests."""
    db = homepot.database.SessionLocal()
    try:
        site = Site(site_id=site_code, name="Provenance Test Site", location="Lab")
        db.add(site)
        db.commit()
        db.refresh(site)
        return site
    finally:
        db.close()


def _create_device(
    device_id: str,
    site_pk: int,
    api_key: str = "test-api-key",
    is_simulated: bool = False,
    device_source: str | None = None,
) -> str:
    """Create a device row and return the plain-text API key."""
    db = homepot.database.SessionLocal()
    try:
        device = Device(
            device_id=device_id,
            name="Provenance Device",
            device_type="pos_terminal",
            site_id=site_pk,
            api_key_hash=hash_password(api_key),
            is_active=True,
            is_simulated=is_simulated,
            config={"device_source": device_source} if device_source else None,
            lifecycle_state=LifecycleState.ACTIVE.value,
        )
        db.add(device)
        db.commit()
        db.refresh(device)
        return api_key
    finally:
        db.close()


def _device_headers(device_id: str, api_key: str) -> dict[str, str]:
    """Headers used for device-authenticated endpoints."""
    return {"X-Device-ID": device_id, "X-API-Key": api_key}


def _auth_header(email: str = "provenance-test@example.com") -> dict[str, str]:
    """Headers used for user-authenticated endpoints."""
    token = create_access_token({"sub": email})
    return {"Authorization": f"Bearer {token}"}


def _latest_metric(device_pk: int) -> DeviceMetrics | None:
    """Return the most recent metrics row for a device primary key."""
    db = homepot.database.SessionLocal()
    try:
        return (
            db.query(DeviceMetrics)
            .filter(DeviceMetrics.device_id == device_pk)
            .order_by(DeviceMetrics.id.desc())
            .first()
        )
    finally:
        db.close()


class TestMetricsProvenance:
    """Device metrics rows snapshot the device provenance class."""

    def test_real_device_metrics_carry_real_provenance(
        self, client: TestClient
    ) -> None:
        """Metrics from a physical device are classified REAL."""
        site = _create_site()
        api_key = _create_device("real-pos-001", int(site.id), device_source="physical")
        device_pk = _device_pk("real-pos-001")

        resp = client.post(
            "/api/v1/analytics/device-metrics",
            json={
                "device_id": "real-pos-001",
                "cpu_percent": 12.0,
                "memory_percent": 51.0,
                "collection_interval_seconds": 5,
            },
            headers=_device_headers("real-pos-001", api_key),
        )
        assert resp.status_code == 201, resp.text

        row = _latest_metric(device_pk)
        assert row is not None
        assert row.provenance == Provenance.REAL.value
        assert row.collection_interval_seconds == 5

    def test_seeded_device_metrics_carry_simulated_provenance(
        self, client: TestClient
    ) -> None:
        """Metrics from a device marked is_simulated are classified SIMULATED."""
        site = _create_site()
        api_key = _create_device("sim-pos-001", int(site.id), is_simulated=True)
        device_pk = _device_pk("sim-pos-001")

        resp = client.post(
            "/api/v1/analytics/device-metrics",
            json={
                "device_id": "sim-pos-001",
                "cpu_percent": 20.0,
                "memory_percent": 60.0,
            },
            headers=_device_headers("sim-pos-001", api_key),
        )
        assert resp.status_code == 201, resp.text

        row = _latest_metric(device_pk)
        assert row is not None
        assert row.provenance == Provenance.SIMULATED.value

    def test_emulator_device_metrics_carry_controlled_provenance(
        self, client: TestClient
    ) -> None:
        """Metrics from a deterministic emulator are classified CONTROLLED."""
        site = _create_site()
        api_key = _create_device("emul-pos-001", int(site.id), device_source="emulator")
        device_pk = _device_pk("emul-pos-001")

        resp = client.post(
            "/api/v1/analytics/device-metrics",
            json={
                "device_id": "emul-pos-001",
                "cpu_percent": 30.0,
                "memory_percent": 70.0,
            },
            headers=_device_headers("emul-pos-001", api_key),
        )
        assert resp.status_code == 201, resp.text

        row = _latest_metric(device_pk)
        assert row is not None
        assert row.provenance == Provenance.CONTROLLED.value

    def test_provenance_is_immutable_after_classification_change(
        self, client: TestClient
    ) -> None:
        """Historical rows keep their provenance when the device changes."""
        site = _create_site()
        api_key = _create_device(
            "mutable-pos-001", int(site.id), device_source="physical"
        )
        device_pk = _device_pk("mutable-pos-001")

        resp = client.post(
            "/api/v1/analytics/device-metrics",
            json={"device_id": "mutable-pos-001", "cpu_percent": 15.0},
            headers=_device_headers("mutable-pos-001", api_key),
        )
        assert resp.status_code == 201, resp.text

        # Re-classify the device as simulated after the row was written.
        db = homepot.database.SessionLocal()
        try:
            device = db.get(Device, device_pk)
            assert device is not None
            device.is_simulated = True
            device.config = {"device_source": "simulation"}
            db.commit()
        finally:
            db.close()

        row = _latest_metric(device_pk)
        assert row is not None
        # The historical row must not silently inherit the new classification.
        assert row.provenance == Provenance.REAL.value


class TestEventProvenance:
    """State, job, and error event rows snapshot the device provenance class."""

    def test_state_change_carries_provenance(self, client: TestClient) -> None:
        """State-change rows snapshot the device provenance."""
        site = _create_site()
        _create_device("state-pos-001", int(site.id), device_source="physical")

        resp = client.post(
            "/api/v1/analytics/device-state-change",
            json={
                "device_id": "state-pos-001",
                "previous_state": "online",
                "new_state": "offline",
                "reason": "Network timeout",
            },
            headers=_auth_header(),
        )
        assert resp.status_code == 201, resp.text

        db = homepot.database.SessionLocal()
        try:
            row = (
                db.query(DeviceStateHistory)
                .order_by(DeviceStateHistory.id.desc())
                .first()
            )
            assert row is not None
            assert row.provenance == Provenance.REAL.value
        finally:
            db.close()

    def test_job_outcome_carries_provenance(self, client: TestClient) -> None:
        """Job-outcome rows snapshot the device provenance."""
        site = _create_site()
        _create_device("job-pos-001", int(site.id), is_simulated=True)

        resp = client.post(
            "/api/v1/analytics/job-outcome",
            json={
                "job_id": "job-456",
                "job_type": "restart",
                "device_id": "job-pos-001",
                "status": "success",
                "duration_ms": 5000,
            },
            headers=_auth_header(),
        )
        assert resp.status_code == 201, resp.text

        db = homepot.database.SessionLocal()
        try:
            row = db.query(JobOutcome).order_by(JobOutcome.id.desc()).first()
            assert row is not None
            assert row.provenance == Provenance.SIMULATED.value
        finally:
            db.close()

    def test_error_log_carries_provenance(self, client: TestClient) -> None:
        """Error rows snapshot the device provenance."""
        site = _create_site()
        _create_device("err-pos-001", int(site.id), device_source="emulator")

        resp = client.post(
            "/api/v1/analytics/error",
            json={
                "category": "device",
                "severity": "error",
                "error_message": "Device unreachable",
                "device_id": "err-pos-001",
            },
            headers=_auth_header(),
        )
        assert resp.status_code == 201, resp.text

        db = homepot.database.SessionLocal()
        try:
            row = db.query(ErrorLog).order_by(ErrorLog.id.desc()).first()
            assert row is not None
            assert row.provenance == Provenance.CONTROLLED.value
        finally:
            db.close()


class TestAgentTelemetryProvenance:
    """Agent telemetry rows snapshot provenance and collection metadata."""

    def test_agent_telemetry_carries_provenance(self, client: TestClient) -> None:
        """Agent telemetry persists provenance and the collection interval."""
        site = _create_site()
        api_key = _create_device(
            "agent-pos-001", int(site.id), device_source="physical"
        )
        device_pk = _device_pk("agent-pos-001")

        resp = client.post(
            "/api/v1/agent/telemetry",
            json={
                "device_id": "agent-pos-001",
                "cpu_usage": 21.0,
                "memory_usage": 56.0,
                "disk_usage": 45.0,
                "collection_interval_seconds": 5,
            },
            headers=_device_headers("agent-pos-001", api_key),
        )
        assert resp.status_code == 200, resp.text

        row = _latest_metric(device_pk)
        assert row is not None
        assert row.provenance == Provenance.REAL.value
        assert row.collection_interval_seconds == 5

    def test_agent_telemetry_bulk_carries_provenance(self, client: TestClient) -> None:
        """Bulk agent telemetry persists provenance on every row."""
        site = _create_site()
        api_key = _create_device(
            "agent-bulk-001", int(site.id), device_source="emulator"
        )
        device_pk = _device_pk("agent-bulk-001")

        resp = client.post(
            "/api/v1/agent/telemetry",
            json=[
                {
                    "device_id": "agent-bulk-001",
                    "cpu_usage": 21.0,
                    "memory_usage": 56.0,
                    "disk_usage": 45.0,
                },
                {
                    "device_id": "agent-bulk-001",
                    "cpu_usage": 22.0,
                    "memory_usage": 57.0,
                    "disk_usage": 46.0,
                },
            ],
            headers=_device_headers("agent-bulk-001", api_key),
        )
        assert resp.status_code == 200, resp.text

        db = homepot.database.SessionLocal()
        try:
            rows = (
                db.query(DeviceMetrics)
                .filter(DeviceMetrics.device_id == device_pk)
                .all()
            )
            assert len(rows) == 2
            assert all(row.provenance == Provenance.CONTROLLED.value for row in rows)
        finally:
            db.close()


def _device_pk(device_id: str) -> int:
    """Resolve the integer primary key for a device_id string."""
    db = homepot.database.SessionLocal()
    try:
        result = db.execute(select(Device).where(Device.device_id == device_id))
        device = result.scalar_one()
        return int(device.id)
    finally:
        db.close()
