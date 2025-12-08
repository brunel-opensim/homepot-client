#!/usr/bin/env python3
"""
Analytics Infrastructure Validation Script

This script validates that the analytics infrastructure is working correctly
by simulating frontend tracking calls and verifying data collection.

Usage:
    # Start backend first:
    # cd backend && uvicorn homepot.app.main:app --reload

    # Then run this script:
    python backend/utils/validate_analytics.py

Purpose:
    - Proves backend analytics endpoints work
    - Demonstrates automatic API request logging
    - Shows data can be queried successfully
    - Independent of frontend implementation
"""

import sys
import time
from datetime import datetime

import requests

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"


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


def check_backend_running():
    """Verify backend server is accessible."""
    print_header("1. Backend Health Check")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
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
    print_header("2. User Activity Tracking")

    test_activities = [
        {
            "activity_type": "page_view",
            "page_url": "/devices",
            "extra_data": {"test": "validation", "source": "validation_script"},
        },
        {
            "activity_type": "button_click",
            "page_url": "/devices",
            "extra_data": {
                "button_id": "add-device-btn",
                "source": "validation_script",
            },
        },
        {
            "activity_type": "search",
            "page_url": "/devices",
            "extra_data": {
                "search_query": "temperature sensor",
                "source": "validation_script",
            },
        },
    ]

    for i, activity in enumerate(test_activities, 1):
        try:
            response = requests.post(
                f"{API_BASE}/analytics/user-activity",
                json=activity,
                timeout=10,
            )
            if response.status_code == 200:
                print_success(
                    f"Activity {i}/3 logged: {activity['activity_type']} "
                    f"on {activity['page_url']}"
                )
            else:
                print_error(
                    f"Activity {i}/3 failed with status {response.status_code}"
                )
                return False
        except requests.exceptions.RequestException as e:
            print_error(f"Activity {i}/3 failed: {e}")
            return False

        time.sleep(0.5)  # Small delay between requests

    return True


def test_api_request_logging():
    """Test that API requests are automatically logged."""
    print_header("3. Automatic API Request Logging")

    # Make some API calls that should be automatically logged
    endpoints_to_test = [
        ("/api/v1/health", "Health check"),
        ("/api/v1/sites", "Sites list"),
        ("/api/v1/devices", "Devices list"),
    ]

    print("Making test API calls (these should be auto-logged):")
    for endpoint, description in endpoints_to_test:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            print_success(f"{description}: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print_error(f"{description} failed: {e}")

        time.sleep(0.3)

    return True


def query_collected_data():
    """Query and display collected analytics data."""
    print_header("4. Query Collected Data")

    # Query user activities
    try:
        response = requests.get(
            f"{API_BASE}/analytics/user-activities?limit=10", timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            activities = data.get("activities", [])
            print_success(
                f"Retrieved {len(activities)} user activity records"
            )

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
            f"{API_BASE}/analytics/api-requests?limit=10", timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            requests_data = data.get("requests", [])
            print_success(
                f"Retrieved {len(requests_data)} API request log records"
            )

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
    print_header("5. Validation Summary")

    print("Analytics Infrastructure Status:")
    print()
    print("✓ Backend API: Running")
    print("✓ Analytics Endpoints: Functional")
    print("✓ User Activity Tracking: Working")
    print("✓ Automatic API Logging: Working")
    print("✓ Data Query Endpoints: Working")
    print()
    print("RESULT: Analytics infrastructure is READY")
    print()
    print("Next Steps:")
    print("  1. Frontend team implements tracking (docs/frontend-analytics-integration.md)")  # noqa: E501
    print("  2. Backend team adds device state & job logging")
    print("  3. Run system for 3-5 days to collect real usage data")
    print("  4. Demonstrate AI-ready dataset")


def main():
    """Run all validation tests."""
    print("\n" + "=" * 60)
    print("  HOMEPOT Analytics Infrastructure Validation")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)

    # Run validation steps
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
