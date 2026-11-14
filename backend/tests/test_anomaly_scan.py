"""Tests for multi-level anomaly detection (anomaly_scan service)."""

import asyncio
from contextlib import asynccontextmanager
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
