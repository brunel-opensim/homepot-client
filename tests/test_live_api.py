"""Live API Tests for HOMEPOT Four-Phase Implementation.

This test suite validates the live HOMEPOT API endpoints by making actual HTTP requests.
It's designed to test the running system at http://localhost:8000.

Run with: pytest tests/test_live_api.py -v
"""

import time

import pytest
import requests

# Configuration
BASE_URL = "http://localhost:8000"
TIMEOUT = 10.0


class TestLiveAPI:
    """Test the live HOMEPOT API endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Verify system is running before each test."""
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            if response.status_code != 200:
                pytest.skip("HOMEPOT system is not running or not healthy")
        except requests.exceptions.RequestException:
            pytest.skip("HOMEPOT system is not accessible at http://localhost:8000")

    def test_system_health(self):
        """Test system health endpoint."""
        response = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "client_connected" in data
        assert "version" in data
        print(f"System Health: {data['status']}")

    def test_system_version(self):
        """Test version endpoint."""
        response = requests.get(f"{BASE_URL}/version", timeout=TIMEOUT)

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        print(f"System Version: {data['version']}")

    def test_list_sites(self):
        """Test listing all POS sites."""
        response = requests.get(f"{BASE_URL}/sites", timeout=TIMEOUT)

        assert response.status_code == 200
        sites = response.json()
        assert isinstance(sites, list)
        assert len(sites) >= 10  # Should have pre-configured sites

        print(f"Sites Found: {len(sites)}")
        if sites:
            print(f"   Sample Site: {sites[0]['name']} ({sites[0]['site_id']})")

    def test_get_specific_site(self):
        """Test getting specific site details."""
        # First get list of sites
        sites_response = requests.get(f"{BASE_URL}/sites", timeout=TIMEOUT)
        sites = sites_response.json()

        if sites:
            site_id = sites[0]["site_id"]
            response = requests.get(f"{BASE_URL}/sites/{site_id}", timeout=TIMEOUT)

            assert response.status_code == 200
            site = response.json()
            assert site["site_id"] == site_id
            assert "name" in site
            print(f"Site Details: {site['name']} at {site.get('location', 'Unknown')}")

    def test_list_agents(self):
        """Test listing all active POS agents."""
        response = requests.get(f"{BASE_URL}/agents", timeout=TIMEOUT)

        assert response.status_code == 200
        agents = response.json()
        assert isinstance(agents, list)
        assert len(agents) >= 15  # Should have many active agents

        print(f"Active Agents: {len(agents)}")
        if agents:
            statuses = {}
            for agent in agents:
                status = agent.get("status", "unknown")
                statuses[status] = statuses.get(status, 0) + 1
            print(f"   Agent Statuses: {statuses}")

    def test_agent_details(self):
        """Test getting specific agent details."""
        # First get list of agents
        agents_response = requests.get(f"{BASE_URL}/agents", timeout=TIMEOUT)
        agents = agents_response.json()

        if agents:
            device_id = agents[0]["device_id"]
            response = requests.get(f"{BASE_URL}/agents/{device_id}", timeout=TIMEOUT)

            assert response.status_code == 200
            agent = response.json()
            assert agent["device_id"] == device_id
            assert "status" in agent
            print(f"Agent Details: {device_id} - {agent['status']}")

    def test_audit_events(self):
        """Test audit events endpoint."""
        response = requests.get(f"{BASE_URL}/audit/events", timeout=TIMEOUT)

        assert response.status_code == 200
        events = response.json()
        assert isinstance(events, list)

        print(f"Audit Events: {len(events)} events found")
        if events:
            categories = {}
            for event in events:
                category = event.get("category", "unknown")
                categories[category] = categories.get(category, 0) + 1
            print(f"   Event Categories: {categories}")

    def test_audit_statistics(self):
        """Test audit statistics endpoint."""
        response = requests.get(f"{BASE_URL}/audit/statistics", timeout=TIMEOUT)

        assert response.status_code == 200
        stats = response.json()
        assert "total_events" in stats
        assert "events_by_category" in stats

        print("Audit Statistics:")
        print(f"   Total Events: {stats['total_events']}")
        print(f"   Categories: {list(stats['events_by_category'].keys())}")

    def test_create_test_site(self):
        """Test creating a new test site."""
        test_site = {
            "site_id": f"TEST_API_{int(time.time())}",
            "name": "API Test Site",
            "location": "Test Location",
            "type": "test",
        }

        response = requests.post(f"{BASE_URL}/sites", json=test_site, timeout=TIMEOUT)

        assert response.status_code == 200
        data = response.json()
        assert "site_id" in data
        print(f"Created Test Site: {data['site_id']}")

    def test_device_health(self):
        """Test device health checking."""
        # Get an agent first
        agents_response = requests.get(f"{BASE_URL}/agents", timeout=TIMEOUT)
        agents = agents_response.json()

        if agents:
            device_id = agents[0]["device_id"]
            response = requests.get(
                f"{BASE_URL}/devices/{device_id}/health", timeout=TIMEOUT
            )

            assert response.status_code == 200
            health = response.json()
            assert "device_id" in health
            print(f"Device Health: {device_id} - {health.get('status', 'unknown')}")

    def test_site_health(self):
        """Test site health monitoring."""
        # Get a site first
        sites_response = requests.get(f"{BASE_URL}/sites", timeout=TIMEOUT)
        sites = sites_response.json()

        if sites:
            site_id = sites[0]["site_id"]
            response = requests.get(
                f"{BASE_URL}/sites/{site_id}/health", timeout=TIMEOUT
            )

            assert response.status_code == 200
            health = response.json()
            assert "site_id" in health
            assert "health_percentage" in health
            print(f"Site Health: {site_id} - {health['health_percentage']}%")

    def test_api_documentation(self):
        """Test API documentation endpoints."""
        # Test OpenAPI schema
        response = requests.get(f"{BASE_URL}/openapi.json", timeout=TIMEOUT)
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema

        # Test Swagger UI
        response = requests.get(f"{BASE_URL}/docs", timeout=TIMEOUT)
        assert response.status_code == 200

        print("API Documentation: Available")

    def test_agent_push_notification(self):
        """Test sending push notification to agent."""
        # Get an agent first
        agents_response = requests.get(f"{BASE_URL}/agents", timeout=TIMEOUT)
        agents = agents_response.json()

        if agents:
            device_id = agents[0]["device_id"]
            notification = {
                "message": f"Test notification at {int(time.time())}",
                "priority": "low",
                "action": "test",
            }

            response = requests.post(
                f"{BASE_URL}/agents/{device_id}/push",
                json=notification,
                timeout=TIMEOUT,
            )

            assert response.status_code == 200
            print(f"Push Notification: Sent to {device_id}")


