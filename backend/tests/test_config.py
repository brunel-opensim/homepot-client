"""Test Configuration for HOMEPOT Test Suites.

This module provides centralized configuration for all HOMEPOT tests,
making it easy to adjust test parameters and environments.
"""

import os


class TestConfig:
    """Centralized test configuration."""

    # Base URLs
    LOCAL_BASE_URL = "http://localhost:8000"
    STAGING_BASE_URL = os.getenv(
        "HOMEPOT_STAGING_URL", "http://staging.homepot.local:8000"
    )
    PROD_BASE_URL = os.getenv("HOMEPOT_PROD_URL", "http://prod.homepot.local:8000")

    # Test Environment
    TEST_ENV = os.getenv("HOMEPOT_TEST_ENV", "local")

    @property
    def base_url(self) -> str:
        """Get base URL based on test environment."""
        if self.TEST_ENV == "staging":
            return self.STAGING_BASE_URL
        elif self.TEST_ENV == "production":
            return self.PROD_BASE_URL
        else:
            return self.LOCAL_BASE_URL

    # Timeouts
    DEFAULT_TIMEOUT = 30.0
    QUICK_TIMEOUT = 5.0
    LONG_TIMEOUT = 60.0

    # Performance Test Parameters
    PERFORMANCE_CONFIG = {
        "response_time_threshold_ms": 1000,
        "max_response_time_ms": 2000,
        "concurrent_users": [5, 10, 20],
        "stress_test_duration": 60,
        "min_requests_per_second": 5,
        "max_error_rate_percent": 5.0,
    }

    # Load Test Parameters
    LOAD_TEST_CONFIG = {
        "ramp_up_users": [1, 5, 10, 20, 50],
        "test_duration": 120,
        "think_time_ms": 100,
    }

    # Database Test Parameters
    DB_TEST_CONFIG = {
        "query_timeout_ms": 3000,
        "large_data_limits": [500, 1000, 2000],
        "bulk_operation_size": 100,
    }

    # Agent Simulation Parameters
    AGENT_TEST_CONFIG = {
        "max_agents_to_test": 50,
        "agent_states": ["idle", "processing", "error", "maintenance"],
        "state_transition_delay": 0.1,
    }

    # Audit System Parameters
    AUDIT_TEST_CONFIG = {
        "event_types": ["transaction", "error", "system", "security"],
        "batch_sizes": [10, 50, 100],
        "retention_test_days": 30,
    }


class TestData:
    """Test data and fixtures."""

    # Sample site data
    SAMPLE_SITE = {
        "name": "Test Store",
        "location": "Test City",
        "manager": "Test Manager",
        "active": True,
    }

    # Sample agent data
    SAMPLE_AGENT = {
        "agent_id": "TEST_AGENT_001",
        "site_id": 1,
        "hardware_id": "TEST_HW_001",
        "status": "active",
        "last_heartbeat": "2024-01-01T12:00:00Z",
    }

    # Sample transaction data
    SAMPLE_TRANSACTION = {
        "amount": 25.50,
        "currency": "USD",
        "payment_method": "card",
        "terminal_id": "TEST_TERM_001",
    }

    # Sample audit event
    SAMPLE_AUDIT_EVENT = {
        "event_type": "transaction",
        "severity": "info",
        "message": "Test transaction processed",
        "metadata": {"test": True},
    }


class TestHelpers:
    """Helper functions for tests."""

    @staticmethod
    def get_config() -> TestConfig:
        """Get test configuration instance."""
        return TestConfig()

    @staticmethod
    def get_test_data() -> TestData:
        """Get test data instance."""
        return TestData()

    @staticmethod
    def is_system_ready(base_url: str, timeout: float = 5.0) -> bool:
        """Check if the HOMEPOT system is ready for testing."""
        import requests

        try:
            response = requests.get(f"{base_url}/health", timeout=timeout)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    @staticmethod
    def wait_for_system(base_url: str, max_wait: int = 30) -> bool:
        """Wait for system to be ready, up to max_wait seconds."""
        import time

        for _ in range(max_wait):
            if TestHelpers.is_system_ready(base_url):
                return True
            time.sleep(1)
        return False

    @staticmethod
    def generate_test_id() -> str:
        """Generate a unique test ID."""
        import uuid

        return f"test_{uuid.uuid4().hex[:8]}"


# Global test configuration instance
config = TestConfig()
test_data = TestData()
helpers = TestHelpers()
