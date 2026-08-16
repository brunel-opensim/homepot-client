"""Tests for the UK demonstrator KPI calculations and export.

Covers the Phase 2 export contract: window/device/provenance filters,
numerator/denominator/exclusions/sample counts, p50/p95/max percentiles,
manifest metadata, empty windows, boundary timestamps, mixed provenance,
site/device isolation, and validation errors.
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
from homepot.app.models.AnalyticsModel import (
    ConfigurationHistory,
    DeviceMetrics,
    DeviceStateHistory,
)
from homepot.config import reload_settings
import homepot.database
from homepot.kpi.calculator import percentile
from homepot.models import (
    Base,
    CommandStatus,
    Device,
    DeviceCommand,
    LifecycleState,
    Site,
    User,
)

EXPORT_URL = "/api/v1/kpi/export"
ADMIN_EMAIL = "admin.kpi@test.local"


@pytest.fixture(autouse=True)
def mock_db_url(monkeypatch):
    """Use a temporary database for these tests."""
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

    yield

    new_engine.dispose()
    if os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


def _seed_admin() -> None:
    db = homepot.database.SessionLocal()
    try:
        if not db.query(User).filter(User.email == ADMIN_EMAIL).first():
            db.add(
                User(
                    email=ADMIN_EMAIL,
                    username="admin_kpi",
                    hashed_password=hash_password("pass"),
                    is_admin=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            db.commit()
    finally:
        db.close()


def _seed_device(
    device_id: str,
    site_id: str,
    device_type: str = "pos_terminal",
    config: dict | None = None,
) -> None:
    db = homepot.database.SessionLocal()
    try:
        site = db.query(Site).filter(Site.site_id == site_id).first()
        if not site:
            site = Site(site_id=site_id, name=f"Site {site_id}")
            db.add(site)
            db.commit()
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if not device:
            api_key = secrets.token_urlsafe(32)
            db.add(
                Device(
                    device_id=device_id,
                    name=f"Device {device_id}",
                    device_type=device_type,
                    site_id=site.id,
                    api_key_hash=hash_password(api_key),
                    is_active=True,
                    lifecycle_state=LifecycleState.ACTIVE.value,
                    config=config or {},
                )
            )
            db.commit()
    finally:
        db.close()


def _seed_command(
    device_id: str,
    command_type: str = "ping",
    status: CommandStatus = CommandStatus.COMPLETED,
    created_at: datetime | None = None,
    executed_at: datetime | None = None,
) -> None:
    db = homepot.database.SessionLocal()
    try:
        device = db.query(Device).filter(Device.device_id == device_id).first()
        db.add(
            DeviceCommand(
                command_id=f"cmd-{secrets.token_hex(4)}",
                device_id=device.id,
                command_type=command_type,
                status=status,
                created_at=created_at or datetime.now(timezone.utc),
                executed_at=executed_at,
            )
        )
        db.commit()
    finally:
        db.close()


def _seed_config(
    device_id: str,
    was_successful: bool | None = True,
    before: dict | None = None,
    after: dict | None = None,
    rolled_back: bool = False,
    rollback_success: bool | None = None,
    rollback_performance: dict | None = None,
    provenance: str = "real",
    timestamp: datetime | None = None,
) -> None:
    db = homepot.database.SessionLocal()
    try:
        db.add(
            ConfigurationHistory(
                timestamp=timestamp or datetime.now(timezone.utc),
                entity_type="device",
                entity_id=device_id,
                parameter_name="push_command:APPLY_CONFIG",
                new_value={"version": "2.0.0"},
                changed_by="agent",
                change_reason="test",
                change_type="automated",
                was_successful=was_successful,
                performance_before=before,
                performance_after=after,
                was_rolled_back=rolled_back,
                rollback_success=rollback_success,
                rollback_performance=rollback_performance,
                provenance=provenance,
            )
        )
        db.commit()
    finally:
        db.close()


def _seed_metric(
    device_id: str,
    latency_ms: float | None,
    provenance: str,
    timestamp: datetime | None = None,
) -> None:
    db = homepot.database.SessionLocal()
    try:
        device = db.query(Device).filter(Device.device_id == device_id).first()
        db.add(
            DeviceMetrics(
                timestamp=timestamp or datetime.now(timezone.utc),
                device_id=device.id,
                network_latency_ms=latency_ms,
                provenance=provenance,
            )
        )
        db.commit()
    finally:
        db.close()


def _seed_state(
    device_id: str,
    provenance: str,
    new_state: str = "online",
    timestamp: datetime | None = None,
) -> None:
    db = homepot.database.SessionLocal()
    try:
        device = db.query(Device).filter(Device.device_id == device_id).first()
        db.add(
            DeviceStateHistory(
                timestamp=timestamp or datetime.now(timezone.utc),
                device_id=device.id,
                new_state=new_state,
                provenance=provenance,
            )
        )
        db.commit()
    finally:
        db.close()


def _auth_headers() -> dict:
    _seed_admin()
    token = create_access_token({"sub": ADMIN_EMAIL})
    return {"Authorization": f"Bearer {token}"}


def _export(client: TestClient, **params) -> dict:
    params.setdefault("start", "2026-01-01T00:00:00Z")
    params.setdefault("end", "2026-12-31T23:59:59Z")
    resp = client.get(EXPORT_URL, params=params, headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    return resp.json()


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


def test_export_requires_auth(client: TestClient) -> None:
    """KPI export requires a logged-in user."""
    resp = client.get(
        EXPORT_URL,
        params={"start": "2026-01-01T00:00:00Z", "end": "2026-12-31T23:59:59Z"},
    )
    assert resp.status_code == 401


def test_export_validation_errors(client: TestClient) -> None:
    """Invalid provenance, format, and window are rejected."""
    headers = _auth_headers()
    base = {"start": "2026-01-01T00:00:00Z", "end": "2026-12-31T23:59:59Z"}

    resp = client.get(
        EXPORT_URL, params={**base, "provenance": "nonsense"}, headers=headers
    )
    assert resp.status_code == 422

    resp = client.get(EXPORT_URL, params={**base, "format": "xml"}, headers=headers)
    assert resp.status_code == 422

    resp = client.get(
        EXPORT_URL,
        params={"start": "2026-12-31T00:00:00Z", "end": "2026-01-01T00:00:00Z"},
        headers=headers,
    )
    assert resp.status_code == 400


def test_export_empty_window(client: TestClient) -> None:
    """An empty window yields null values and zero sample counts."""
    bundle = _export(client, start="2030-01-01T00:00:00Z", end="2030-01-02T00:00:00Z")

    assert all(t["rows"] == [] for t in bundle["raw"])
    assert len(bundle["raw"]) == 4
    mw01 = _result(bundle, "MW-01")
    assert mw01["value"] is None
    assert mw01["denominator"] == 0
    assert mw01["sample_count"] == 0
    # All four provenance scopes are reported separately
    assert [k["provenance"] for k in bundle["kpis"] if k["kpi_id"] == "MW-01"] == [
        "all",
        "real",
        "controlled",
        "simulated",
    ]


def test_manifest_metadata(client: TestClient) -> None:
    """The manifest carries run ID, version, commit, timezone, and window metadata."""
    bundle = _export(client)

    manifest = bundle["manifest"]
    assert manifest["run_id"]
    assert manifest["timezone"] == "UTC"
    assert manifest["calculation_version"]
    assert manifest["generated_at"]
    assert manifest["git_commit"]
    assert manifest["filters"]["start"] == "2026-01-01T00:00:00+00:00"
    assert set(manifest["units"].keys()) >= {"MW-01", "MW-02", "EQ-01", "PF-LAT"}


def test_command_kpis_arithmetic(client: TestClient) -> None:
    """MW-01 and MW-02 compute from terminal commands with known timestamps."""
    _seed_device("kpi-cmd-dev", "site-a", config={"device_source": "physical"})
    t0 = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    # completed at +100s and +200s
    _seed_command(
        "kpi-cmd-dev", "ping", CommandStatus.COMPLETED, t0, t0 + timedelta(seconds=100)
    )
    _seed_command(
        "kpi-cmd-dev", "ping", CommandStatus.COMPLETED, t0, t0 + timedelta(seconds=200)
    )
    # one failed at +300s, one still pending
    _seed_command(
        "kpi-cmd-dev", "restart", CommandStatus.FAILED, t0, t0 + timedelta(seconds=300)
    )
    _seed_command("kpi-cmd-dev", "ping", CommandStatus.PENDING, t0)

    bundle = _export(client)

    mw01 = _result(bundle, "MW-01", "real")
    assert mw01["numerator"] == 2
    assert mw01["denominator"] == 3
    assert mw01["exclusions"] == 1
    assert mw01["value"] == pytest.approx(66.67, abs=0.01)

    mw02_ping_p50 = _result(
        bundle, "MW-02", "real", command_type="ping", statistic="p50"
    )
    mw02_ping_p95 = _result(
        bundle, "MW-02", "real", command_type="ping", statistic="p95"
    )
    mw02_ping_max = _result(
        bundle, "MW-02", "real", command_type="ping", statistic="max"
    )
    assert mw02_ping_p50["value"] == pytest.approx(150.0, abs=0.001)
    assert mw02_ping_p95["value"] == pytest.approx(195.0, abs=0.001)
    assert mw02_ping_max["value"] == pytest.approx(200.0, abs=0.001)

    mw02_restart = _result(
        bundle, "MW-02", "real", command_type="restart", statistic="max"
    )
    assert mw02_restart["value"] == pytest.approx(300.0, abs=0.001)


def test_config_kpis_arithmetic(client: TestClient) -> None:
    """MW-03, MW-04, and MW-05 compute from configuration history."""
    _seed_device("kpi-cfg-dev", "site-a", config={"device_source": "physical"})
    healthy = {"status": "healthy", "response_time_ms": 40}
    degraded = {"status": "degraded", "response_time_ms": 210}

    # MW-03: 2 successful + 1 failed, 1 without outcome (excluded)
    _seed_config("kpi-cfg-dev", True, before=degraded, after=healthy)
    _seed_config("kpi-cfg-dev", True, before=healthy, after=degraded)
    _seed_config("kpi-cfg-dev", False)
    _seed_config("kpi-cfg-dev", None)
    # MW-05: one successful rollback, one failed rollback
    _seed_config(
        "kpi-cfg-dev",
        False,
        before=healthy,
        after=degraded,
        rolled_back=True,
        rollback_success=True,
        rollback_performance=healthy,
    )
    _seed_config(
        "kpi-cfg-dev",
        False,
        before=healthy,
        after=degraded,
        rolled_back=True,
        rollback_success=False,
    )

    bundle = _export(client)

    mw03 = _result(bundle, "MW-03", "real")
    assert mw03["numerator"] == 2
    assert mw03["denominator"] == 5
    assert mw03["exclusions"] == 1
    assert mw03["value"] == pytest.approx(40.0)

    mw04 = _result(bundle, "MW-04", "real")
    # successful with before+after: first two configs; improved = 1
    assert mw04["numerator"] == 1
    assert mw04["denominator"] == 2
    assert mw04["value"] == pytest.approx(50.0)

    mw05 = _result(bundle, "MW-05", "real")
    assert mw05["denominator"] == 2
    assert mw05["numerator"] == 1
    assert mw05["value"] == pytest.approx(50.0)


def test_provenance_separation(client: TestClient) -> None:
    """Metrics are reported per provenance scope and filtered by provenance."""
    _seed_device("kpi-mix-a", "site-a", config={"device_source": "physical"})
    _seed_device("kpi-mix-b", "site-a", config={"device_source": "simulation"})
    _seed_metric("kpi-mix-a", 100.0, "real")
    _seed_metric("kpi-mix-a", 200.0, "real")
    _seed_metric("kpi-mix-b", 500.0, "simulated")

    bundle = _export(client)

    real_p50 = _result(bundle, "PF-LAT", "real", statistic="p50")
    assert real_p50["sample_count"] == 2
    assert real_p50["value"] == pytest.approx(150.0)

    sim_p50 = _result(bundle, "PF-LAT", "simulated", statistic="p50")
    assert sim_p50["sample_count"] == 1
    assert sim_p50["value"] == pytest.approx(500.0)

    filtered = _export(client, provenance="real")
    filtered_p50 = _result(filtered, "PF-LAT", "real", statistic="p50")
    assert filtered_p50["sample_count"] == 2


def test_site_device_isolation(client: TestClient) -> None:
    """Site and device filters isolate the KPI population."""
    _seed_device("kpi-site-a-dev", "site-a", config={"device_source": "physical"})
    _seed_device("kpi-site-b-dev", "site-b", config={"device_source": "physical"})
    _seed_command("kpi-site-a-dev", "ping", CommandStatus.COMPLETED)
    _seed_command("kpi-site-b-dev", "ping", CommandStatus.FAILED)

    whole = _export(client)
    assert _result(whole, "MW-01", "real")["denominator"] == 2

    site_a = _export(client, site_id="site-a")
    assert _result(site_a, "MW-01", "real")["denominator"] == 1
    assert _result(site_a, "MW-01", "real")["numerator"] == 1

    device_b = _export(client, device_id="kpi-site-b-dev")
    assert _result(device_b, "MW-01", "real")["numerator"] == 0


def test_boundary_timestamps(client: TestClient) -> None:
    """Rows exactly at start/end are included; outside the window are not."""
    _seed_device("kpi-boundary", "site-a", config={"device_source": "physical"})
    start = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 6, 2, 0, 0, 0, tzinfo=timezone.utc)
    _seed_command("kpi-boundary", "ping", CommandStatus.COMPLETED, start, start)
    _seed_command("kpi-boundary", "ping", CommandStatus.COMPLETED, end, end)
    _seed_command(
        "kpi-boundary",
        "ping",
        CommandStatus.FAILED,
        datetime(2026, 5, 31, 23, 59, 59, tzinfo=timezone.utc),
    )

    bundle = _export(client, start="2026-06-01T00:00:00Z", end="2026-06-02T00:00:00Z")
    assert _result(bundle, "MW-01", "real")["denominator"] == 2


def test_provenance_coverage(client: TestClient) -> None:
    """EQ-01 reports per-table provenance coverage."""
    _seed_device("kpi-cov-dev", "site-a", config={"device_source": "physical"})
    _seed_metric("kpi-cov-dev", 50.0, "real")
    _seed_metric("kpi-cov-dev", 60.0, None)  # no provenance
    _seed_state("kpi-cov-dev", "real")

    bundle = _export(client)
    metrics = _result(bundle, "EQ-01", "all", table="device_metrics")
    assert metrics["numerator"] == 1
    assert metrics["denominator"] == 2
    assert metrics["value"] == pytest.approx(50.0)

    state = _result(bundle, "EQ-01", "all", table="device_state_history")
    assert state["value"] == pytest.approx(100.0)


def test_raw_rows_exported(client: TestClient) -> None:
    """Raw evidence rows are included in the JSON bundle."""
    _seed_device("kpi-raw-dev", "site-a", config={"device_source": "physical"})
    _seed_command("kpi-raw-dev", "ping", CommandStatus.COMPLETED)

    bundle = _export(client)
    tables = {t["table"]: t for t in bundle["raw"]}
    assert set(tables.keys()) == {
        "device_metrics",
        "device_state_history",
        "configuration_history",
        "device_commands",
    }
    assert len(tables["device_commands"]["rows"]) == 1
    assert tables["device_commands"]["columns"][-1] == "provenance"


def test_csv_summary(client: TestClient) -> None:
    """CSV format returns a self-describing KPI summary table."""
    _seed_device("kpi-csv-dev", "site-a", config={"device_source": "physical"})
    _seed_command("kpi-csv-dev", "ping", CommandStatus.COMPLETED)

    resp = client.get(
        EXPORT_URL,
        params={
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-12-31T23:59:59Z",
            "format": "csv",
        },
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    text = resp.text
    assert text.startswith("# manifest:")
    assert "kpi_id,name,formula,unit,value" in text
    assert "MW-01" in text


def test_percentile_helper() -> None:
    """The percentile helper matches expected p50/p95/max for a known sample."""
    assert percentile([], 0.5) is None
    assert percentile([7], 0.95) == 7
    values = [100.0, 200.0, 300.0, 400.0]
    assert percentile(values, 0.5) == pytest.approx(250.0)
    assert percentile(values, 0.95) == pytest.approx(385.0)
    assert percentile(values, 1.0) == pytest.approx(400.0)