class TestSystemValidation:
    """High-level system validation tests."""

    def test_complete_system_validation(self):
        """Comprehensive validation of the four-phase system."""
        print("\nHOMEPOT Four-Phase System Validation")
        print("=" * 50)

        # Phase 1: Core Infrastructure
        print("\nPhase 1: Core Infrastructure")
        response = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        assert response.status_code == 200
        health = response.json()
        print(f"   Database & API: {health['status']}")

        # Phase 2: API Endpoints
        print("\nPhase 2: Enhanced API Endpoints")
        sites_response = requests.get(f"{BASE_URL}/sites", timeout=TIMEOUT)
        sites = sites_response.json()
        print(f"   Sites Management: {len(sites)} sites")

        # Phase 3: Agent Simulation
        print("\nPhase 3: Agent Simulation")
        agents_response = requests.get(f"{BASE_URL}/agents", timeout=TIMEOUT)
        agents = agents_response.json()
        print(f"   POS Agents: {len(agents)} active agents")

        # Phase 4: Audit Logging
        print("\nPhase 4: Audit Logging")
        audit_response = requests.get(f"{BASE_URL}/audit/statistics", timeout=TIMEOUT)
        audit_stats = audit_response.json()
        print(f"   Audit Events: {audit_stats['total_events']} events logged")

        print("\nAll Four Phases: OPERATIONAL")
        print("=" * 50)

    def test_performance_benchmark(self):
        """Basic performance benchmark."""
        endpoints = ["/health", "/sites", "/agents", "/audit/events"]

        print("\nPerformance Benchmark")
        print("-" * 30)

        for endpoint in endpoints:
            start_time = time.time()
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=TIMEOUT)
            end_time = time.time()

            assert response.status_code == 200
            response_time = (end_time - start_time) * 1000  # Convert to ms
            print(f"   {endpoint:<15}: {response_time:6.1f}ms")

            # Performance assertion
            assert response_time < 2000  # Should respond within 2 seconds


@pytest.mark.live
def test_system_readiness():
    """Quick system readiness check."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        data = response.json()

        if data.get("status") == "healthy":
            print("HOMEPOT System: READY")
            return True
        else:
            print("HOMEPOT System: NOT HEALTHY")
            return False

    except Exception as e:
        print(f"HOMEPOT System: NOT ACCESSIBLE ({e})")
        return False


if __name__ == "__main__":
    """Run live API tests independently."""
    print("HOMEPOT Live API Test Suite")
    print("=" * 40)

    # Check system readiness first
    if test_system_readiness():
        print("\nReady to run full test suite!")
        print("Usage: pytest tests/test_live_api.py -v")
    else:
        print("\nStart HOMEPOT system first:")
        print("   python -m homepot_client.main")
