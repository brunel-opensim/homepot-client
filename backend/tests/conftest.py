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
