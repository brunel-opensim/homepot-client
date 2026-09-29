"""Tests that device commands record who issued them.

Two technicians can work the same device at once, and the command queue used
to be anonymous: it stored no actor at all, so nothing could say who last
touched a device. These tests cover the record itself and its exposure on the
command history endpoint.
"""

import asyncio
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from homepot.app.api.API_v1.Endpoints.DeviceCommandsEndpoint import (
    CommandHistoryResponse,
)
from homepot.config import reload_settings
import homepot.database
from homepot.models import (
    Base,
    CommandStatus,
    Device,
    DeviceCommand,
    DeviceType,
    Site,
)


@pytest.fixture
def db_service(monkeypatch):
    """Provide a database service backed by a temporary SQLite file."""
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

    # Tables are created through a sync engine, matching the pattern used by the
    # rest of the suite; the async service then opens its own sessions on the
    # same file.
    engine = create_engine(
        db_url, connect_args={"check_same_thread": False}, pool_pre_ping=True
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(homepot.database, "sync_engine", engine)
    monkeypatch.setattr(homepot.database, "SessionLocal", session_factory)

    service = homepot.database.DatabaseService()
    homepot.database._db_service = service

    yield service

    asyncio.run(service.close())
    homepot.database._db_service = None
    engine.dispose()
    if os.path.exists(path):
        os.unlink(path)


async def _make_device(service):
    """Create a site and a device to hang commands off."""
    async with service.get_session() as session:
        site = Site(site_id="site-issued-by", name="Test Site")
        session.add(site)
        await session.flush()
        device = Device(
            device_id="dev-issued-by",
            name="Device",
            device_type=DeviceType.POS_TERMINAL.value,
            site_id=site.id,
        )
        session.add(device)
        await session.flush()
        return device.id


async def test_create_device_command_records_the_actor(db_service):
    """The issuing user is stored on the command."""
    device_pk = await _make_device(db_service)
    command = await db_service.create_device_command(
        device_id=device_pk, command_type="ping", issued_by="tech@example.com"
    )
    assert command.issued_by == "tech@example.com"


async def test_issued_by_defaults_to_none(db_service):
    """Callers that do not supply an actor still work, as pre-existing rows have none."""
    device_pk = await _make_device(db_service)
    command = await db_service.create_device_command(
        device_id=device_pk, command_type="ping"
    )
    assert command.issued_by is None


async def test_actor_survives_a_reload(db_service):
    """The actor is persisted, not just attached to the returned instance."""
    device_pk = await _make_device(db_service)
    await db_service.create_device_command(
        device_id=device_pk, command_type="restart", issued_by="tech@example.com"
    )
    stored = await db_service.get_commands_for_device(device_pk)
    assert [c.issued_by for c in stored] == ["tech@example.com"]


def test_history_response_exposes_the_actor():
    """The history endpoint can now tell the dashboard who issued a command."""
    response = CommandHistoryResponse(
        command_id="abc",
        command_type="restart",
        status=CommandStatus.PENDING,
        created_at="2026-09-29T10:00:00+00:00",
        issued_by="tech@example.com",
    )
    assert response.issued_by == "tech@example.com"


def test_history_response_actor_is_optional():
    """Rows predating the column report no actor rather than failing."""
    response = CommandHistoryResponse(
        command_id="abc",
        command_type="restart",
        status=CommandStatus.PENDING,
        created_at="2026-09-29T10:00:00+00:00",
    )
    assert response.issued_by is None


def test_device_command_model_has_the_column():
    """The column exists on the model, so create_all builds it for fresh databases."""
    assert DeviceCommand.__table__.c.issued_by.nullable is True
