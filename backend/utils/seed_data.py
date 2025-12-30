#!/usr/bin/env python3
"""
Script to seed the database with initial sites, devices, and sample data.

This script creates:
1. Database schema (if not exists)
2. Analytics tables
3. Users (Analytics Test, Simulation)
4. Demo sites (Standard + OS-specific)
5. Demo devices (Standard + OS-specific)
6. Sample data for jobs, health checks, audit logs, and analytics
7. Full weekly operating schedules

Usage:
    python backend/utils/seed_data.py
"""

import asyncio
import sys
from datetime import datetime
from datetime import time as dt_time
from datetime import timedelta, timezone
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path.cwd() / "backend" / "src"))

# Monkey patch bcrypt to work with passlib (bcrypt >= 4.0.0 compatibility)
import bcrypt

from homepot.app.models.UserModel import Base as AppBase
from homepot.app.models.UserModel import User
from homepot.database import DatabaseService
from homepot.models import (
    AuditLog,
    Device,
    DeviceType,
    HealthCheck,
    Job,
    JobPriority,
    JobStatus,
)

if not hasattr(bcrypt, "__about__"):

    class About:
        """Monkey patch for bcrypt version."""

        __version__ = bcrypt.__version__

    bcrypt.__about__ = About()

from passlib.context import CryptContext
from sqlalchemy import select


