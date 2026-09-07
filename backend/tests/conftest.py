"""Test configuration and fixtures for HOMEPOT Client tests.

This module provides common test configuration, fixtures, and utilities
used across the test suite.
"""

import faulthandler
import os
import threading
import time
from typing import Any, Dict, Generator

from fastapi.testclient import TestClient
import pytest

# Default to SQLite in-memory for testing, unless a DATABASE__URL has
# already been provided by the environment (e.g. CI providing a real
# PostgreSQL/TimescaleDB test database). This must happen before any local
# imports evaluate the settings globally.
os.environ.setdefault("DATABASE__URL", "sqlite+aiosqlite:///:memory:")

# Configure asyncio for testing
pytest_plugins = ("pytest_asyncio",)


def _arm_session_watchdog() -> None:
    """Arm a process-wide watchdog that covers collection/import time.

    pytest's own faulthandler only arms around each test's setup/call/teardown,
    so a hang during module import or collection is invisible to it. When CI
    sets HOMEPOT_CI_WATCHDOG_SECS, dump all thread tracebacks and exit after
    the cap as a final backstop. (The primary guard against a hung test is the
    shell-level file-growth watchdog in ci-cd.yml, which kills pytest outside
    of Python when its log stops growing.)
    """
    timeout = os.environ.get("HOMEPOT_CI_WATCHDOG_SECS")
    path = os.environ.get("HOMEPOT_CI_WATCHDOG_LOG", "pytest-watchdog.log")
    if not timeout:
        return
    try:
        # Keep the handle referenced (and open) until the timeout fires;
        # dump_traceback_later writes to it asynchronously much later.
        global _WATCHDOG_FILE
        _WATCHDOG_FILE = open(path, "w", encoding="utf-8")
        faulthandler.dump_traceback_later(
            float(timeout), file=_WATCHDOG_FILE, exit=True
        )
    except (OSError, ValueError):
        # Best-effort only; CI must not fail if the watchdog cannot be armed.
        pass


_WATCHDOG_FILE = None
_CURRENT_TEST = "collect"  # set by pytest_runtest hook as tests execute


def _watchdog_thread(path: str, timeout: float) -> None:
    """Daemon-thread watchdog: heartbeat + hard os._exit after the cap.

    Runs entirely inside the pytest process so it is immune to the MSYS /
    PowerShell process-kill failures observed on Windows runners, where a
    hung native python.exe cannot be signaled or killed from outside but a
    Python thread that acquires the GIL periodically can still call
    os._exit(). Appends a heartbeat naming the in-flight test every
    WATCHDOG_HEARTBEAT_SECS so CI can see the exact stuck test even if the
    log is only finalized after the process self-terminates.
    """
    start = time.monotonic()
    beat = float(os.environ.get("HOMEPOT_WATCHDOG_HEARTBEAT_SECS", "10"))
    try:
        f = open(path, "a", encoding="utf-8", buffering=1)
    except OSError:
        return
    with f:
        while True:
            elapsed = int(time.monotonic() - start)
            f.write(
                f"[watchdog] t={elapsed:>6}s in-test={_CURRENT_TEST}\n"
            )
            if elapsed >= int(timeout):
                trace_path = path + ".traceback"
                try:
                    with open(trace_path, "w", encoding="utf-8") as tf:
                        faulthandler.dump_traceback(file=tf)
                except OSError:
                    pass
                f.write("[watchdog] HARD EXIT after %ss\n" % elapsed)
                os._exit(1)
            time.sleep(beat)


def _arm_session_watchdog() -> None:
    """Arm a process-wide watchdog that covers collection/import time.

    pytest's own faulthandler only arms around each test's setup/call/teardown,
    so a hang during module import or collection is invisible to it. When CI
    sets HOMEPOT_CI_WATCHDOG_SECS, a daemon thread records a heartbeat naming
    the in-flight test/phase and force-exits the process via os._exit after the
    cap. The heartbeat file is closed on every write, so Windows CI can read it
    even if the process later self-terminates.
    """
    timeout = os.environ.get("HOMEPOT_CI_WATCHDOG_SECS")
    path = os.environ.get("HOMEPOT_CI_WATCHDOG_LOG", "pytest-watchdog.log")
    if not timeout:
        return
    try:
        # Clear previous content (we append in the thread).
        with open(path, "w", encoding="utf-8"):
            pass
        threading.Thread(
            target=_watchdog_thread,
            args=(path, float(timeout)),
            daemon=True,
        ).start()
    except (OSError, ValueError):
        # Best-effort only; CI must not fail if the watchdog cannot be armed.
        pass


def pytest_runtest_call(item: pytest.Item) -> None:
    """Track the node id of the currently running test for the watchdog."""
    global _CURRENT_TEST
    _CURRENT_TEST = item.nodeid


