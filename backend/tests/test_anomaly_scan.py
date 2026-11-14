"""Tests for multi-level anomaly detection (anomaly_scan service)."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from homepot.app.ai_ops.anomaly_scan import (
    _count_consecutive_failures,
    _count_flapping,
    classify_anomaly_level,
)


def _check(ts: int, healthy: bool) -> SimpleNamespace:
    """Build a fake health-check row with a numeric sortable timestamp."""
    return SimpleNamespace(timestamp=ts, is_healthy=healthy)


@pytest.fixture
def isolated_db(tmp_path):
    """Provide a fresh, function-scoped SQLite database isolated from others.

    The shared ``temp_db`` fixture reads the global settings URL, which other
    tests mutate via ``reload_settings()``; use an explicit temp-file engine so
    this test never sees rows left behind by unrelated suites.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from homepot.models import Base

    engine = create_engine(
        f"sqlite:///{tmp_path / 'anomaly.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    yield factory
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


# ---------------------------------------------------------------------------
# Level classification
# ---------------------------------------------------------------------------


def test_classify_level_zero_when_no_score():
    """A zero score is Level 0 regardless of breach history."""
    assert classify_anomaly_level(0.0) == 0
    assert classify_anomaly_level(0.0, breach_count=10) == 0


def test_classify_level_three_on_critical_score():
    """A score at/above 0.8 is always Level 3 (critical)."""
    assert classify_anomaly_level(0.8) == 3
    assert classify_anomaly_level(0.95) == 3


def test_classify_level_two_on_consecutive_failures():
    """Consecutive health-check failures promote to Level 2."""
    assert (
        classify_anomaly_level(
            0.3, consecutive_failures=3.0, consecutive_failure_threshold=3.0
        )
        == 2
    )


def test_classify_level_two_on_flapping():
    """Flapping above the threshold promotes to Level 2."""
    assert classify_anomaly_level(0.3, flapping_count=6.0, flapping_threshold=5.0) == 2


def test_classify_level_two_on_persistent_breaches():
    """Repeated breaches within the window promote to Level 2."""
    assert classify_anomaly_level(0.2, breach_count=3, persistent_breach_count=3) == 2
    assert classify_anomaly_level(0.2, breach_count=2, persistent_breach_count=3) == 1


def test_classify_level_one_for_single_low_breach():
    """A single low-impact breach is Level 1 (transient)."""
    assert classify_anomaly_level(0.2) == 1


# ---------------------------------------------------------------------------
# Flapping and consecutive-failure windowing (the flapping-window fix)
# ---------------------------------------------------------------------------


def test_flapping_counts_transitions_beyond_five_checks():
    """Ten alternating checks yield 9 transitions, exceeding the old window."""
    checks = [_check(i, bool(i % 2 == 0)) for i in range(10)]
    assert _count_flapping(checks) == 9


def test_flapping_ignores_steady_checks():
    """Steady-health checks produce no transitions."""
    checks = [_check(i, True) for i in range(8)]
    assert _count_flapping(checks) == 0


def test_consecutive_failures_counts_from_newest():
    """Consecutive failures are counted from the newest check backwards."""
    checks = [
        _check(5, False),
        _check(4, False),
        _check(3, False),
        _check(2, True),
        _check(1, True),
    ]
    assert _count_consecutive_failures(checks) == 3


def test_consecutive_failures_stops_at_first_healthy():
    """Counting stops at the first healthy check."""
    checks = [_check(3, False), _check(2, True), _check(1, False)]
    assert _count_consecutive_failures(checks) == 1


# ---------------------------------------------------------------------------
# Persistence round-trip
# ---------------------------------------------------------------------------


class _FakeAsyncSession:
    """Wrap a sync SQLAlchemy session with async methods the service expects."""

    def __init__(self, sync_session):
        self._s = sync_session

    async def execute(self, stmt):
        return self._s.execute(stmt)

    def add(self, obj):
        self._s.add(obj)

    async def commit(self):
        self._s.commit()


class _FakeDB:
    """Wrap a sync session as a minimal DatabaseService stand-in."""

    def __init__(self, sync_session):
        self._s = sync_session

    def get_session(self):
        @asynccontextmanager
        async def _cm():
            yield _FakeAsyncSession(self._s)

        return _cm()


def test_scan_and_persist_round_trip(monkeypatch, isolated_db):
    """scan_and_persist writes rows and promotes a device to Level 2."""
    from homepot.app.ai_ops import anomaly_scan
    from homepot.app.models.AnalyticsModel import AnomalyScan, DeviceMetrics
    from homepot.models import Device, LifecycleState

    get_db = isolated_db
    sync_db = get_db()
    try:
        device = Device(
            device_id="DEV-TEST",
            name="Test Device",
            device_type="pos_terminal",
            site_id=1,
            is_active=True,
            lifecycle_state=LifecycleState.ACTIVE.value,
            status="online",
        )
        sync_db.add(device)
        sync_db.commit()
        sync_db.refresh(device)
        sync_db.add(
            DeviceMetrics(
                device_id=device.id,
                cpu_percent=95.0,
                memory_percent=10.0,
                disk_percent=10.0,
                network_latency_ms=10.0,
                error_rate=0.0,
            )
        )
        sync_db.commit()

        class _FakeDetector:
            """Deterministic detector: one low-impact breach (score 0.2)."""

            thresholds = {"consecutive_failures": 3, "flapping_count": 5}

            def check_anomaly(self, metrics):
                return 0.2, ["High CPU: 95.0%"]

        monkeypatch.setattr(
            "ai.anomaly_detection.AnomalyDetector", lambda: _FakeDetector()
        )
        monkeypatch.setattr(
            "ai.config.load_ai_config", lambda: {"anomaly_detection": {}}
        )
        monkeypatch.setattr(anomaly_scan, "compute_connectivity", lambda d: "online")

        db = _FakeDB(sync_db)
        summaries = asyncio.run(anomaly_scan.scan_and_persist(db))
        assert len(summaries) == 1
        assert summaries[0]["device_id"] == "DEV-TEST"
        assert summaries[0]["level"] == 1

        # Level 1 is below the dashboard's min_level=2.
        assert asyncio.run(anomaly_scan.latest_anomaly_summaries(db, min_level=2)) == []

        # A second pass (breach_count=2) stays Level 1; the third promotes to 2.
        asyncio.run(anomaly_scan.scan_and_persist(db))
        asyncio.run(anomaly_scan.scan_and_persist(db))

        rows = sync_db.query(AnomalyScan).order_by(AnomalyScan.id).all()
        assert len(rows) == 3
        assert rows[-1].level == 2

        promoted = asyncio.run(anomaly_scan.latest_anomaly_summaries(db, min_level=2))
        assert len(promoted) == 1
        assert promoted[0]["level"] == 2
    finally:
        sync_db.close()


def _seed_device(sync_db, device_id, status):
    """Create one active device with the given (string) status."""
    from homepot.models import Device, LifecycleState

    device = Device(
        device_id=device_id,
        name=device_id,
        device_type="pos_terminal",
        site_id=1,
        is_active=True,
        lifecycle_state=LifecycleState.ACTIVE.value,
        status=status,
    )
    sync_db.add(device)
    sync_db.commit()
    sync_db.refresh(device)
    return device


def test_graceful_offline_not_scored(monkeypatch, isolated_db):
    """A gracefully-off device (goodbye heartbeat) is not an anomaly."""
    from homepot.app.ai_ops import anomaly_scan
    from homepot.app.models.AnalyticsModel import AnomalyScan
    from homepot.models import DeviceStatus

    sync_db = isolated_db()
    try:
        _seed_device(sync_db, "DEV-GRACEFUL", DeviceStatus.OFFLINE.value)
        monkeypatch.setattr(anomaly_scan, "compute_connectivity", lambda d: "offline")

        db = _FakeDB(sync_db)
        summaries = asyncio.run(anomaly_scan.scan_and_persist(db))
        assert summaries == []
        row = sync_db.query(AnomalyScan).order_by(AnomalyScan.id.desc()).first()
        assert row.level == 0
        assert row.score == 0.0
    finally:
        sync_db.close()


def test_unexpected_offline_is_scored(monkeypatch, isolated_db):
    """An unexpected outage (stale heartbeat, status still online) is scored."""
    from homepot.app.ai_ops import anomaly_scan
    from homepot.models import DeviceStatus

    sync_db = isolated_db()
    try:
        _seed_device(sync_db, "DEV-UNEXPECTED", DeviceStatus.ONLINE.value)
        monkeypatch.setattr(anomaly_scan, "compute_connectivity", lambda d: "offline")

        db = _FakeDB(sync_db)
        summaries = asyncio.run(anomaly_scan.scan_and_persist(db))
        assert len(summaries) == 1
        assert summaries[0]["device_id"] == "DEV-UNEXPECTED"
        assert summaries[0]["level"] >= 1
    finally:
        sync_db.close()


def test_device_monitoring_active_manual_auto_and_dismiss(isolated_db):
    """monitoring_active reflects manual pin, Level-2 auto, and dismiss."""
    from homepot.app.ai_ops import anomaly_scan
    from homepot.app.models.AnalyticsModel import AnomalyScan
    from homepot.models import Device, DeviceStatus, LifecycleState

    sync_db = isolated_db()

    def _make(device_id, *, is_monitored, dismissed_until=None):
        device = Device(
            device_id=device_id,
            name=device_id,
            device_type="pos_terminal",
            site_id=1,
            is_active=True,
            lifecycle_state=LifecycleState.ACTIVE.value,
            status=DeviceStatus.ONLINE.value,
            is_monitored=is_monitored,
            monitor_dismissed_until=dismissed_until,
        )
        sync_db.add(device)
        sync_db.commit()
        sync_db.refresh(device)
        return device

    async def _active(db, device):
        async with db.get_session() as session:
            return await anomaly_scan.device_monitoring_active(session, device)

    try:
        manual = _make("DEV-MANUAL", is_monitored=True)
        auto = _make("DEV-AUTO", is_monitored=False)
        plain = _make("DEV-PLAIN", is_monitored=False)
        dismissed = _make(
            "DEV-DISMISSED",
            is_monitored=False,
            dismissed_until=datetime.now(timezone.utc) + timedelta(minutes=30),
        )

        # Level 2 scans for the auto and dismissed devices.
        for dev_id in ("DEV-AUTO", "DEV-DISMISSED"):
            sync_db.add(
                AnomalyScan(
                    device_id=dev_id,
                    score=0.5,
                    level=2,
                    severity="warning",
                    reasons=[],
                )
            )
        sync_db.commit()

        db = _FakeDB(sync_db)
        assert asyncio.run(_active(db, manual)) is True
        assert asyncio.run(_active(db, auto)) is True
        assert asyncio.run(_active(db, plain)) is False
        assert asyncio.run(_active(db, dismissed)) is False
    finally:
        sync_db.close()
