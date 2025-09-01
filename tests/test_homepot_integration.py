"""Comprehensive Integration Tests for HOMEPOT Four-Phase Implementation.

This test suite validates the complete HOMEPOT POS management system including:
- Phase 1: Core Infrastructure & Database
- Phase 2: Enhanced API Endpoints & WebSocket Dashboard
- Phase 3: Realistic Agent Simulation & Health Checks
- Phase 4: Comprehensive Audit Logging & System Metrics

The tests use httpx for async HTTP testing and cover the full API surface.
"""

import os
import time

import httpx
import pytest
from fastapi.testclient import TestClient

# Test Configuration
TEST_BASE_URL = "http://localhost:8000"
TEST_TIMEOUT = 30.0

# Skip live tests in CI environments
skip_live_tests = pytest.mark.skipif(
    os.environ.get("CI") is not None,
    reason="Integration tests skipped in CI environment - requires running server",
)


@skip_live_tests
class TestHOMEPOTSystem:
    """Comprehensive system tests for all four phases of HOMEPOT implementation."""

    @pytest.fixture(scope="class")
    def client(self) -> TestClient:
        """Create a test client for the HOMEPOT application."""
        from homepot_client.main import app

        return TestClient(app)

    @pytest.fixture(scope="class")
    async def async_client(self) -> httpx.AsyncClient:
        """Create an async HTTP client for testing."""
        async with httpx.AsyncClient(
            base_url=TEST_BASE_URL, timeout=TEST_TIMEOUT
        ) as client:
            yield client


@pytest.mark.integration
@skip_live_tests
class TestPhase1CoreInfrastructure:
    """Test Phase 1: Core Infrastructure & Database functionality."""

    def test_health_endpoint(self, client: TestClient) -> None:
        """Test system health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "client_connected" in data
        assert "version" in data
        assert data["version"] == "0.1.0"

    def test_version_endpoint(self, client: TestClient) -> None:
        """Test version information endpoint."""
        response = client.get("/version")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert data["version"] == "0.1.0"

    def test_status_endpoint(self, client: TestClient) -> None:
        """Test client status endpoint."""
        response = client.get("/status")

        assert response.status_code == 200
        data = response.json()
        assert "connected" in data
        assert "version" in data
        assert "uptime" in data

    def test_root_endpoint(self, client: TestClient) -> None:
        """Test root API information endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "docs" in data
        assert data["docs"] == "/docs"


@pytest.mark.integration
@skip_live_tests
class TestPhase2APIEndpoints:
    """Test Phase 2: Enhanced API Endpoints & WebSocket Dashboard."""

    def test_list_sites(self, client: TestClient) -> None:
        """Test listing all POS sites."""
        response = client.get("/sites")

        assert response.status_code == 200
        sites = response.json()
        assert isinstance(sites, list)
        assert len(sites) >= 14  # Should have pre-configured sites

        # Verify site structure
        if sites:
            site = sites[0]
            assert "site_id" in site
            assert "name" in site
            assert "created_at" in site

    def test_get_specific_site(self, client: TestClient) -> None:
        """Test getting specific site information."""
        # First get a site ID
        sites_response = client.get("/sites")
        sites = sites_response.json()

        if sites:
            site_id = sites[0]["site_id"]
            response = client.get(f"/sites/{site_id}")

            assert response.status_code == 200
            site = response.json()
            assert site["site_id"] == site_id
            assert "name" in site
            assert "created_at" in site

    def test_create_site(self, client: TestClient) -> None:
        """Test creating a new POS site."""
        test_site = {
            "site_id": "TEST_SITE_001",
            "name": "Test Site",
            "location": "Test Location",
            "type": "test",
        }

        response = client.post("/sites", json=test_site)

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "site_id" in data
        assert data["site_id"] == "TEST_SITE_001"

    def test_site_health(self, client: TestClient) -> None:
        """Test site health monitoring."""
        # Get a site ID first
        sites_response = client.get("/sites")
        sites = sites_response.json()

        if sites:
            site_id = sites[0]["site_id"]
            response = client.get(f"/sites/{site_id}/health")

            assert response.status_code == 200
            health = response.json()
            assert "site_id" in health
            assert "status" in health
            assert "health_percentage" in health
            assert health["site_id"] == site_id

    def test_device_registration(self, client: TestClient) -> None:
        """Test device registration at a site."""
        # Get a site ID first
        sites_response = client.get("/sites")
        sites = sites_response.json()

        if sites:
            site_id = sites[0]["site_id"]
            test_device = {
                "device_id": "TEST_DEVICE_001",
                "device_type": "pos_terminal",
                "location": "Test Counter",
            }

            response = client.post(f"/sites/{site_id}/devices", json=test_device)

            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "device_id" in data
            assert data["device_id"] == "TEST_DEVICE_001"

    def test_job_creation(self, client: TestClient) -> None:
        """Test creating a job for a site."""
        # Get a site ID first
        sites_response = client.get("/sites")
        sites = sites_response.json()

        if sites:
            site_id = sites[0]["site_id"]
            test_job = {
                "job_type": "config_update",
                "priority": "medium",
                "config": {"test_setting": "test_value"},
            }

            response = client.post(f"/sites/{site_id}/jobs", json=test_job)

            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "job_id" in data