async def init_database():
    """Initialize PostgreSQL database with schema and seed data."""
    print("Importing database service...")

    # Create database service (will use DATABASE__URL from .env)
    db_service = DatabaseService()

    print("Creating database schema...")
    await db_service.initialize()

    # Create analytics tables (uses same Base as User models)
    print("Creating analytics tables...")
    async with db_service.engine.begin() as conn:
        await conn.run_sync(AppBase.metadata.create_all)

    print("Database schema created")

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    now = datetime.now(timezone.utc).replace(
        tzinfo=None
    )  # Database uses naive datetime

    # --- USERS ---
    print("\n=== Creating Users ===")
    async with db_service.get_session() as session:
        # 1. Admin User (matching DB credentials for simplicity)
        result = await session.execute(
            select(User).where(User.username == "homepot_user")
        )
        if not result.scalar_one_or_none():
            admin_user = User(
                email="admin@homepot.com",
                username="homepot_user",
                hashed_password=pwd_context.hash("homepot_dev_password"),
                is_admin=True,
                created_at=now,
                updated_at=now,
            )
            session.add(admin_user)
            print("Created user: homepot_user")
        else:
            print("User homepot_user already exists")
            # Fetch for later use
            admin_user = (
                await session.execute(
                    select(User).where(User.username == "homepot_user")
                )
            ).scalar_one()

        await session.commit()

    # --- SITES ---
    print("\n=== Creating Sites ===")

    async def get_or_create_site(
        site_id, name, description, location, latitude=None, longitude=None
    ):
        existing = await db_service.get_site_by_site_id(site_id)
        if existing:
            # print(f"Site {site_id} already exists")
            return existing

        site = await db_service.create_site(
            site_id=site_id,
            name=name,
            description=description,
            location=location,
            latitude=latitude,
            longitude=longitude,
        )
        print(f"Created site: {site.name} ({site_id})")
        return site

    # Create 4 Targeted Sites
    site1 = await get_or_create_site(
        "site-001",
        "Site 1 - Mixed OS",
        "Mixed environment site 1",
        "New York, USA",
        40.7128,
        -74.0060,
    )
    site2 = await get_or_create_site(
        "site-002",
        "Site 2 - Mixed OS",
        "Mixed environment site 2",
        "London, UK",
        51.5074,
        -0.1278,
    )
    site3 = await get_or_create_site(
        "site-003",
        "Site 3 - Mixed OS",
        "Mixed environment site 3",
        "Tokyo, Japan",
        35.6762,
        139.6503,
    )
    site4 = await get_or_create_site(
        "site-004",
        "Site 4 - Mixed OS",
        "Mixed environment site 4",
        "Sydney, Australia",
        -33.8688,
        151.2093,
    )

    sites = [site1, site2, site3, site4]

    # --- DEVICES ---
    print("\n=== Creating Devices ===")

    async def get_or_create_device(
        device_id, name, device_type, site_id, ip_address, config
    ):
        existing = await db_service.get_device_by_device_id(device_id)
        if existing:
            return existing

        device = await db_service.create_device(
            device_id=device_id,
            name=name,
            device_type=device_type,
            site_id=site_id,
            ip_address=ip_address,
            config=config,
        )
        print(f"Created device: {device.name} ({device_id})")
        return device

    # Site 1 Devices
    print("--- Site 1 Devices ---")
    await get_or_create_device(
        "site1-fcm-01",
        "Android/Linux POS 1-1",
        DeviceType.POS_TERMINAL,
        site1.site_id,
        "10.1.1.10",
        {
            "os": "linux",
            "push_platform": "fcm",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site1-wns-02",
        "Windows POS 1-2",
        DeviceType.POS_TERMINAL,
        site1.site_id,
        "10.1.2.10",
        {
            "os": "windows",
            "push_platform": "wns",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site1-apns-03",
        "Apple POS 1-3",
        DeviceType.POS_TERMINAL,
        site1.site_id,
        "10.1.3.10",
        {
            "os": "macos",
            "push_platform": "apns",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site1-web-04",
        "Web Client 1-4",
        "web_client",
        site1.site_id,
        "10.1.4.10",
        {
            "os": "web",
            "push_platform": "web_push",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site1-mqtt-05",
        "IoT Sensor 1-5",
        DeviceType.IOT_SENSOR,
        site1.site_id,
        "10.1.5.10",
        {
            "os": "rtos",
            "push_platform": "mqtt",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )

    # Site 2 Devices
    print("--- Site 2 Devices ---")
    await get_or_create_device(
        "site2-fcm-01",
        "Android/Linux POS 2-1",
        DeviceType.POS_TERMINAL,
        site2.site_id,
        "10.2.1.10",
        {
            "os": "linux",
            "push_platform": "fcm",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site2-wns-02",
        "Windows POS 2-2",
        DeviceType.POS_TERMINAL,
        site2.site_id,
        "10.2.2.10",
        {
            "os": "windows",
            "push_platform": "wns",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site2-apns-03",
        "Apple POS 2-3",
        DeviceType.POS_TERMINAL,
        site2.site_id,
        "10.2.3.10",
        {
            "os": "macos",
            "push_platform": "apns",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site2-web-04",
        "Web Client 2-4",
        "web_client",
        site2.site_id,
        "10.2.4.10",
        {
            "os": "web",
            "push_platform": "web_push",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site2-mqtt-05",
        "IoT Sensor 2-5",
        DeviceType.IOT_SENSOR,
        site2.site_id,
        "10.2.5.10",
        {
            "os": "rtos",
            "push_platform": "mqtt",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )

    # Site 3 Devices
    print("--- Site 3 Devices ---")
    await get_or_create_device(
        "site3-fcm-01",
        "Android/Linux POS 3-1",
        DeviceType.POS_TERMINAL,
        site3.site_id,
        "10.3.1.10",
        {
            "os": "linux",
            "push_platform": "fcm",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site3-wns-02",
        "Windows POS 3-2",
        DeviceType.POS_TERMINAL,
        site3.site_id,
        "10.3.2.10",
        {
            "os": "windows",
            "push_platform": "wns",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site3-apns-03",
        "Apple POS 3-3",
        DeviceType.POS_TERMINAL,
        site3.site_id,
        "10.3.3.10",
        {
            "os": "macos",
            "push_platform": "apns",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site3-web-04",
        "Web Client 3-4",
        "web_client",
        site3.site_id,
        "10.3.4.10",
        {
            "os": "web",
            "push_platform": "web_push",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site3-mqtt-05",
        "IoT Sensor 3-5",
        DeviceType.IOT_SENSOR,
        site3.site_id,
        "10.3.5.10",
        {
            "os": "rtos",
            "push_platform": "mqtt",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )

    # Site 4 Devices
    print("--- Site 4 Devices ---")
    await get_or_create_device(
        "site4-fcm-01",
        "Android/Linux POS 4-1",
        DeviceType.POS_TERMINAL,
        site4.site_id,
        "10.4.1.10",
        {
            "os": "linux",
            "push_platform": "fcm",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site4-wns-02",
        "Windows POS 4-2",
        DeviceType.POS_TERMINAL,
        site4.site_id,
        "10.4.2.10",
        {
            "os": "windows",
            "push_platform": "wns",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site4-apns-03",
        "Apple POS 4-3",
        DeviceType.POS_TERMINAL,
        site4.site_id,
        "10.4.3.10",
        {
            "os": "macos",
            "push_platform": "apns",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site4-web-04",
        "Web Client 4-4",
        "web_client",
        site4.site_id,
        "10.4.4.10",
        {
            "os": "web",
            "push_platform": "web_push",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site4-mqtt-05",
        "IoT Sensor 4-5",
        DeviceType.IOT_SENSOR,
        site4.site_id,
        "10.4.5.10",
        {
            "os": "rtos",
            "push_platform": "mqtt",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )

    # --- SAMPLE DATA ---
    print("\n=== Creating Sample Data ===")
    async with db_service.get_session() as session:
        # Get first device
        result = await session.execute(select(Device).limit(1))
        first_device = result.scalar_one()

        # Sample Job
        result = await session.execute(
            select(Job).where(Job.job_id == "job-sample-001")
        )
        if not result.scalar_one_or_none():
            sample_job = Job(
                job_id="job-sample-001",
                action="Update POS payment config",
                description="Sample job for schema validation",
                priority=JobPriority.NORMAL,
                status=JobStatus.COMPLETED,
                site_id=sites[0].id,
                device_id=first_device.id,
                payload={"config_version": "1.0.0"},
                created_by=admin_user.id,
                completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            session.add(sample_job)
            await session.commit()
            await session.refresh(sample_job)
            print("Created sample job")

            # Sample Health Check
            sample_health = HealthCheck(
                id=1,
                device_id=first_device.id,
                is_healthy=True,
                response_time_ms=45,
                status_code=200,
                endpoint="/health",
                timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            session.add(sample_health)

            # Sample Audit Log
            sample_audit = AuditLog(
                event_type="job_created",
                description=f"Job {sample_job.job_id} created for site {sites[0].site_id}",
                user_id=admin_user.id,
                job_id=sample_job.id,
                device_id=first_device.id,
                site_id=sites[0].id,
                event_metadata={"action": "Update POS payment config"},
            )
            session.add(sample_audit)

            # Sample Analytics
            from homepot.app.models.AnalyticsModel import (
                APIRequestLog,
                ConfigurationHistory,
                DeviceMetrics,
                DeviceStateHistory,
                ErrorLog,
                JobOutcome,
                SiteOperatingSchedule,
                UserActivity,
            )

            session.add(
                APIRequestLog(
                    endpoint="/api/v1/sites/site-001/jobs",
                    method="POST",
                    status_code=200,
                    response_time_ms=125.5,
                    user_id=str(admin_user.id),
                    ip_address="192.168.1.100",
                    user_agent="HOMEPOT-Client/1.0",
                )
            )

            session.add(
                UserActivity(
                    user_id=str(admin_user.id),
                    activity_type="page_view",
                    page_url="/dashboard/sites/site-001",
                    duration_ms=3500,
                    extra_data={"action": "viewed_job_list"},
                )
            )

            session.add(
                DeviceStateHistory(
                    device_id=first_device.device_id,
                    previous_state="offline",
                    new_state="online",
                    changed_by="system",
                    reason="Device came online after reboot",
                )
            )

            session.add(
                JobOutcome(
                    job_id=sample_job.job_id,
                    job_type="config_update",
                    device_id=first_device.device_id,
                    status="success",
                    duration_ms=2340,
                    initiated_by=str(admin_user.id),
                    extra_data={"config_applied": True, "restart_required": False},
                )
            )

            session.add(
                ErrorLog(
                    category="validation",
                    severity="warning",
                    error_code="VAL001",
                    error_message="Invalid configuration parameter detected",
                    stack_trace="Traceback (most recent call last):\n  File example.py line 42",
                    endpoint="/api/v1/config/validate",
                    user_id=str(admin_user.id),
                    context={"param": "invalid_value", "expected": "integer"},
                )
            )

            session.add(
                DeviceMetrics(
                    device_id=first_device.device_id,
                    cpu_percent=45.2,
                    memory_percent=62.8,
                    disk_percent=38.5,
                    network_latency_ms=12.3,
                    transaction_count=156,
                    transaction_volume=2847.50,
                    error_rate=0.64,
                    active_connections=8,
                    queue_depth=2,
                    extra_metrics={"temperature_celsius": 42, "uptime_hours": 168},
                )
            )

            session.add(
                ConfigurationHistory(
                    entity_type="device",
                    entity_id=first_device.device_id,
                    parameter_name="max_connections",
                    old_value={"value": 10},
                    new_value={"value": 15},
                    changed_by=str(admin_user.id),
                    change_reason="Increased load during peak hours",
                    change_type="manual",
                    performance_before={"avg_response_time": 145, "error_rate": 1.2},
                    performance_after={"avg_response_time": 98, "error_rate": 0.3},
                    was_successful=True,
                    was_rolled_back=False,
                    timestamp=datetime.now(timezone.utc).replace(tzinfo=None)
                    - timedelta(hours=2),
                )
            )

            await session.commit()
            print("Created sample analytics data")

    # --- SCHEDULES ---
    print("\n=== Creating Operating Schedules ===")

    weekly_schedule = [
        {
            "day": 0,
            "open": dt_time(8, 0),
            "close": dt_time(22, 0),
            "closed": False,
            "maint": False,
            "vol": 500,
            "notes": "Regular weekday",
        },
        {
            "day": 1,
            "open": dt_time(8, 0),
            "close": dt_time(22, 0),
            "closed": False,
            "maint": False,
            "vol": 450,
            "notes": "Regular weekday",
        },
        {
            "day": 2,
            "open": dt_time(8, 0),
            "close": dt_time(22, 0),
            "closed": False,
            "maint": True,
            "vol": 420,
            "notes": "Maintenance 2-4 AM",
        },
        {
            "day": 3,
            "open": dt_time(8, 0),
            "close": dt_time(23, 0),
            "closed": False,
            "maint": False,
            "vol": 550,
            "notes": "Late night shopping",
        },
        {
            "day": 4,
            "open": dt_time(8, 0),
            "close": dt_time(23, 30),
            "closed": False,
            "maint": False,
            "vol": 700,
            "notes": "Busiest day",
        },
        {
            "day": 5,
            "open": dt_time(9, 0),
            "close": dt_time(23, 0),
            "closed": False,
            "maint": False,
            "vol": 650,
            "notes": "Weekend traffic",
        },
        {
            "day": 6,
            "open": dt_time(10, 0),
            "close": dt_time(18, 0),
            "closed": False,
            "maint": True,
            "vol": 200,
            "notes": "Sunday reduced hours",
        },
    ]

    async with db_service.get_session() as session:
        for sched in weekly_schedule:
            result = await session.execute(
                select(SiteOperatingSchedule).where(
                    SiteOperatingSchedule.site_id == sites[0].site_id,
                    SiteOperatingSchedule.day_of_week == sched["day"],
                )
            )
            existing = result.scalar_one_or_none()

            if not existing:
                new_sched = SiteOperatingSchedule(
                    site_id=sites[0].site_id,
                    day_of_week=sched["day"],
                    open_time=sched["open"],
                    close_time=sched["close"],
                    is_closed=sched["closed"],
                    is_maintenance_window=sched["maint"],
                    expected_transaction_volume=sched["vol"],
                    notes=sched["notes"],
                )
                session.add(new_sched)

        await session.commit()
        print(f"Created weekly operating schedules for {sites[0].site_id}")

    print("\n" + "=" * 50)
    print("DATABASE SEEDING COMPLETE")
    print("=" * 50)

    await db_service.close()


if __name__ == "__main__":
    asyncio.run(init_database())
