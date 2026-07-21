"""Comprehensive Integration Tests for HOMEPOT Four-Phase Implementation.

This test suite validates the complete HOMEPOT POS management system including:
- Phase 1: Core Infrastructure & Database
- Phase 2: Enhanced API Endpoints & WebSocket Dashboard
- Phase 3: Realistic Agent Simulation & Health Checks
- Phase 4: Comprehensive Audit Logging & System Metrics

The tests use httpx for async HTTP testing and cover the full API surface.
"""

import asyncio
from datetime import datetime, timezone
import os
import tempfile
import time
from typing import Any, AsyncGenerator, Generator
import uuid

from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from homepot.app.auth_utils import create_access_token, hash_password
from homepot.config import reload_settings
import homepot.database
from homepot.models import Base, User

TEST_USER_EMAIL = "integration@test.local"


def generate_random_id(prefix: str) -> str:
    """Generate a random ID with the given prefix."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
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

    new_engine = create_engine(
        db_url, connect_args={"check_same_thread": False}, pool_pre_ping=True
    )
    Base.metadata.create_all(bind=new_engine)
    new_session_local = sessionmaker(bind=new_engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(homepot.database, "sync_engine", new_engine)
    monkeypatch.setattr(homepot.database, "SessionLocal", new_session_local)

    # Seed the test user
    session = new_session_local()
    try:
        existing = session.query(User).filter(User.email == TEST_USER_EMAIL).first()
        if not existing:
            user = User(
                email=TEST_USER_EMAIL,
                username="integration",
                hashed_password=hash_password("testpassword123"),
                is_admin=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(user)
            session.commit()
    finally:
        session.close()

    yield

    new_engine.dispose()
    if os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


def auth_headers() -> dict:
    """Return Authorization headers with a valid Bearer token for the test user."""
    token = create_access_token({"sub": TEST_USER_EMAIL})
    return {"Authorization": f"Bearer {token}"}


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
        from homepot.main import app

        return TestClient(app)

    @pytest.fixture(scope="class")
    async def async_client(self) -> AsyncGenerator[httpx.AsyncClient, None]:
        """Create an async HTTP client for testing."""
        async with httpx.AsyncClient(
            base_url=TEST_BASE_URL, timeout=TEST_TIMEOUT
        ) as client:
            yield client


@pytest.mark.integration
class TestPhase1CoreInfrastructure:
    """Test Phase 1: Core Infrastructure & Database functionality."""

    def test_health_endpoint(self, client: TestClient) -> None:
        """Test system health check endpoint."""
        response = client.get("/api/v1/health/health")

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
class TestPhase2APIEndpoints:
    """Test Phase 2: Enhanced API Endpoints & WebSocket Dashboard."""

    _headers: dict = {}

    def test_list_sites(self, client: TestClient) -> None:
        """Test listing all POS sites."""
        TestPhase2APIEndpoints._headers = auth_headers()
        response = client.get("/api/v1/sites", headers=TestPhase2APIEndpoints._headers)

        assert response.status_code == 200
        data = response.json()
        assert "sites" in data
        sites = data["sites"]
        assert isinstance(sites, list)

        if sites:
            site = sites[0]
            assert "site_id" in site
            assert "name" in site
            assert "created_at" in site

    def test_get_specific_site(self, client: TestClient) -> None:
        """Test getting specific site information."""
        h = TestPhase2APIEndpoints._headers
        sites_response = client.get("/api/v1/sites", headers=h)
        data = sites_response.json()
        sites = data.get("sites", [])

        if sites:
            site_id = sites[0]["site_id"]
            response = client.get(f"/api/v1/sites/{site_id}", headers=h)

            assert response.status_code == 200
            site = response.json()
            assert site["site_id"] == site_id
            assert "name" in site
            assert "created_at" in site

    def test_create_site(self, client: TestClient) -> None:
        """Test creating a new POS site."""
        h = TestPhase2APIEndpoints._headers
        site_id = generate_random_id("TEST_SITE")
        test_site = {
            "site_id": site_id,
            "name": "Test Site",
            "location": "Test Location",
            "type": "test",
        }

        try:
            response = client.post("/api/v1/sites", json=test_site, headers=h)

            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "site_id" in data
            assert data["site_id"] == site_id
        finally:
            if response.status_code == 200:
                client.delete(f"/api/v1/sites/{site_id}", headers=h)

    def test_site_health(self, client: TestClient) -> None:
        """Test site health monitoring."""
        h = TestPhase2APIEndpoints._headers
        sites_response = client.get("/api/v1/sites", headers=h)
        sites = sites_response.json().get("sites", [])

        if sites:
            site_id = sites[0]["site_id"]
            response = client.get(f"/api/v1/health/sites/{site_id}/health", headers=h)

            assert response.status_code == 200
            health = response.json()
            assert "site_id" in health
            assert "health_percentage" in health
            assert health["site_id"] == site_id

    def test_device_registration(self, client: TestClient) -> None:
        """Test device registration at a site."""
        h = TestPhase2APIEndpoints._headers
        sites_response = client.get("/api/v1/sites", headers=h)
        sites = sites_response.json().get("sites", [])

        if sites:
            site_id = sites[0]["site_id"]
            device_id = generate_random_id("TEST_DEVICE")
            test_device = {
                "site_id": site_id,
                "device_id": device_id,
                "name": "Test Device 001",
                "device_type": "pos_terminal",
                "location": "Test Counter",
            }

            response = client.post(
                "/api/v1/devices/device", json=test_device, headers=h
            )

            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "device_id" in data
            assert data["device_id"] == device_id

    def test_job_creation(self, client: TestClient) -> None:
        """Test creating a job for a site."""
        h = TestPhase2APIEndpoints._headers
        sites_response = client.get("/api/v1/sites", headers=h)
        sites = sites_response.json().get("sites", [])

        if sites:
            site_id = sites[0]["site_id"]
            test_job = {
                "job_type": "config_update",
                "priority": "medium",
                "config": {"test_setting": "test_value"},
            }

            response = client.post(
                f"/api/v1/sites/{site_id}/jobs", json=test_job, headers=h
            )

            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "job_id" in data


@pytest.mark.integration
@skip_live_tests
class TestPhase3AgentSimulation:
    """Test Phase 3: Realistic Agent Simulation & Health Checks."""

    _headers: dict = {}

    def test_list_agents(self, client: TestClient) -> None:
        """Test listing all active POS agents."""
        TestPhase3AgentSimulation._headers = auth_headers()
        h = TestPhase3AgentSimulation._headers
        response = client.get("/api/v1/agents", headers=h)

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        agents = data["agents"]
        assert isinstance(agents, list)

        if agents:
            agent = agents[0]
            assert "device_id" in agent
            assert "state" in agent

    def test_get_specific_agent(self, client: TestClient) -> None:
        """Test getting specific agent information."""
        h = TestPhase3AgentSimulation._headers
        agents_response = client.get("/api/v1/agents", headers=h)
        agents = agents_response.json().get("agents", [])

        if agents:
            device_id = agents[0]["device_id"]
            response = client.get(f"/api/v1/agents/{device_id}", headers=h)

            assert response.status_code == 200
            agent = response.json()
            assert agent["device_id"] == device_id
            assert "state" in agent

    def test_agent_push_notification(self, client: TestClient) -> None:
        """Test sending push notification to agent."""
        h = TestPhase3AgentSimulation._headers
        agents_response = client.get("/api/v1/agents", headers=h)
        agents = agents_response.json().get("agents", [])

        if agents:
            device_id = agents[0]["device_id"]
            notification = {
                "message": "Test notification",
                "priority": "medium",
                "action": "test_action",
            }

            response = client.post(
                f"/api/v1/agents/{device_id}/push", json=notification, headers=h
            )

            assert response.status_code == 200
            data = response.json()
            assert "message" in data

    def test_device_health_check(self, client: TestClient) -> None:
        """Test device health check functionality."""
        h = TestPhase3AgentSimulation._headers
        agents_response = client.get("/api/v1/agents", headers=h)
        agents = agents_response.json().get("agents", [])

        if agents:
            device_id = agents[0]["device_id"]
            response = client.get(
                f"/api/v1/health/devices/{device_id}/health", headers=h
            )

            assert response.status_code == 200
            health = response.json()
            assert "device_id" in health
            assert "agent_state" in health
            assert "health" in health

    def test_device_restart(self, client: TestClient) -> None:
        """Test device restart functionality."""
        h = TestPhase3AgentSimulation._headers
        agents_response = client.get("/api/v1/agents", headers=h)
        agents = agents_response.json().get("agents", [])

        if agents:
            device_id = agents[0]["device_id"]
            response = client.post(f"/api/v1/devices/{device_id}/restart", headers=h)

            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert device_id in data["message"]


@pytest.mark.integration
@skip_live_tests
class TestPhase4AuditLogging:
    """Test Phase 4: Comprehensive Audit Logging & System Metrics."""

    _headers: dict = {}

    def test_audit_events(self, client: TestClient) -> None:
        """Test retrieving audit events."""
        TestPhase4AuditLogging._headers = auth_headers()
        h = TestPhase4AuditLogging._headers
        response = client.get("/api/v1/audit/events", headers=h)

        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        events = data["events"]
        assert isinstance(events, list)

        if events:
            event = events[0]
            assert "id" in event
            assert "event_type" in event
            assert "description" in event
            assert "created_at" in event

    def test_audit_statistics(self, client: TestClient) -> None:
        """Test audit statistics endpoint."""
        h = TestPhase4AuditLogging._headers
        response = client.get("/api/v1/audit/statistics", headers=h)

        assert response.status_code == 200
        stats_response = response.json()
        assert "statistics" in stats_response
        stats = stats_response["statistics"]

        assert "total_events" in stats
        assert "events_by_type" in stats
        assert isinstance(stats["total_events"], int)

    def test_audit_event_types(self, client: TestClient) -> None:
        """Test getting available audit event types."""
        h = TestPhase4AuditLogging._headers
        response = client.get("/api/v1/audit/event-types", headers=h)

        assert response.status_code == 200
        data = response.json()
        assert "event_types" in data
        event_types = data["event_types"]
        assert isinstance(event_types, list)
        assert len(event_types) >= 20


@pytest.mark.integration
class TestEndToEndWorkflows:
    """Test complete end-to-end workflows across all phases."""

    _headers: dict = {}

    def test_complete_site_setup_workflow(self, client: TestClient) -> None:
        """Test create site, add device, create job, monitor health."""
        TestEndToEndWorkflows._headers = auth_headers()
        h = TestEndToEndWorkflows._headers
        site_id = generate_random_id("E2E_TEST_SITE")
        test_site = {
            "site_id": site_id,
            "name": "End-to-End Test Site",
            "location": "Test Location",
            "type": "test",
        }

        site_response = client.post("/api/v1/sites", json=test_site, headers=h)
        assert site_response.status_code == 200

        test_device = {
            "site_id": site_id,
            "device_id": generate_random_id("E2E_TEST_DEVICE"),
            "name": "E2E Test Device",
            "device_type": "pos_terminal",
            "location": "Test Counter",
        }

        device_response = client.post(
            "/api/v1/devices/device", json=test_device, headers=h
        )
        assert device_response.status_code == 200

        test_job = {
            "job_type": "config_update",
            "priority": "high",
            "config": {"test_setting": "e2e_value"},
        }

        job_response = client.post(
            f"/api/v1/sites/{site_id}/jobs", json=test_job, headers=h
        )
        assert job_response.status_code == 200
        job_data = job_response.json()
        job_id = job_data["job_id"]

        job_status_response = client.get(f"/jobs/{job_id}")
        assert job_status_response.status_code == 200

        health_response = client.get(
            f"/api/v1/health/sites/{site_id}/health", headers=h
        )
        assert health_response.status_code == 200

    def test_agent_management_workflow(self, client: TestClient) -> None:
        """Test agent management workflow: list, monitor, notify, restart."""
        h = TestEndToEndWorkflows._headers
        site_id = generate_random_id("AGENT_WF_SITE")
        client.post(
            "/api/v1/sites",
            json={
                "site_id": site_id,
                "name": "Agent Workflow Test Site",
                "location": "Test Location",
                "type": "test",
            },
            headers=h,
        )
        setup_device_id = generate_random_id("AGENT_WF_DEVICE")
        client.post(
            "/api/v1/devices/device",
            json={
                "site_id": site_id,
                "device_id": setup_device_id,
                "name": "Agent Workflow Test Device",
                "device_type": "pos_terminal",
                "location": "Test Counter",
            },
            headers=h,
        )

        client.post("/api/v1/agents/simulation/stop", headers=h)
        client.post("/api/v1/agents/simulation/start", headers=h)

        agents_response = client.get("/api/v1/agents", headers=h)
        assert agents_response.status_code == 200
        agents = agents_response.json().get("agents", [])
        assert len(agents) > 0

        device_id = agents[0]["device_id"]

        agent_response = client.get(f"/api/v1/agents/{device_id}", headers=h)
        assert agent_response.status_code == 200

        notification = {"message": "Workflow test notification", "priority": "medium"}
        push_response = client.post(
            f"/api/v1/agents/{device_id}/push", json=notification, headers=h
        )
        assert push_response.status_code == 200

        health_response = client.get(
            f"/api/v1/health/devices/{device_id}/health", headers=h
        )
        assert health_response.status_code == 200

        restart_response = client.post(
            f"/api/v1/devices/{device_id}/restart", headers=h
        )
        assert restart_response.status_code == 200

    def test_audit_trail_workflow(self, client: TestClient) -> None:
        """Test audit trail workflow: perform actions, verify logging."""
        h = auth_headers()
        endpoints = [
            "/api/v1/health/health",
            "/api/v1/sites",
            "/api/v1/agents",
            "/api/v1/audit/statistics",
        ]

        for endpoint in endpoints:
            response = client.get(
                endpoint, headers=h if endpoint != "/api/v1/health/health" else {}
            )
            assert response.status_code == 200

        audit_response = client.get("/api/v1/audit/events", headers=h)
        assert audit_response.status_code == 200
        events = audit_response.json().get("events", [])
        assert len(events) > 0

        stats_response = client.get("/api/v1/audit/statistics", headers=h)
        assert stats_response.status_code == 200
        stats = stats_response.json().get("statistics", {})
        assert stats.get("total_events", 0) > 0


class TestDeviceSiteFields:
    """Tests for PR 19: surface hidden device/site fields."""

    _headers: dict = {}

    def setup_method(self) -> None:
        """Set auth headers before each test."""
        if not TestDeviceSiteFields._headers:
            TestDeviceSiteFields._headers = auth_headers()

    def test_device_get_includes_last_heartbeat_at(self, client: TestClient) -> None:
        """GET /devices/device/{device_id} includes last_heartbeat_at."""
        h = TestDeviceSiteFields._headers
        devices_resp = client.get("/api/v1/devices/device", headers=h)
        assert devices_resp.status_code == 200
        devices = devices_resp.json().get("devices", [])
        if devices:
            device_id = devices[0]["device_id"]
            resp = client.get(f"/api/v1/devices/device/{device_id}", headers=h)
            assert resp.status_code == 200
            data = resp.json()
            assert "last_heartbeat_at" in data
            assert "credential_status" in data

    def test_device_list_includes_new_fields(self, client: TestClient) -> None:
        """GET /devices/device includes last_heartbeat_at and credential_status."""
        h = TestDeviceSiteFields._headers
        resp = client.get("/api/v1/devices/device", headers=h)
        assert resp.status_code == 200
        devices = resp.json().get("devices", [])
        if devices:
            d = devices[0]
            assert "last_heartbeat_at" in d
            assert "credential_status" in d

    def test_devices_by_site_includes_new_fields(self, client: TestClient) -> None:
        """GET /devices/sites/{site_id}/devices includes new fields."""
        h = TestDeviceSiteFields._headers
        sites_resp = client.get("/api/v1/sites", headers=h)
        assert sites_resp.status_code == 200
        sites = sites_resp.json().get("sites", [])
        if sites:
            site_id = sites[0]["site_id"]
            resp = client.get(f"/api/v1/devices/sites/{site_id}/devices", headers=h)
            assert resp.status_code == 200
            devices = resp.json()
            if devices:
                d = devices[0]
                assert "last_heartbeat_at" in d
                assert "credential_status" in d

    def test_site_list_includes_tenant_id(self, client: TestClient) -> None:
        """GET /sites includes tenant_id."""
        h = TestDeviceSiteFields._headers
        resp = client.get("/api/v1/sites", headers=h)
        assert resp.status_code == 200
        sites = resp.json().get("sites", [])
        if sites:
            assert "tenant_id" in sites[0]

    def test_site_get_includes_tenant_id(self, client: TestClient) -> None:
        """GET /sites/{site_id} includes tenant_id."""
        h = TestDeviceSiteFields._headers
        sites_resp = client.get("/api/v1/sites", headers=h)
        assert sites_resp.status_code == 200
        sites = sites_resp.json().get("sites", [])
        if sites:
            site_id = sites[0]["site_id"]
            resp = client.get(f"/api/v1/sites/{site_id}", headers=h)
            assert resp.status_code == 200
            assert "tenant_id" in resp.json()

    def test_device_credentials_endpoint(self, client: TestClient) -> None:
        """GET /devices/device/{device_id}/credentials returns history."""
        h = TestDeviceSiteFields._headers
        devices_resp = client.get("/api/v1/devices/device", headers=h)
        assert devices_resp.status_code == 200
        devices = devices_resp.json().get("devices", [])
        if devices:
            device_id = devices[0]["device_id"]
            resp = client.get(
                f"/api/v1/devices/device/{device_id}/credentials", headers=h
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "device_id" in data
            assert "credentials" in data
            assert isinstance(data["credentials"], list)
            if data["credentials"]:
                c = data["credentials"][0]
                assert "credential_id" in c
                assert "is_active" in c
                assert "created_at" in c
                assert "key_hash" not in c


@pytest.mark.performance
@skip_live_tests
class TestSystemPerformance:
    """Performance tests for the complete HOMEPOT system."""

    def test_api_response_times(self, client: TestClient) -> None:
        """Test that API endpoints respond within acceptable time limits."""
        h = auth_headers()
        endpoints = [
            "/api/v1/sites",
            "/api/v1/agents",
            "/api/v1/audit/events",
            "/api/v1/audit/statistics",
        ]

        for endpoint in endpoints:
            start_time = time.time()
            response = client.get(endpoint, headers=h)
            end_time = time.time()

            assert response.status_code == 200
            response_time = end_time - start_time
            assert response_time < 2.0

    def test_concurrent_requests(self, client: TestClient) -> None:
        """Test system behavior under concurrent load."""
        import concurrent.futures

        def make_request():
            response = client.get("/api/v1/health/health")
            return response.status_code == 200

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in futures]

        assert all(results)

    def test_large_dataset_handling(self, client: TestClient) -> None:
        """Test system performance with large datasets."""
        h = auth_headers()
        response = client.get("/api/v1/audit/events?limit=1000", headers=h)
        assert response.status_code == 200

        events = response.json().get("events", [])
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
        assert "/api/v1/health/health" in paths
        # Registered with a trailing slash (matches frontend's
        # `apiClient.get('/sites/')` in frontend/src/services/api.js).
        assert "/api/v1/sites/" in paths
        assert "/api/v1/agents" in paths
        assert "/api/v1/audit/events" in paths

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
        response = requests.get(f"{TEST_BASE_URL}/api/v1/health/health", timeout=5)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"

        print("HOMEPOT System Integration Test: PASSED")
        print(f"   System Status: {data['status']}")
        print(f"   Version: {data.get('version', 'Unknown')}")
        print(f"   Client Connected: {data.get('client_connected', 'Unknown')}")

    except requests.exceptions.RequestException as e:
        pytest.skip(
            f"System is not running locally for this integration network test: {e}"
        )


if __name__ == "__main__":
    """Run integration tests independently."""
    print("Running HOMEPOT Four-Phase Integration Tests...")

    # Run the health check first
    test_system_integration_health_check()

    print("\nAll integration tests ready to run with pytest!")
    print("Usage: pytest tests/test_homepot_integration.py -v")