@pytest.mark.integration
@skip_live_tests
class TestPhase3AgentSimulation:
    """Test Phase 3: Realistic Agent Simulation & Health Checks."""

    def test_list_agents(self, client: TestClient) -> None:
        """Test listing all active POS agents."""
        response = client.get("/agents")

        assert response.status_code == 200
        agents = response.json()
        assert isinstance(agents, list)
        assert len(agents) >= 20  # Should have many active agents

        # Verify agent structure
        if agents:
            agent = agents[0]
            assert "device_id" in agent
            assert "site_id" in agent
            assert "status" in agent
            assert "last_heartbeat" in agent

    def test_get_specific_agent(self, client: TestClient) -> None:
        """Test getting specific agent information."""
        # First get an agent ID
        agents_response = client.get("/agents")
        agents = agents_response.json()

        if agents:
            device_id = agents[0]["device_id"]
            response = client.get(f"/agents/{device_id}")

            assert response.status_code == 200
            agent = response.json()
            assert agent["device_id"] == device_id
            assert "status" in agent
            assert "health_metrics" in agent

    def test_agent_push_notification(self, client: TestClient) -> None:
        """Test sending push notification to agent."""
        # Get an agent ID first
        agents_response = client.get("/agents")
        agents = agents_response.json()

        if agents:
            device_id = agents[0]["device_id"]
            notification = {
                "message": "Test notification",
                "priority": "medium",
                "action": "test_action",
            }

            response = client.post(f"/agents/{device_id}/push", json=notification)

            assert response.status_code == 200
            data = response.json()
            assert "message" in data

    def test_device_health_check(self, client: TestClient) -> None:
        """Test device health check functionality."""
        # Get an agent ID first
        agents_response = client.get("/agents")
        agents = agents_response.json()

        if agents:
            device_id = agents[0]["device_id"]
            response = client.get(f"/devices/{device_id}/health")

            assert response.status_code == 200
            health = response.json()
            assert "device_id" in health
            assert "status" in health
            assert "metrics" in health

    def test_device_restart(self, client: TestClient) -> None:
        """Test device restart functionality."""
        # Get an agent ID first
        agents_response = client.get("/agents")
        agents = agents_response.json()

        if agents:
            device_id = agents[0]["device_id"]
            response = client.post(f"/devices/{device_id}/restart")

            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert device_id in data["message"]


@pytest.mark.integration
@skip_live_tests
class TestPhase4AuditLogging:
    """Test Phase 4: Comprehensive Audit Logging & System Metrics."""

    def test_audit_events(self, client: TestClient) -> None:
        """Test retrieving audit events."""
        response = client.get("/audit/events")

        assert response.status_code == 200
        events = response.json()
        assert isinstance(events, list)

        # Verify event structure
        if events:
            event = events[0]
            assert "id" in event
            assert "event_type" in event
            assert "category" in event
            assert "description" in event
            assert "timestamp" in event

    def test_audit_statistics(self, client: TestClient) -> None:
        """Test audit statistics endpoint."""
        response = client.get("/audit/statistics")

        assert response.status_code == 200
        stats = response.json()
        assert "total_events" in stats
        assert "events_by_category" in stats
        assert "events_by_severity" in stats
        assert isinstance(stats["total_events"], int)

    def test_audit_event_types(self, client: TestClient) -> None:
        """Test getting available audit event types."""
        response = client.get("/audit/event-types")

        assert response.status_code == 200
        event_types = response.json()
        assert isinstance(event_types, list)
        assert len(event_types) >= 20  # Should have 20+ event types


