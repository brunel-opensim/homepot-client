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
import random
import sys
from datetime import datetime
from datetime import time as dt_time
from datetime import timedelta, timezone
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path.cwd() / "backend" / "src"))

# Monkey patch bcrypt to work with passlib (bcrypt >= 4.0.0 compatibility)
import bcrypt

from homepot.app.models.AnalyticsModel import (
    APIRequestLog,
    ConfigurationHistory,
    DeviceMetrics,
    DeviceStateHistory,
    ErrorLog,
    JobOutcome,
    PushNotificationLog,
    SiteOperatingSchedule,
    UserActivity,
)
from homepot.app.models.UserModel import Base as AppBase
from homepot.app.models.UserModel import User
from homepot.database import DatabaseService
from homepot.models import (
    AuditLog,
    Base,
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


def generate_historical_metrics(device_id: int, hours: int = 24) -> list[DeviceMetrics]:
    """Generate historical metrics for a device."""
    metrics = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for i in range(hours):
        timestamp = now - timedelta(hours=hours - i)

        # Simulate daily cycle (higher load during day)
        hour_of_day = timestamp.hour
        is_peak = 9 <= hour_of_day <= 17

        base_cpu = 40 if is_peak else 10
        base_mem = 60 if is_peak else 30
        base_trans = 100 if is_peak else 10

        cpu = min(100, max(0, base_cpu + random.uniform(-10, 20)))
        mem = min(100, max(0, base_mem + random.uniform(-5, 10)))
        trans_count = int(max(0, base_trans + random.uniform(-20, 50)))
        trans_vol = trans_count * random.uniform(10, 50)

        metrics.append(
            DeviceMetrics(
                device_id=device_id,
                cpu_percent=round(cpu, 1),
                memory_percent=round(mem, 1),
                disk_percent=round(random.uniform(30, 40), 1),
                network_latency_ms=round(random.uniform(5, 50), 1),
                transaction_count=trans_count,
                transaction_volume=round(trans_vol, 2),
                error_rate=round(random.uniform(0, 2), 2),
                active_connections=int(trans_count / 10),
                queue_depth=int(trans_count / 50),
                timestamp=timestamp,
                extra_metrics={"temperature_celsius": round(random.uniform(35, 55), 1)},
            )
        )
    return metrics


def generate_historical_errors(
    device_id: str, user_id: str, count: int = 5
) -> list[ErrorLog]:
    """Generate historical error logs."""
    errors = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    error_types = [
        ("api", "error", "Connection timeout", "NET001"),
        ("validation", "warning", "Invalid input format", "VAL001"),
        ("device", "critical", "Sensor malfunction", "DEV002"),
        ("auth", "error", "Token expired", "AUTH003"),
    ]

    for _ in range(count):
        cat, sev, msg, code = random.choice(error_types)
        timestamp = now - timedelta(hours=random.randint(1, 48))
        errors.append(
            ErrorLog(
                category=cat,
                severity=sev,
                error_code=code,
                error_message=msg,
                endpoint="/api/v1/mobile/sync",
                user_id=user_id,
                device_id=device_id,
                context={"retry_count": random.randint(1, 3)},
                timestamp=timestamp,
            )
        )
    return errors


def generate_historical_user_activity(
    user_id: str, count: int = 20
) -> list[UserActivity]:
    """Generate historical user activity."""
    activities = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    activity_types = ["page_view", "click", "search", "filter"]
    pages = ["/dashboard", "/devices", "/sites", "/settings"]

    for _ in range(count):
        timestamp = now - timedelta(hours=random.randint(1, 24))
        activities.append(
            UserActivity(
                user_id=user_id,
                activity_type=random.choice(activity_types),
                page_url=random.choice(pages),
                element_id=f"btn-{random.randint(1, 50)}",
                duration_ms=random.randint(500, 5000),
                session_id=f"sess-{random.randint(10000, 99999)}",
                timestamp=timestamp,
            )
        )
    return activities


async def init_database():
    """Initialize PostgreSQL database with schema and seed data."""
    print("Importing database service...")

    # Create database service (will use DATABASE__URL from .env)
    db_service = DatabaseService()

    print("Dropping existing tables...")
    async with db_service.engine.begin() as conn:
        await conn.run_sync(AppBase.metadata.drop_all)
        await conn.run_sync(Base.metadata.drop_all)

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

    # Create 2 Targeted Sites
    site1 = await get_or_create_site(
        "site-001",
        "Site 1 - Mixed OS",
        "Mixed environment site 1",
        "London, UK",
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

    sites = [site1, site2]

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
        "site1-linux-01",
        "Linux POS 1-1",
        DeviceType.POS_TERMINAL,
        site1.id,
        "10.1.1.10",
        {
            "os": "linux",
            "push_platform": "fcm",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site1-windows-02",
        "Windows POS 1-2",
        DeviceType.POS_TERMINAL,
        site1.id,
        "10.1.2.10",
        {
            "os": "windows",
            "push_platform": "wns",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site1-macos-03",
        "Apple POS 1-3",
        DeviceType.POS_TERMINAL,
        site1.id,
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
        "Web Dashboard 1-4",
        DeviceType.POS_TERMINAL,
        site1.id,
        "10.1.4.10",
        {
            "os": "web",
            "push_platform": "web_push",
            "agent_version": "1.0.0-web",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site1-iot-05",
        "IoT Sensor 1-5",
        DeviceType.IOT_SENSOR,
        site1.id,
        "10.1.5.10",
        {
            "os": "embedded",
            "push_platform": "mqtt",
            "agent_version": "1.0.0-iot",
            "version": "1.0.0",
        },
    )

    # Site 2 Devices
    print("--- Site 2 Devices ---")
    await get_or_create_device(
        "site2-linux-01",
        "Linux POS 2-1",
        DeviceType.POS_TERMINAL,
        site2.id,
        "10.2.1.10",
        {
            "os": "linux",
            "push_platform": "fcm",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site2-windows-02",
        "Windows POS 2-2",
        DeviceType.POS_TERMINAL,
        site2.id,
        "10.2.2.10",
        {
            "os": "windows",
            "push_platform": "wns",
            "agent_version": "1.0.0-sim",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site2-macos-03",
        "Apple POS 2-3",
        DeviceType.POS_TERMINAL,
        site2.id,
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
        "Web Dashboard 2-4",
        DeviceType.POS_TERMINAL,
        site2.id,
        "10.2.4.10",
        {
            "os": "web",
            "push_platform": "web_push",
            "agent_version": "1.0.0-web",
            "version": "1.0.0",
        },
    )
    await get_or_create_device(
        "site2-iot-05",
        "IoT Sensor 2-5",
        DeviceType.IOT_SENSOR,
        site2.id,
        "10.2.5.10",
        {
            "os": "embedded",
            "push_platform": "mqtt",
            "agent_version": "1.0.0-iot",
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
                    device_id=first_device.id,
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

            # Generate historical metrics
            historical_metrics = generate_historical_metrics(first_device.id)
            session.add_all(historical_metrics)

            # Generate historical errors
            historical_errors = generate_historical_errors(
                first_device.device_id, str(admin_user.id)
            )
            session.add_all(historical_errors)

            # Generate historical user activity
            historical_activity = generate_historical_user_activity(str(admin_user.id))
            session.add_all(historical_activity)

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

            session.add(
                PushNotificationLog(
                    message_id="msg-001",
                    device_id=first_device.device_id,
                    job_id=sample_job.job_id,
                    provider="fcm",
                    status="delivered",
                    latency_ms=150,
                    sent_at=datetime.now(timezone.utc).replace(tzinfo=None)
                    - timedelta(minutes=5),
                    received_at=datetime.now(timezone.utc).replace(tzinfo=None)
                    - timedelta(minutes=5)
                    + timedelta(milliseconds=150),
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
            "peak_start": dt_time(12, 0),
            "peak_end": dt_time(14, 0),
            "notes": "Regular weekday - high traffic",
        },
        {
            "day": 1,
            "open": dt_time(8, 0),
            "close": dt_time(22, 0),
            "closed": False,
            "maint": False,
            "vol": 450,
            "peak_start": dt_time(12, 0),
            "peak_end": dt_time(14, 0),
            "notes": "Regular weekday",
        },
        {
            "day": 2,
            "open": dt_time(8, 0),
            "close": dt_time(22, 0),
            "closed": False,
            "maint": True,
            "vol": 420,
            "peak_start": dt_time(12, 0),
            "peak_end": dt_time(14, 0),
            "notes": "Maintenance 2-4 AM",
        },
        {
            "day": 3,
            "open": dt_time(8, 0),
            "close": dt_time(23, 0),
            "closed": False,
            "maint": False,
            "vol": 550,
            "peak_start": dt_time(17, 0),
            "peak_end": dt_time(20, 0),
            "notes": "Late night shopping",
        },
        {
            "day": 4,
            "open": dt_time(8, 0),
            "close": dt_time(23, 30),
            "closed": False,
            "maint": False,
            "vol": 700,
            "peak_start": dt_time(16, 0),
            "peak_end": dt_time(21, 0),
            "notes": "Busiest day",
        },
        {
            "day": 5,
            "open": dt_time(9, 0),
            "close": dt_time(23, 0),
            "closed": False,
            "maint": False,
            "vol": 650,
            "peak_start": dt_time(11, 0),
            "peak_end": dt_time(16, 0),
            "notes": "Weekend traffic",
        },
        {
            "day": 6,
            "open": dt_time(10, 0),
            "close": dt_time(18, 0),
            "closed": False,
            "maint": True,
            "vol": 200,
            "peak_start": dt_time(12, 0),
            "peak_end": dt_time(14, 0),
            "notes": "Sunday reduced hours",
        },
    ]

    async with db_service.get_session() as session:
        for sched in weekly_schedule:
            result = await session.execute(
                select(SiteOperatingSchedule).where(
                    SiteOperatingSchedule.site_id == sites[0].id,
                    SiteOperatingSchedule.day_of_week == sched["day"],
                )
            )
            existing = result.scalar_one_or_none()

            if not existing:
                new_sched = SiteOperatingSchedule(
                    site_id=sites[0].id,
                    day_of_week=sched["day"],
                    open_time=sched["open"],
                    close_time=sched["close"],
                    is_closed=sched["closed"],
                    is_maintenance_window=sched["maint"],
                    expected_transaction_volume=sched["vol"],
                    peak_hours_start=sched["peak_start"],
                    peak_hours_end=sched["peak_end"],
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
