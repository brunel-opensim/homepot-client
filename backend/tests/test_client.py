"""Unit tests for HOMEPOT Client core functionality.

This module contains comprehensive unit tests for the main client classes
and functions. These tests verify the basic functionality and serve as a
foundation for the larger project test suite.
"""

from typing import Any, Dict

import pytest

from homepot_client import __version__
from homepot_client.client import HomepotClient, create_client


class TestHomepotClient:
    """Test suite for the HomepotClient class."""

    def test_client_initialization_default(self) -> None:
        """Test client initialization with default configuration."""
        client = HomepotClient()

        assert client.config == {}
        assert client.connected is False
        assert client.is_connected() is False

    def test_client_initialization_with_config(
        self, sample_config: Dict[str, Any]
    ) -> None:
        """Test client initialization with provided configuration."""
        client = HomepotClient(sample_config)

        assert client.config == sample_config
        assert client.connected is False
        assert client.is_connected() is False

    @pytest.mark.asyncio
    async def test_client_connect_success(self) -> None:
        """Test successful client connection."""
        client = HomepotClient()

        result = await client.connect()

        assert result is True
        assert client.connected is True
        assert client.is_connected() is True

    @pytest.mark.asyncio
    async def test_client_disconnect(self) -> None:
        """Test client disconnection."""
        client = HomepotClient()
        await client.connect()  # First connect

        await client.disconnect()

        assert client.connected is False
        assert client.is_connected() is False

    def test_client_get_version(self) -> None:
        """Test getting client version."""
        client = HomepotClient()

        version = client.get_version()

        assert version == __version__
        assert isinstance(version, str)
        assert len(version) > 0


class TestClientFactory:
    """Test suite for the client factory function."""

    def test_create_client_default(self) -> None:
        """Test creating client with default configuration."""
        client = create_client()

        assert isinstance(client, HomepotClient)
        assert client.config == {}
        assert client.connected is False

    def test_create_client_with_config(self, sample_config: Dict[str, Any]) -> None:
        """Test creating client with provided configuration."""
        client = create_client(sample_config)

        assert isinstance(client, HomepotClient)
        assert client.config == sample_config
        assert client.connected is False


class TestPackageInfo:
    """Test suite for package-level information."""

    def test_version_format(self) -> None:
        """Test that version follows semantic versioning format."""
        version_parts = __version__.split(".")

        assert len(version_parts) >= 3
        for part in version_parts[:3]:
            assert part.isdigit()

    def test_version_not_empty(self) -> None:
        """Test that version is not empty."""
        assert __version__
        assert len(__version__) > 0


@pytest.mark.integration
class TestClientIntegration:
    """Integration tests for client functionality.

    These tests verify that different components work together correctly.
    They can be skipped during quick unit test runs.
    """

    @pytest.mark.asyncio
    async def test_client_lifecycle(self, sample_config: Dict[str, Any]) -> None:
        """Test complete client lifecycle: create, connect, disconnect."""
        # Create client
        client = create_client(sample_config)
        assert not client.is_connected()

        # Connect
        result = await client.connect()
        assert result is True
        assert client.is_connected()

        # Verify version
        version = client.get_version()
        assert version == __version__

        # Disconnect
        await client.disconnect()
        assert not client.is_connected()


@pytest.mark.slow
class TestClientPerformance:
    """Performance tests for client operations.

    These tests verify that operations complete within acceptable time limits.
    They are marked as slow and can be skipped during quick test runs.
    """

    @pytest.mark.asyncio
    async def test_connect_performance(self) -> None:
        """Test that connection completes within reasonable time."""
        import time

        client = HomepotClient()
        start_time = time.time()

        await client.connect()

        elapsed_time = time.time() - start_time
        assert elapsed_time < 1.0  # Should complete within 1 second


# Dummy test to verify test suite setup
def test_dummy_always_passes() -> None:
    """Dummy test that always passes to verify test setup.

    This test can be removed once real functionality is implemented.
    It serves as a sanity check that the test environment is working correctly.
    """
    assert True
    assert 1 + 1 == 2
    assert "HOMEPOT" in "HOMEPOT Client"


def test_python_version_compatibility() -> None:
    """Test that we're running on a supported Python version."""
    import sys

    # HOMEPOT Client requires Python 3.9+
    assert sys.version_info >= (3, 9)


def test_imports_work() -> None:
    """Test that all main imports work correctly."""
    # Test importing main package
    import homepot_client

    assert hasattr(homepot_client, "__version__")

    # Test importing main classes
    from homepot_client.client import HomepotClient, create_client

    assert HomepotClient is not None
    assert create_client is not None

    # Test that we can create instances
    client = create_client()
    assert isinstance(client, HomepotClient)
