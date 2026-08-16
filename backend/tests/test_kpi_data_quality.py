"""KPI data-quality edge cases and degenerate sample protection.

Protects the KPI formulas against degenerate inputs: all-failed command
windows, in-flight (non-terminal) commands, missing outcome flags, missing
performance evidence, unresolved rollbacks, missing provenance, and null
latency samples. Also guards export reproducibility by pinning the manifest
``git_commit`` to the repository HEAD.
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
from homepot.kpi.manifest import get_git_commit
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
ADMIN_EMAIL = "admin.quality@test.local"


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
                    username="admin_quality",
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
    site_id: str = "site-quality-1",
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
            db.add(
                Device(
                    device_id=device_id,
                    name=f"Device {device_id}",
                    device_type=device_type,
                    site_id=site.id,
                    api_key_hash=hash_password(secrets.token_urlsafe(32)),
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
    provenance: str | None = "real",
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
    provenance: str | None = "real",
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
    provenance: str | None = "real",
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


def test_mw01_all_failed_commands_zero_completion(client: TestClient) -> None:
    """Every terminal command failing still yields a valid 0% completion rate."""
    _seed_device("quality-pos-001")
    for _ in range(3):
        _seed_command("quality-pos-001", status=CommandStatus.FAILED)

    kpi = _result(_export(client), "MW-01")
    assert kpi["value"] == 0.0
    assert kpi["numerator"] == 0
    assert kpi["denominator"] == 3
    assert kpi["exclusions"] == 0


def test_mw01_in_flight_commands_yield_null_value(client: TestClient) -> None:
    """Commands still in flight (non-terminal) are excluded, not counted."""
    _seed_device("quality-pos-002")
    _seed_command("quality-pos-002", status=CommandStatus.PENDING)
    _seed_command("quality-pos-002", status=CommandStatus.SENT)

    kpi = _result(_export(client), "MW-01")
    assert kpi["value"] is None
    assert kpi["denominator"] == 0
    assert kpi["exclusions"] == 2


def test_mw02_two_sample_round_trip_percentiles(client: TestClient) -> None:
    """Round-trip p50/p95/max interpolate correctly on a two-sample window."""
    _seed_device("quality-pos-003")
    now = datetime.now(timezone.utc)
    _seed_command(
        "quality-pos-003",
        created_at=now,
        executed_at=now + timedelta(seconds=1),
    )
    _seed_command(
        "quality-pos-003",
        created_at=now,
        executed_at=now + timedelta(seconds=3),
    )

    bundle = _export(client)
    group = {"command_type": "ping", "statistic": "p50"}
    assert _result(bundle, "MW-02", **group)["value"] == 2.0
    group["statistic"] = "p95"
    assert _result(bundle, "MW-02", **group)["value"] == 2.9
    group["statistic"] = "max"
    assert _result(bundle, "MW-02", **group)["value"] == 3.0


def test_mw02_single_sample_all_stats_equal(client: TestClient) -> None:
    """A single observed round-trip makes p50, p95 and max identical."""
    _seed_device("quality-pos-004")
    now = datetime.now(timezone.utc)
    _seed_command(
        "quality-pos-004",
        created_at=now,
        executed_at=now + timedelta(seconds=2.5),
    )

    bundle = _export(client)
    for stat in ("p50", "p95", "max"):
        kpi = _result(bundle, "MW-02", **{"command_type": "ping", "statistic": stat})
        assert kpi["value"] == 2.5
        assert kpi["numerator"] == 1
        assert kpi["denominator"] == 1


def test_mw03_missing_outcome_yields_null_value(client: TestClient) -> None:
    """Configuration changes without an outcome flag are excluded, not counted."""
    _seed_device("quality-pos-005")
    _seed_config("quality-pos-005", was_successful=None)
    _seed_config("quality-pos-005", was_successful=None)

    kpi = _result(_export(client), "MW-03")
    assert kpi["value"] is None
    assert kpi["denominator"] == 0
    assert kpi["exclusions"] == 2


def test_mw04_success_without_evidence_not_verified(client: TestClient) -> None:
    """Successful changes without before/after windows cannot be verified."""
    _seed_device("quality-pos-006")
    _seed_config("quality-pos-006", was_successful=True, before=None, after=None)

    kpi = _result(_export(client), "MW-04")
    assert kpi["value"] is None
    assert kpi["denominator"] == 0
    assert kpi["exclusions"] == 1


def test_mw05_mixed_rollback_outcomes_restored(client: TestClient) -> None:
    """Rollbacks restoring the health target count regardless of flag source."""
    _seed_device("quality-pos-007")
    _seed_config(
        "quality-pos-007",
        rolled_back=True,
        rollback_success=True,
        before={"status": "degraded"},
        after={"status": "online"},
    )
    _seed_config(
        "quality-pos-007",
        rolled_back=True,
        rollback_success=None,
        rollback_performance={"status": "healthy"},
        before={"status": "degraded"},
        after={"status": "degraded"},
    )

    kpi = _result(_export(client), "MW-05")
    assert kpi["value"] == 100.0
    assert kpi["numerator"] == 2
    assert kpi["denominator"] == 2


def test_mw05_failed_rollback_excluded(client: TestClient) -> None:
    """A rollback explicitly reported as failed counts as not restored."""
    _seed_device("quality-pos-008")
    _seed_config(
        "quality-pos-008",
        rolled_back=True,
        rollback_success=False,
        before={"status": "degraded"},
        after={"status": "degraded"},
    )

    kpi = _result(_export(client), "MW-05")
    assert kpi["value"] == 0.0
    assert kpi["numerator"] == 0
    assert kpi["denominator"] == 1


def test_eq01_missing_provenance_zero_coverage(client: TestClient) -> None:
    """Rows with no provenance class yield 0% coverage on every table."""
    _seed_device("quality-pos-009")
    _seed_metric("quality-pos-009", 100.0, provenance=None)
    _seed_state("quality-pos-009", provenance=None)
    _seed_config("quality-pos-009", provenance=None)

    bundle = _export(client)
    for table in ("device_metrics", "device_state_history", "configuration_history"):
        kpi = _result(bundle, "EQ-01", **{"table": table})
        assert kpi["value"] == 0.0
        assert kpi["numerator"] == 0
        assert kpi["denominator"] == 1


def test_eq01_valid_provenance_full_coverage(client: TestClient) -> None:
    """Every row carrying a provenance class yields 100% coverage per table."""
    _seed_device("quality-pos-010")
    _seed_metric("quality-pos-010", 100.0, provenance="real")
    _seed_state("quality-pos-010", provenance="real")
    _seed_config("quality-pos-010", provenance="real")

    bundle = _export(client)
    for table in ("device_metrics", "device_state_history", "configuration_history"):
        kpi = _result(bundle, "EQ-01", **{"table": table})
        assert kpi["value"] == 100.0
        assert kpi["numerator"] == 1
        assert kpi["denominator"] == 1


def test_pf_lat_null_latency_rows_ignored(client: TestClient) -> None:
    """Rows without network_latency_ms are excluded from every PF-LAT stat."""
    _seed_device("quality-pos-011")
    _seed_metric("quality-pos-011", 100.0, provenance="real")
    _seed_metric("quality-pos-011", 200.0, provenance="real")
    _seed_metric("quality-pos-011", None, provenance="real")

    bundle = _export(client)
    for stat, expected in (("p50", 150.0), ("p95", 195.0), ("max", 200.0)):
        kpi = _result(bundle, "PF-LAT", **{"statistic": stat})
        assert kpi["value"] == expected
        assert kpi["numerator"] == 2
        assert kpi["denominator"] == 2


def test_manifest_git_commit_tracks_repo_head(client: TestClient) -> None:
    """Exported manifests pin the exact repository commit for reproducibility."""
    bundle = _export(client)
    assert bundle["manifest"]["git_commit"] == get_git_commit()
    assert bundle["manifest"]["git_commit"] not in (None, "unknown", "")