_arm_session_watchdog()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create a test client for the HOMEPOT application."""
    from homepot.client import HomepotClient
    from homepot.main import app, get_client

    # Create a mock client for testing
    def get_test_client() -> HomepotClient:
        """Override the client dependency for testing."""
        # Create a mock client that appears connected
        mock_client = HomepotClient()
        # Mock the connection methods to avoid actual network calls
        mock_client.is_connected = lambda: True  # type: ignore
        mock_client.get_version = lambda: "0.1.0"  # type: ignore
        return mock_client

    # Override the dependency for both locations it might be imported from natively
    app.dependency_overrides[get_client] = get_test_client

    # Also override the one locally defined in HealthEndpoint
    from homepot.app.api.API_v1.Endpoints.HealthEndpoint import (
        get_client as get_health_client,
    )

    app.dependency_overrides[get_health_client] = get_test_client

    # Use TestClient as a context manager so FastAPI's lifespan handlers run.
    # This ensures the database service (and its in-memory SQLite schema) is
    # initialized once, on a single persistent event loop, instead of being
    # lazily (and inconsistently) initialized per-request.
    with TestClient(app) as test_client:
        yield test_client

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
async def reset_db_service():
    """Reset the database service singleton after each test."""
    from homepot.database import close_database_service

    yield
    await close_database_service()


@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """Provide a sample configuration for testing."""
    return {
        "host": "localhost",
        "port": 8080,
        "timeout": 30,
        "secure": True,
        "consortium_id": "test-consortium",
    }


@pytest.fixture
def invalid_config() -> Dict[str, Any]:
    """Provide an invalid configuration for testing error cases."""
    return {
        "host": "",
        "port": -1,
        "timeout": "invalid",
    }


@pytest.fixture
async def async_client():
    """Create an async test client for the HOMEPOT application."""
    from httpx import ASGITransport, AsyncClient

    from homepot.app.main import app

    # Create async client with ASGI transport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    import logging

    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import OperationalError, ProgrammingError
    from sqlalchemy.orm import sessionmaker

    # Importing registers ErrorLog (and other analytics tables) with
    # Base.metadata so create_all() below also creates them.
    from homepot.app.models.AnalyticsModel import ErrorLog  # noqa: F401
    from homepot.config import get_settings
    from homepot.models import Base

    logger = logging.getLogger(__name__)

    # Get database URL from config
    settings = get_settings()
    database_url = settings.database.url

    # Convert async URLs to sync for testing
    if database_url.startswith("sqlite+aiosqlite://"):
        database_url = database_url.replace("sqlite+aiosqlite://", "sqlite://")
    elif database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://"
        )

    engine = None
    use_postgresql = "postgresql" in database_url

    # Handle PostgreSQL test database creation
    if use_postgresql:
        # Extract and modify database name for testing
        parts = database_url.rsplit("/", 1)
        if len(parts) == 2:
            base_url, db_name = parts
            # Remove any query parameters
            db_name = db_name.split("?")[0]
            test_db_name = f"{db_name}_test"
            test_database_url = f"{base_url}/{test_db_name}"

            # Try to create test database if it doesn't exist
            try:
                # Connect to default 'postgres' database to create test database
                admin_url = f"{base_url}/postgres"
                admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

                with admin_engine.connect() as conn:
                    # Check if test database exists
                    result = conn.execute(
                        text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                        {"dbname": test_db_name},
                    )
                    exists = result.fetchone() is not None

                    if not exists:
                        logger.info(f"Creating test database: {test_db_name}")
                        conn.execute(text(f'CREATE DATABASE "{test_db_name}"'))
                        logger.info(
                            f"Test database created successfully: {test_db_name}"
                        )

                admin_engine.dispose()

                # Now connect to the test database
                engine = create_engine(
                    test_database_url, pool_pre_ping=True, pool_size=5, max_overflow=10
                )

            except (OperationalError, ProgrammingError) as e:
                logger.warning(
                    f"PostgreSQL not available or error creating test DB: {e}"
                )
                logger.info("Falling back to SQLite in-memory database for testing")
                use_postgresql = False

    # Fallback to SQLite if PostgreSQL failed or not configured
    if not use_postgresql or engine is None:
        target_url = "sqlite:///:memory:"

        # If we are here because it's configured as SQLite (not because Postgres failed)
        if not use_postgresql and database_url.startswith("sqlite"):
            target_url = database_url

        logger.info(f"Using SQLite database for testing: {target_url}")
        engine = create_engine(
            target_url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session maker
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def get_test_db():
        """Get test database session."""
        db = TestingSessionLocal()
        return db

    yield get_test_db

    # Cleanup - drop all tables after tests
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
