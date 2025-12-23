"""Test configuration and fixtures for HOMEPOT Client tests.

This module provides common test configuration, fixtures, and utilities
used across the test suite.
"""

import asyncio
from typing import Any, Dict, Generator

import pytest
from fastapi.testclient import TestClient

# Configure asyncio for testing
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


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

    # Override the dependency
    app.dependency_overrides[get_client] = get_test_client

    test_client = TestClient(app)

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

    from homepot.config import get_settings
    from homepot.models import Base

    logger = logging.getLogger(__name__)

    # Get database URL from config
    settings = get_settings()
    database_url = settings.database.url

    # Convert async URLs to sync for testing
    if database_url.startswith("sqlite+aiosqlite://"):
        database_url = database_url.replace("sqlite+aiosqlite://", "sqlite:///")
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
