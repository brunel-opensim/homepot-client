"""Test configuration and fixtures for HOMEPOT Client tests.

This module provides common test configuration, fixtures, and utilities
used across the test suite.
"""

import pytest
import asyncio
from typing import Generator, Dict, Any

# Configure asyncio for testing
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


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