@pytest.mark.integration
@skip_live_tests
class TestEndToEndWorkflows:
    """Test complete end-to-end workflows across all phases."""

    def test_complete_site_setup_workflow(self, client: TestClient) -> None:
        """Test create site, add device, create job, monitor health."""
        # Step 1: Create a new site
        test_site = {
            "site_id": "E2E_TEST_SITE",
            "name": "End-to-End Test Site",
            "location": "Test Location",
            "type": "test",
        }

        site_response = client.post("/sites", json=test_site)
        assert site_response.status_code == 200

        # Step 2: Register a device at the site
        test_device = {
            "device_id": "E2E_TEST_DEVICE",
            "device_type": "pos_terminal",
            "location": "Test Counter",
        }

        device_response = client.post("/sites/E2E_TEST_SITE/devices", json=test_device)
        assert device_response.status_code == 200

        # Step 3: Create a job for the site
        test_job = {
            "job_type": "config_update",
            "priority": "high",
            "config": {"test_setting": "e2e_value"},
        }

        job_response = client.post("/sites/E2E_TEST_SITE/jobs", json=test_job)
        assert job_response.status_code == 200
        job_data = job_response.json()
        job_id = job_data["job_id"]

        # Step 4: Check job status
        job_status_response = client.get(f"/jobs/{job_id}")
        assert job_status_response.status_code == 200

        # Step 5: Check site health
        health_response = client.get("/sites/E2E_TEST_SITE/health")
        assert health_response.status_code == 200

    def test_agent_management_workflow(self, client: TestClient) -> None:
        """Test agent management workflow: list, monitor, notify, restart."""
        # Step 1: Get all agents
        agents_response = client.get("/agents")
        assert agents_response.status_code == 200
        agents = agents_response.json()
        assert len(agents) > 0

        device_id = agents[0]["device_id"]

        # Step 2: Get specific agent details
        agent_response = client.get(f"/agents/{device_id}")
        assert agent_response.status_code == 200

        # Step 3: Send push notification
        notification = {"message": "Workflow test notification", "priority": "medium"}
        push_response = client.post(f"/agents/{device_id}/push", json=notification)
        assert push_response.status_code == 200

        # Step 4: Check device health
        health_response = client.get(f"/devices/{device_id}/health")
        assert health_response.status_code == 200

        # Step 5: Restart device
        restart_response = client.post(f"/devices/{device_id}/restart")
        assert restart_response.status_code == 200

    def test_audit_trail_workflow(self, client: TestClient) -> None:
        """Test audit trail workflow: perform actions, verify logging."""
        # Perform several actions that should generate audit events
        actions = [
            ("GET", "/health"),
            ("GET", "/sites"),
            ("GET", "/agents"),
            ("GET", "/audit/statistics"),
        ]

        for method, endpoint in actions:
            if method == "GET":
                response = client.get(endpoint)
                assert response.status_code == 200

        # Check that audit events were created
        audit_response = client.get("/audit/events")
        assert audit_response.status_code == 200
        events = audit_response.json()
        assert len(events) > 0

        # Verify audit statistics updated
        stats_response = client.get("/audit/statistics")
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert stats["total_events"] > 0


@pytest.mark.performance
@skip_live_tests
class TestSystemPerformance:
    """Performance tests for the complete HOMEPOT system."""

    def test_api_response_times(self, client: TestClient) -> None:
        """Test that API endpoints respond within acceptable time limits."""
        endpoints = [
            "/health",
            "/sites",
            "/agents",
            "/audit/events",
            "/audit/statistics",
        ]

        for endpoint in endpoints:
            start_time = time.time()
            response = client.get(endpoint)
            end_time = time.time()

            assert response.status_code == 200
            response_time = end_time - start_time
            assert response_time < 2.0  # Should respond within 2 seconds

    def test_concurrent_requests(self, client: TestClient) -> None:
        """Test system behavior under concurrent load."""
        import concurrent.futures

        def make_request():
            response = client.get("/health")
            return response.status_code == 200

        # Test 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in futures]

        # All requests should succeed
        assert all(results)

    def test_large_dataset_handling(self, client: TestClient) -> None:
        """Test system performance with large datasets."""
        # Test endpoints that might return large amounts of data
        response = client.get("/audit/events?limit=1000")
        assert response.status_code == 200

        events = response.json()
        # Should handle large result sets efficiently
        assert isinstance(events, list)


@pytest.mark.api
@skip_live_tests
class TestAPIDocumentation:
    """Test API documentation and schema validation."""

    def test_openapi_schema(self, client: TestClient) -> None:
        """Test that OpenAPI schema is available and valid."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema

        # Verify key endpoints are documented
        paths = schema["paths"]
        assert "/health" in paths
        assert "/sites" in paths
        assert "/agents" in paths
        assert "/audit/events" in paths

    def test_docs_ui(self, client: TestClient) -> None:
        """Test that Swagger UI is accessible."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower()


@skip_live_tests
def test_system_integration_health_check():
    """High-level integration test to verify system is operational."""
    import requests

    try:
        # Test if system is running and responsive
        response = requests.get(f"{TEST_BASE_URL}/health", timeout=5)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"

        print("HOMEPOT System Integration Test: PASSED")
        print(f"   System Status: {data['status']}")
        print(f"   Version: {data.get('version', 'Unknown')}")
        print(f"   Client Connected: {data.get('client_connected', 'Unknown')}")

    except requests.exceptions.RequestException as e:
        pytest.fail(f"System integration test failed: {e}")


if __name__ == "__main__":
    """Run integration tests independently."""
    print("Running HOMEPOT Four-Phase Integration Tests...")

    # Run the health check first
    test_system_integration_health_check()

    print("\nAll integration tests ready to run with pytest!")
    print("Usage: pytest tests/test_homepot_integration.py -v")
