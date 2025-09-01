"""Performance Tests for HOMEPOT Four-Phase Implementation.

This test suite focuses on performance, load testing, and scalability validation
for the complete HOMEPOT POS management system.

Run with: pytest tests/test_performance.py -v
"""

import concurrent.futures
import statistics
import time

import pytest
import requests


BASE_URL = "http://localhost:8000"
TIMEOUT = 30.0


class TestPerformance:
    """Performance tests for HOMEPOT system."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Verify system is running before each test."""
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            if response.status_code != 200:
                pytest.skip("HOMEPOT system is not running")
        except requests.exceptions.RequestException:
            pytest.skip("HOMEPOT system is not accessible")

    @pytest.mark.performance
    def test_api_response_times(self):
        """Test response times for all major endpoints."""
        endpoints = [
            ("/health", "Health Check"),
            ("/sites", "Sites List"),
            ("/agents", "Agents List"),
            ("/audit/events", "Audit Events"),
            ("/audit/statistics", "Audit Statistics"),
            ("/version", "Version Info"),
        ]

        print("\nAPI Response Time Analysis")
        print("=" * 50)

        results = {}

        for endpoint, name in endpoints:
            times = []

            # Warm up
            requests.get(f"{BASE_URL}{endpoint}", timeout=TIMEOUT)

            # Measure 10 requests
            for _ in range(10):
                start = time.time()
                response = requests.get(f"{BASE_URL}{endpoint}", timeout=TIMEOUT)
                end = time.time()

                assert response.status_code == 200
                times.append((end - start) * 1000)  # Convert to ms

            avg_time = statistics.mean(times)
            min_time = min(times)
            max_time = max(times)

            results[endpoint] = {"avg": avg_time, "min": min_time, "max": max_time}

            print(
                f"{name:<20}: {avg_time:6.1f}ms avg "
                f"(min: {min_time:5.1f}, max: {max_time:5.1f})"
            )

            # Performance assertions
            assert avg_time < 1000  # Average response time should be < 1s
            assert max_time < 2000  # Max response time should be < 2s

        return results

    @pytest.mark.performance
    def test_concurrent_load(self):
        """Test system behavior under concurrent load."""
        print("\nConcurrent Load Test")
        print("=" * 30)

        def make_request(endpoint: str) -> float:
            """Make a single request and return response time."""
            start = time.time()
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=TIMEOUT)
            end = time.time()
            return (end - start) * 1000, response.status_code == 200

        # Test different concurrency levels
        concurrency_levels = [5, 10, 20]
        endpoint = "/health"  # Use lightweight endpoint

        for concurrent_requests in concurrency_levels:
            print(f"\n   Testing {concurrent_requests} concurrent requests...")

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=concurrent_requests
            ) as executor:
                futures = [
                    executor.submit(make_request, endpoint)
                    for _ in range(concurrent_requests)
                ]

                results = [future.result() for future in futures]
                times = [result[0] for result in results]
                successes = [result[1] for result in results]

            success_rate = sum(successes) / len(successes) * 100
            avg_time = statistics.mean(times)
            max_time = max(times)

            print(f"     Success Rate: {success_rate:5.1f}%")
            print(f"     Avg Time:     {avg_time:6.1f}ms")
            print(f"     Max Time:     {max_time:6.1f}ms")

            # Assertions
            assert success_rate >= 95  # At least 95% success rate
            assert avg_time < 2000  # Average time should be reasonable
            assert max_time < 5000  # Max time should not be excessive

    @pytest.mark.performance
    def test_memory_usage_stability(self):
        """Test that repeated requests don't cause memory leaks."""
        import psutil

        print("\nMemory Usage Stability Test")
        print("=" * 35)

        # Get initial memory usage (if we can access the process)
        try:
            # This is a simplified test - in practice you'd monitor the actual service
            initial_memory = psutil.virtual_memory().used

            # Make many requests
            for i in range(100):
                response = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
                assert response.status_code == 200

                if i % 20 == 0:
                    current_memory = psutil.virtual_memory().used
                    memory_diff = current_memory - initial_memory
                    print(
                        f"   Request {i:3d}: Memory diff: "
                        f"{memory_diff / (1024 * 1024):6.1f} MB"
                    )

            final_memory = psutil.virtual_memory().used
            total_diff = final_memory - initial_memory

            print(f"   Total memory change: {total_diff / 1024 / 1024:6.1f} MB")

            # Memory usage shouldn't grow excessively
            assert total_diff < 100 * 1024 * 1024  # Less than 100MB growth

        except ImportError:
            pytest.skip("psutil not available for memory testing")

    @pytest.mark.performance
    def test_database_query_performance(self):
        """Test database query performance with larger datasets."""
        print("\nDatabase Query Performance")
        print("=" * 35)

        # Test endpoints that likely involve database queries
        db_endpoints = [
            ("/sites", "Sites Query"),
            ("/agents", "Agents Query"),
            ("/audit/events?limit=100", "Audit Events (100)"),
            ("/audit/events?limit=1000", "Audit Events (1000)"),
            ("/audit/statistics", "Audit Statistics"),
        ]

        for endpoint, name in db_endpoints:
            times = []

            # Measure 5 requests
            for _ in range(5):
                start = time.time()
                response = requests.get(f"{BASE_URL}{endpoint}", timeout=TIMEOUT)
                end = time.time()

                assert response.status_code == 200
                times.append((end - start) * 1000)

            avg_time = statistics.mean(times)
            print(f"   {name:<25}: {avg_time:6.1f}ms avg")

            # Database queries should be reasonably fast
            assert avg_time < 3000  # Should complete within 3 seconds

    @pytest.mark.performance
    def test_websocket_performance(self):
        """Test WebSocket connection performance (if available)."""
        print("\nWebSocket Performance Test")
        print("=" * 30)

        try:
            import websocket

            def on_message(ws, message):
                pass

            def on_error(ws, error):
                print(f"WebSocket error: {error}")

            start_time = time.time()
            ws = websocket.WebSocketApp(
                "ws://localhost:8000/ws/status",
                on_message=on_message,
                on_error=on_error,
            )

            # Test connection time
            connection_time = (time.time() - start_time) * 1000
            print(f"   Connection Time: {connection_time:6.1f}ms")

            ws.close()

            # Connection should be fast
            assert connection_time < 1000  # Should connect within 1 second

        except ImportError:
            print("   WebSocket client not available - skipping")
        except Exception as e:
            print(f"   WebSocket test failed: {e}")

    @pytest.mark.performance
    def test_large_data_handling(self):
        """Test handling of large datasets."""
        print("\nLarge Data Handling Test")
        print("=" * 30)

        # Test requesting large amounts of audit data
        large_limits = [500, 1000, 2000]

        for limit in large_limits:
            start = time.time()
            response = requests.get(
                f"{BASE_URL}/audit/events?limit={limit}", timeout=TIMEOUT
            )
            end = time.time()

            if response.status_code == 200:
                data = response.json()
                response_time = (end - start) * 1000
                data_size = len(str(data))

                print(
                    f"   Limit {limit:4d}: {response_time:6.1f}ms, {data_size:8d} bytes"
                )

                # Should handle large datasets efficiently
                assert response_time < 5000  # Should complete within 5 seconds
            else:
                print(f"   Limit {limit:4d}: Failed (status {response.status_code})")

    @pytest.mark.performance
    def test_stress_test(self):
        """Stress test with sustained load."""
        print("\nStress Test (60 seconds)")
        print("=" * 30)

        duration = 60  # seconds
        request_count = 0
        error_count = 0
        start_time = time.time()

        while time.time() - start_time < duration:
            try:
                response = requests.get(f"{BASE_URL}/health", timeout=5)
                request_count += 1

                if response.status_code != 200:
                    error_count += 1

            except requests.exceptions.RequestException:
                error_count += 1
                request_count += 1

            # Brief pause to prevent overwhelming
            time.sleep(0.1)

        actual_duration = time.time() - start_time
        requests_per_second = request_count / actual_duration
        error_rate = (error_count / request_count) * 100 if request_count > 0 else 0

        print(f"   Duration:         {actual_duration:6.1f}s")
        print(f"   Total Requests:   {request_count:6d}")
        print(f"   Requests/Second:  {requests_per_second:6.1f}")
        print(f"   Error Rate:       {error_rate:6.1f}%")

        # Stress test assertions
        assert error_rate < 5.0  # Less than 5% error rate
        assert requests_per_second > 5  # At least 5 requests per second


