"""Tests for OS family classification used by site OS icons and capabilities."""

import asyncio
from datetime import datetime, timezone
import os
import tempfile
from typing import Any, Generator

from fastapi.testclient import TestClient
import pytest

from homepot.app.auth_utils import create_access_token, hash_password
from homepot.app.main import app
from homepot.app.schemas.permissions import (
    derive_capabilities,
    derive_push_channel,
    os_family,
)
from homepot.config import reload_settings
import homepot.database
from homepot.models import Base, Device, DeviceStatus, Site, User


@pytest.mark.parametrize(
    ("os_details", "expected"),
    [
        (None, None),
        ("", None),
        ("unknown-runtime", None),
        ("windows", "windows"),
        ("Windows 11", "windows"),
        ("win32", "windows"),
        ("linux", "linux"),
        ("Linux 6.8.0 (Debian 12)", "linux"),
        ("ubuntu 22.04", "linux"),
        ("debian 12", "linux"),
        ("macos", "macos"),
        ("macOS 14", "macos"),
        ("darwin", "macos"),
        ("ios", "ios"),
        ("iOS 17", "ios"),
        ("ipados", "ios"),
        ("android", "android"),
        ("Android 14", "android"),
    ],
)
def test_os_family(os_details, expected):
    """os_family maps both short tokens and versioned emulator strings."""
    assert os_family(os_details) is expected


def test_os_family_distinguishes_apple_families():
    """Apple OS families must remain distinct from Linux."""
    assert os_family("macOS 14") == "macos"
    assert os_family("iOS 17") == "ios"
    assert os_family("Linux 6.8.0 (Debian 12)") == "linux"


def test_derive_push_channel_still_consistent():
    """Push-channel derivation is preserved via os_family."""
    assert derive_push_channel("Android 14") == "fcm"
    assert derive_push_channel("Windows 11") == "wns"
    assert derive_push_channel("iOS 17") == "apns"
    assert derive_push_channel("macOS 14") is None
    assert derive_push_channel("Linux 6.8.0 (Debian 12)") is None


def test_derive_capabilities_still_consistent():
    """Capability derivation is preserved via os_family."""
    caps_linux = derive_capabilities("Linux 6.8.0 (Debian 12)")
    caps_macos = derive_capabilities("macOS 14")
    caps_ios = derive_capabilities("iOS 17")
    caps_android = derive_capabilities("Android 14")
    assert caps_linux["command_execution"] is True
    assert caps_macos["root_access"] is True
    assert caps_ios["network_monitoring"] is True
    assert caps_ios["command_execution"] is False
    assert caps_android["command_execution"] is True
    assert caps_android["root_access"] is False
    assert derive_capabilities(None)["root_access"] is False


@pytest.fixture
def file_db(monkeypatch: Any) -> Generator[None, None, None]:
    """Use a temp file-based SQLite DB so sync+async engines share data."""
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

    new_engine = __import__("sqlalchemy").create_engine(
        db_url, connect_args={"check_same_thread": False}, pool_pre_ping=True
    )
    Base.metadata.create_all(bind=new_engine)
    new_session_local = __import__(
        "sqlalchemy.orm", fromlist=["sessionmaker"]
    ).sessionmaker(bind=new_engine, autocommit=False, autoflush=False)

    monkeypatch.setattr(homepot.database, "sync_engine", new_engine)
    monkeypatch.setattr(homepot.database, "SessionLocal", new_session_local)

    yield

    new_engine.dispose()
    if os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


