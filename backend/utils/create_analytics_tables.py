#!/usr/bin/env python3
"""
Database migration script to create analytics tables.

This script creates the necessary tables for the analytics infrastructure:
- api_request_logs: Automatic API request tracking
- device_state_history: Device state changes
- job_outcomes: Job execution results
- error_logs: Categorized error tracking
- user_activities: User behavior tracking (frontend)

Usage:
    python backend/utils/create_analytics_tables.py
"""

import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

# Add backend src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from homepot.app.models.AnalyticsModel import (  # noqa: E402
    APIRequestLog,
    DeviceStateHistory,
    ErrorLog,
    JobOutcome,
    UserActivity,
)
from homepot.config import get_database_url  # noqa: E402


def check_table_exists(engine, table_name: str) -> bool:
    """Check if a table exists in the database."""
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = :table_name
                );
            """
            ),
            {"table_name": table_name},
        )
        return result.scalar()


def create_analytics_tables():
    """Create all analytics tables if they don't exist."""
    print("Starting analytics table creation...")

    # Get database URL
    try:
        db_url = get_database_url()
        print(f"Database URL: {db_url.split('@')[1] if '@' in db_url else 'local'}")
    except Exception as e:
        print(f"Error getting database URL: {e}")
        sys.exit(1)

    # Create engine
    try:
        engine = create_engine(db_url)
        print("Database connection established")
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)

    # Define tables to create
    tables = [
        ("api_request_logs", APIRequestLog),
        ("device_state_history", DeviceStateHistory),
        ("job_outcomes", JobOutcome),
        ("error_logs", ErrorLog),
        ("user_activities", UserActivity),
    ]

    created_count = 0
    existing_count = 0

    # Check and create each table
    for table_name, model in tables:
        try:
            if check_table_exists(engine, table_name):
                print(f"Table '{table_name}' already exists, skipping...")
                existing_count += 1
            else:
                # Create the table
                model.__table__.create(engine)
                print(f"Created table '{table_name}'")
                created_count += 1
        except ProgrammingError as e:
            if "already exists" in str(e):
                print(f"Table '{table_name}' already exists, skipping...")
                existing_count += 1
            else:
                print(f"Error creating table '{table_name}': {e}")
                raise
        except Exception as e:
            print(f"Error creating table '{table_name}': {e}")
            raise

    # Summary
    print("\n" + "=" * 60)
    print("Analytics Table Migration Summary")
    print("=" * 60)
    print(f"- Tables created: {created_count}")
    print(f"- Tables already existed: {existing_count}")
    print(f"- Total tables: {len(tables)}")
    print("=" * 60)

    if created_count > 0:
        print("\nAnalytics tables successfully created!")
        print("- Tables are ready to collect data:")
        print("   - api_request_logs: Automatic API tracking (middleware active)")
        print("   - device_state_history: Device state changes")
        print("   - job_outcomes: Job execution results")
        print("   - error_logs: Error tracking and categorization")
        print("   - user_activities: User behavior (frontend integration)")
    else:
        print("\nAll analytics tables already exist!")

    print("\nNext steps:")
    print("   1. Start the backend server: uvicorn homepot.app.main:app --reload")
    print("   2. Make some API calls to generate data")
    print("   3. Query analytics: GET /api/v1/analytics/api-requests")
    print("   4. Run the demo script: python scripts/demo_analytics.py")

    engine.dispose()


if __name__ == "__main__":
    try:
        create_analytics_tables()
    except KeyboardInterrupt:
        print("\n\nMigration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nMigration failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