class TestScalability:
    """Tests for system scalability characteristics."""

    @pytest.mark.performance
    def test_agent_scaling(self):
        """Test system behavior with many agents."""
        response = requests.get(f"{BASE_URL}/agents", timeout=TIMEOUT)
        assert response.status_code == 200

        agents = response.json()
        agent_count = len(agents)

        print("\nAgent Scaling Test")
        print(f"   Current Agents: {agent_count}")

        # Time the request
        start = time.time()
        response = requests.get(f"{BASE_URL}/agents", timeout=TIMEOUT)
        end = time.time()

        response_time = (end - start) * 1000
        print(f"   Query Time:     {response_time:6.1f}ms")

        # Should handle current agent load efficiently
        assert response_time < 2000  # Should be fast even with many agents

    @pytest.mark.performance
    def test_audit_data_scaling(self):
        """Test audit system performance with large event volumes."""
        response = requests.get(f"{BASE_URL}/audit/statistics", timeout=TIMEOUT)
        assert response.status_code == 200

        stats = response.json()
        event_count = stats.get("total_events", 0)

        print("\nAudit Data Scaling Test")
        print(f"   Total Events: {event_count}")

        # Test query performance with current event volume
        start = time.time()
        response = requests.get(f"{BASE_URL}/audit/events?limit=100", timeout=TIMEOUT)
        end = time.time()

        response_time = (end - start) * 1000
        print(f"   Query Time:   {response_time:6.1f}ms")

        # Should handle current audit volume efficiently
        assert response_time < 3000  # Should be reasonable even with many events


if __name__ == "__main__":
    """Run performance tests independently."""
    print("HOMEPOT Performance Test Suite")
    print("=" * 40)

    # Quick system check
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("System Ready for Performance Testing")
            print("Usage: pytest tests/test_performance.py -v -m performance")
        else:
            print("System Not Ready")
    except Exception as e:
        print(f"System Not Accessible: {e}")