def _seed_site_with_devices(site_id: str, devices: list[dict]) -> None:
    """Seed a site and its devices, returning the created site."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(
        homepot.database.sync_engine.url,
        connect_args={"check_same_thread": False},
    )
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()
    try:
        site = Site(site_id=site_id, name=f"Site {site_id}", is_active=True)
        session.add(site)
        session.commit()
        session.refresh(site)

        for spec in devices:
            device = Device(
                device_id=spec["device_id"],
                name=spec["name"],
                device_type=spec.get("device_type", "pos_terminal"),
                site_id=site.id,
                is_active=True,
                status=DeviceStatus.ONLINE,
                os_details=spec.get("os_details"),
                config=spec.get("config"),
            )
            session.add(device)
        session.commit()
    finally:
        session.close()


def _admin_token(email: str = "admin@osfamily.test") -> str:
    """Create an admin user and return an access token."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(
        homepot.database.sync_engine.url,
        connect_args={"check_same_thread": False},
    )
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()
    try:
        admin = User(
            email=email,
            username="admin_osfamily",
            hashed_password=hash_password("pass"),
            is_admin=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(admin)
        session.commit()
    finally:
        session.close()
    return create_access_token({"sub": email})


def test_site_os_types_include_emulator_os(file_db: Any) -> None:
    """Emulator devices with versioned os_details surface canonical OS icons."""
    _seed_site_with_devices(
        "site-emulators",
        [
            {
                "device_id": "win-emu-1",
                "name": "windows-pos-emulator-1",
                "os_details": "Windows 11",
                "config": {"os": "Windows 11", "device_source": "emulator"},
            },
            {
                "device_id": "ios-emu-1",
                "name": "ios-pos-emulator-1",
                "device_type": "tablet",
                "os_details": "iOS 17",
                "config": {"os": "iOS 17", "device_source": "emulator"},
            },
        ],
    )
    token = _admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    client = TestClient(app)
    response = client.get("/api/v1/sites", headers=headers)
    assert response.status_code == 200
    sites = response.json()["sites"]
    site = next(s for s in sites if s["site_id"] == "site-emulators")
    assert "windows" in site["os_types"]
    assert "ios" in site["os_types"]


def test_site_os_types_include_simulated_os(file_db: Any) -> None:
    """Simulated devices (short config['os'] tokens) still map to canonical keys."""
    _seed_site_with_devices(
        "site-simulated",
        [
            {
                "device_id": "sim-android-1",
                "name": "android-pos-sim-1",
                "os_details": "Android 14",
                "config": {"os": "android", "device_source": "simulator"},
            },
            {
                "device_id": "sim-linux-1",
                "name": "linux-pos-sim-1",
                "os_details": "Linux 6.8.0 (Debian 12)",
                "config": {"os": "linux", "device_source": "simulator"},
            },
        ],
    )
    token = _admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    client = TestClient(app)
    response = client.get("/api/v1/sites", headers=headers)
    assert response.status_code == 200
    sites = response.json()["sites"]
    site = next(s for s in sites if s["site_id"] == "site-simulated")
    assert "android" in site["os_types"]
    assert "linux" in site["os_types"]


def test_site_os_types_fallback_to_name_inference(file_db: Any) -> None:
    """Devices without OS info fall back to name-based inference."""
    _seed_site_with_devices(
        "site-names",
        [
            {"device_id": "unknown-mac-thing", "name": "backoffice-mac-1"},
            {"device_id": "unknown-web-thing", "name": "portal-web-1"},
        ],
    )
    token = _admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    client = TestClient(app)
    response = client.get("/api/v1/sites", headers=headers)
    assert response.status_code == 200
    sites = response.json()["sites"]
    site = next(s for s in sites if s["site_id"] == "site-names")
    assert "macos" in site["os_types"]
    assert "web" in site["os_types"]


def test_devices_by_site_includes_os_family(file_db: Any) -> None:
    """Devices in a site expose a canonical os_family key for icon rendering."""
    _seed_site_with_devices(
        "site-family-payload",
        [
            {
                "device_id": "win-dev-1",
                "name": "windows-pc-1",
                "os_details": "Windows 11",
                "config": {"os": "Windows 11", "device_source": "emulator"},
            },
            {
                "device_id": "android-dev-1",
                "name": "android-phone-1",
                "os_details": "Android 14",
                "config": {"os": "android", "device_source": "simulator"},
            },
            {
                "device_id": "no-info-dev-1",
                "name": "generic-device-1",
                "os_details": None,
                "config": None,
            },
        ],
    )
    token = _admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    client = TestClient(app)
    response = client.get(
        "/api/v1/devices/sites/site-family-payload/devices", headers=headers
    )
    assert response.status_code == 200
    by_id = {d["device_id"]: d for d in response.json()}
    assert by_id["win-dev-1"]["os_family"] == "windows"
    assert by_id["win-dev-1"]["os_details"] == "Windows 11"
    assert by_id["android-dev-1"]["os_family"] == "android"
    # No OS info anywhere -> no canonical family
    assert by_id["no-info-dev-1"]["os_family"] is None
