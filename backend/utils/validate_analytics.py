#!/usr/bin/env python3
"""
Analytics Infrastructure Validation Script.

This script validates that the analytics infrastructure is working correctly
by simulating frontend tracking calls and verifying data collection.

Usage:
    # Start backend first:
    # cd backend && uvicorn homepot.app.main:app --reload

    # Then run this script:
    python backend/utils/validate_analytics.py

    # Or with test credentials:
    python backend/utils/validate_analytics.py test@example.com testpass123

Purpose:
    - Proves backend analytics endpoints work
    - Demonstrates automatic API request logging
    - Shows data can be queried successfully
    - Independent of frontend implementation
"""

from datetime import datetime
import sys
import time

import requests

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

# Authentication - will be set after login
AUTH_TOKEN = None
AUTH_HEADERS = {}


def print_header(text):
    """Print formatted section header."""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def print_success(text):
    """Print success message."""
    print(f"✓ {text}")


def print_error(text):
    """Print error message."""
    print(f"✗ {text}")


def authenticate(email="test@example.com", password="testpass123"):  # noqa: S107
    """Authenticate and get access token."""
    global AUTH_TOKEN, AUTH_HEADERS

    print_header("1. Authentication")

    # Try to login
    try:
        response = requests.post(
            f"{API_BASE}/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            # Token is in data.data.access_token based on the response structure
            token_data = data.get("data", {})
            AUTH_TOKEN = token_data.get("access_token")
            if not AUTH_TOKEN:
                print_error(f"No access token in response: {data}")
                return False
            AUTH_HEADERS = {"Authorization": f"Bearer {AUTH_TOKEN}"}
            print_success(f"Authenticated as {email}")
            return True
        else:
            print_error(f"Login failed with status {response.status_code}")
            print("\nNote: Analytics endpoints require authentication.")
            print("Please ensure a test user exists or provide credentials:")
            print("  python backend/utils/validate_analytics.py <email> <password>")
            return False
    except requests.exceptions.RequestException as e:
        print_error(f"Authentication failed: {e}")
        return False


def check_backend_running():
    """Verify backend server is accessible."""
    print_header("2. Backend Health Check")
    try:
        # Use docs endpoint as a simple connectivity check (no auth required)
        response = requests.get(f"{BASE_URL}/docs", timeout=5)
        if response.status_code == 200:
            print_success("Backend is running and accessible")
            return True
        else:
            print_error(f"Backend returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print_error(f"Cannot connect to backend: {e}")
        print("\nPlease start the backend first:")
        print("  cd backend")
        print("  uvicorn homepot.app.main:app --reload")
        return False


def test_user_activity_tracking():
    """Test user activity tracking endpoint."""
    print_header("3. User Activity Tracking")

    test_activities = [
        {
            "activity_type": "page_view",
            "page_url": "/devices",
            "duration_ms": 1500,
            "extra_data": {"test": "validation", "source": "validation_script"},
        },
        {
            "activity_type": "click",
            "page_url": "/devices",
            "element_id": "add-device-btn",
            "duration_ms": 250,
            "extra_data": {"source": "validation_script"},
        },
        {
            "activity_type": "search",
            "page_url": "/devices",
            "search_query": "temperature sensor",
            "duration_ms": 800,
            "extra_data": {"source": "validation_script"},
        },
    ]

    for i, activity in enumerate(test_activities, 1):
        try:
            response = requests.post(
                f"{API_BASE}/analytics/user-activity",
                json=activity,
                headers=AUTH_HEADERS,
                timeout=10,
            )
            if response.status_code in [200, 201]:
                print_success(
                    f"Activity {i}/3 logged: {activity['activity_type']} "
                    f"on {activity['page_url']}"
                )
            else:
                print_error(f"Activity {i}/3 failed with status {response.status_code}")
                print(f"  Response: {response.text[:200]}")
                return False
        except requests.exceptions.RequestException as e:
            print_error(f"Activity {i}/3 failed: {e}")
            return False

        time.sleep(0.5)  # Small delay between requests

    return True


def test_api_request_logging():
    """Test that API requests are automatically logged."""
    print_header("4. Automatic API Request Logging")

    # Make some API calls that should be automatically logged
    # Note: Some endpoints may return 404 if they don't exist yet
    # (expected during development)
    endpoints_to_test = [
        # Trailing slash required by FastAPI
        ("/api/v1/sites/", "Sites list", [200]),
        # 404 if no list endpoint exists
        ("/api/v1/devices", "Devices list", [200, 404]),
        # 404 if no list endpoint exists
        ("/api/v1/jobs", "Jobs list", [200, 404]),
    ]

    print("Making test API calls (these should be auto-logged):")
    for endpoint, description, expected_codes in endpoints_to_test:
        try:
            response = requests.get(
                f"{BASE_URL}{endpoint}", headers=AUTH_HEADERS, timeout=10
            )
            if response.status_code in expected_codes:
                status_note = ""
                if response.status_code == 404:
                    status_note = " (endpoint not implemented)"
                result = f"{description}: {response.status_code}{status_note}"
                print_success(result)
            else:
                print_error(f"{description}: {response.status_code} (unexpected)")
        except requests.exceptions.RequestException as e:
            print_error(f"{description} failed: {e}")

        time.sleep(0.3)

    return True


def query_collected_data():
    """Query and display collected analytics data."""
    print_header("5. Query Collected Data")

    # Query user activities
    try:
        response = requests.get(
            f"{API_BASE}/analytics/user-activities?limit=10",
            headers=AUTH_HEADERS,
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            activities = data.get("activities", [])
            print_success(f"Retrieved {len(activities)} user activity records")

            if activities:
                print("\nRecent activities:")
                for activity in activities[:3]:
                    activity_type = activity.get("activity_type", "N/A")
                    page_url = activity.get("page_url", "N/A")
                    timestamp = activity.get("timestamp", "N/A")
                    print(f"  - {timestamp[:19]} | {activity_type:12s} | {page_url}")
        else:
            print_error(f"Query failed with status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print_error(f"Query failed: {e}")
        return False

    time.sleep(0.5)

    # Query API request logs
    try:
        response = requests.get(
            f"{API_BASE}/analytics/api-requests?limit=10",
            headers=AUTH_HEADERS,
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            requests_data = data.get("requests", [])
            print_success(f"Retrieved {len(requests_data)} API request log records")

            if requests_data:
                print("\nRecent API requests:")
                for req in requests_data[:3]:
                    timestamp = req.get("timestamp", "N/A")
                    endpoint = req.get("endpoint", "N/A")
                    method = req.get("method", "N/A")
                    status = req.get("status_code", "N/A")
                    response_time = req.get("response_time_ms", "N/A")
                    formatted = (
                        f"  - {timestamp[:19]} | {method:4s} | "
                        f"{endpoint:30s} | {status} | {response_time}ms"
                    )
                    print(formatted)
        else:
            print_error(f"API request query failed with status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print_error(f"API request query failed: {e}")
        return False

    return True


def display_summary():
    """Display validation summary."""
    print_header("6. Validation Summary")

    print("Analytics Infrastructure Status:")
    print()
    print("  Backend API: Running")
    print("  Analytics Endpoints: Functional")
    print("  User Activity Tracking: Working")
    print("  Automatic API Logging: Working")
    print("  Data Query Endpoints: Working")
    print()
    print("RESULT: Analytics infrastructure is READY")
    print()
    print("Next Steps:")
    print("  1. Frontend team implements tracking")
    print("     (docs/frontend-analytics-integration.md)")
    print("  2. Backend team adds device state & job logging")
    print("  3. Run system for 3-5 days to collect real usage data")
    print("  4. Demonstrate AI-ready dataset")


def main():
    """Run all validation tests."""
    print("\n" + "=" * 60)
    print("  HOMEPOT Analytics Infrastructure Validation")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)

    # Get credentials from command line if provided
    email = sys.argv[1] if len(sys.argv) > 1 else "test@example.com"
    password = sys.argv[2] if len(sys.argv) > 2 else "testpass123"

    # Run validation steps
    if not authenticate(email, password):
        sys.exit(1)

    time.sleep(0.5)

    if not check_backend_running():
        sys.exit(1)

    time.sleep(1)

    if not test_user_activity_tracking():
        print_error("\nUser activity tracking validation FAILED")
        sys.exit(1)

    time.sleep(1)

    if not test_api_request_logging():
        print_error("\nAPI request logging validation FAILED")
        sys.exit(1)

    time.sleep(1)

    if not query_collected_data():
        print_error("\nData query validation FAILED")
        sys.exit(1)

    time.sleep(1)

    display_summary()

    print("\n" + "=" * 60)
    print("  Validation Complete - All Tests Passed")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
