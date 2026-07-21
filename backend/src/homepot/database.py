"""Database service layer for HOMEPOT Client.

This module provides async database operations and session management
for the HOMEPOT system.
"""

from collections import defaultdict
from contextlib import asynccontextmanager
import datetime
import logging
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional
import uuid

from sqlalchemy import Result, create_engine, func, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from homepot.config import get_settings
from homepot.models import (
    AuditLog,
    Base,
    CommandStatus,
    ConnectivityState,
    Device,
    DeviceCommand,
    DeviceCredential,
    DeviceStatus,
    EnrolmentIntent,
    EnrolmentIntentStatus,
    HealthCheck,
    HealthState,
    Job,
    JobStatus,
    LifecycleEpoch,
    LifecycleState,
    Site,
    User,
)

logger = logging.getLogger(__name__)

# Import additional models to ensure they are registered with Base.metadata
# This is crucial for create_all to create tables for these models
try:
    from homepot.app.models.AnalyticsModel import (  # noqa: F401
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
except ImportError:
    logger.warning("Could not import AnalyticsModel. Tables may not be created.")


def _ensure_device_dna_columns(bind: Any) -> None:
    """Ensure new DNA and heartbeat columns exist on the devices table.

    Important: SQLAlchemy `create_all()` does not alter existing tables.
    This helper applies safe additive `ALTER TABLE` statements so existing
    deployments can pick up newly added `Device` fields without dropping data.
    """
    inspector = inspect(bind)
    if "devices" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("devices")}
    dialect = bind.dialect.name

    if dialect == "sqlite":
        ddl_map = {
            "os_details": "ALTER TABLE devices ADD COLUMN os_details VARCHAR(255)",
            "local_ip": "ALTER TABLE devices ADD COLUMN local_ip VARCHAR(45)",
            "wan_ip": "ALTER TABLE devices ADD COLUMN wan_ip VARCHAR(45)",
            "last_heartbeat_at": (
                "ALTER TABLE devices ADD COLUMN last_heartbeat_at DATETIME"
            ),
            "peripherals": "ALTER TABLE devices ADD COLUMN peripherals JSON",
        }
    elif dialect == "postgresql":
        ddl_map = {
            "os_details": "ALTER TABLE devices ADD COLUMN os_details VARCHAR(255)",
            "local_ip": "ALTER TABLE devices ADD COLUMN local_ip VARCHAR(45)",
            "wan_ip": "ALTER TABLE devices ADD COLUMN wan_ip VARCHAR(45)",
            "last_heartbeat_at": (
                "ALTER TABLE devices ADD COLUMN last_heartbeat_at "
                "TIMESTAMP WITH TIME ZONE"
            ),
            "peripherals": "ALTER TABLE devices ADD COLUMN peripherals JSON",
        }
    else:
        ddl_map = {
            "os_details": "ALTER TABLE devices ADD COLUMN os_details VARCHAR(255)",
            "local_ip": "ALTER TABLE devices ADD COLUMN local_ip VARCHAR(45)",
            "wan_ip": "ALTER TABLE devices ADD COLUMN wan_ip VARCHAR(45)",
            "last_heartbeat_at": (
                "ALTER TABLE devices ADD COLUMN last_heartbeat_at TIMESTAMP"
            ),
            "peripherals": "ALTER TABLE devices ADD COLUMN peripherals JSON",
        }

    for column_name, ddl in ddl_map.items():
        if column_name in existing_columns:
            continue
        try:
            bind.execute(text(ddl))
            logger.info("Added missing devices.%s column", column_name)
        except Exception as e:
            error_text = str(e).lower()
            duplicate_markers = (
                "duplicate column",
                "already exists",
            )
            if any(marker in error_text for marker in duplicate_markers):
                logger.info("devices.%s already exists, skipping", column_name)
                continue
            raise


class DatabaseService:
    """Async database service for HOMEPOT operations."""

    def __init__(self) -> None:
        """Initialize database service."""
        settings = get_settings()

        # Convert SQLite URL to async format
        db_url = settings.database.url
        if db_url.startswith("sqlite://"):
            db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://")
        elif db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

        engine_kwargs: Dict[str, Any] = {
            "echo": settings.database.echo_sql,
            "future": True,
        }

        # SQLite ":memory:" databases are private to the connection that
        # created them. Without pinning the async engine to a single shared
        # connection (StaticPool), each new pooled connection would see a
        # brand-new, empty in-memory database, causing intermittent
        # "no such table" errors under concurrent/successive requests.
        if db_url.startswith("sqlite+aiosqlite://") and ":memory:" in db_url:
            from sqlalchemy.pool import StaticPool

            engine_kwargs["poolclass"] = StaticPool
            engine_kwargs["connect_args"] = {"check_same_thread": False}

        self.engine = create_async_engine(db_url, **engine_kwargs)

        self.session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        self._initialized = False
        self._timescaledb_enabled = False

    async def initialize(self) -> None:
        """Initialize database schema."""
        if self._initialized:
            return

        try:
            # Create data directory if it doesn't exist (for SQLite databases)
            settings = get_settings()
            db_url = settings.database.url
            if db_url.startswith("sqlite://"):
                # Parse the database file path
                db_path = db_url.replace("sqlite:///", "")
                if db_path.startswith("./"):
                    db_path = db_path[2:]

                # Create parent directory if it doesn't exist
                db_file = Path(db_path)
                db_file.parent.mkdir(parents=True, exist_ok=True)
                logger.info(f"Ensured database directory exists: {db_file.parent}")

            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                await conn.run_sync(_ensure_device_dna_columns)

            logger.info("Database initialized successfully")

            # Initialize TimescaleDB if using PostgreSQL
            if db_url.startswith("postgresql://") or db_url.startswith(
                "postgresql+asyncpg://"
            ):
                await self._initialize_timescaledb()

            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def _initialize_timescaledb(self) -> None:
        """Initialize TimescaleDB extension and hypertables."""
        try:
            from homepot.timescale import TimescaleDBManager

            async with self.get_session() as session:
                ts_manager = TimescaleDBManager(session)

                # Check if TimescaleDB is available
                if not await ts_manager.is_timescaledb_available():
                    logger.info("TimescaleDB not available - using standard PostgreSQL")
                    return

                # Enable extension (requires superuser or database owner)
                await ts_manager.enable_extension()

                # Convert health_checks to hypertable (1 week chunks)
                success = await ts_manager.create_hypertable(
                    table_name="health_checks",
                    time_column="timestamp",
                    chunk_time_interval="1 week",
                    if_not_exists=True,
                )

                if success:
                    logger.info("TimescaleDB hypertable created: health_checks")

                    # Add compression policy (compress data older than 7 days)
                    await ts_manager.add_compression_policy(
                        hypertable="health_checks",
                        compress_after="7 days",
                        if_not_exists=True,
                    )

                    # Add retention policy (keep data for 90 days)
                    await ts_manager.add_retention_policy(
                        hypertable="health_checks",
                        retention_period="90 days",
                        if_not_exists=True,
                    )

                    self._timescaledb_enabled = True
                    logger.info("TimescaleDB initialization completed successfully")

        except Exception as e:
            logger.warning(f"TimescaleDB initialization failed: {e}")
            logger.info("Continuing with standard PostgreSQL")

    def is_timescaledb_enabled(self) -> bool:
        """Check if TimescaleDB is enabled for this database."""
        return self._timescaledb_enabled

    async def close(self) -> None:
        """Close database connections."""
        await self.engine.dispose()
        logger.info("Database connections closed")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session."""
        session = self.session_maker()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    # User operations
    async def create_user(
        self,
        username: str,
        email: str,
        hashed_password: str,
        api_key: Optional[str] = None,
        is_admin: bool = False,
    ) -> User:
        """Create a new user."""
        async with self.get_session() as session:
            user = User(
                username=username,
                email=email,
                hashed_password=hashed_password,
                api_key=api_key,
                is_admin=is_admin,
            )
            session.add(user)
            await session.flush()
            await session.refresh(user)
            return user

    async def get_user_by_api_key(self, api_key: str) -> Optional[User]:
        """Get user by API key."""
        from sqlalchemy import select

        async with self.get_session() as session:
            result = await session.execute(
                select(User).where(User.api_key == api_key, User.is_active.is_(True))
            )
            return result.scalar_one_or_none()

    # Site operations
    async def create_site(
        self,
        site_id: str,
        name: str,
        description: Optional[str] = None,
        location: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        tenant_id: Optional[int] = None,
    ) -> Site:
        """Create a new site."""
        async with self.get_session() as session:
            site = Site(
                site_id=site_id,
                name=name,
                description=description,
                location=location,
                latitude=latitude,
                longitude=longitude,
                tenant_id=tenant_id,
            )
            session.add(site)
            await session.flush()
            await session.refresh(site)
            return site

    async def get_site_by_site_id(self, site_id: str) -> Optional[Site]:
        """Get site by site_id."""
        from sqlalchemy import select

        async with self.get_session() as session:
            result = await session.execute(
                select(Site).where(Site.site_id == site_id, Site.is_active.is_(True))
            )
            return result.scalar_one_or_none()

    async def get_device_by_device_id(self, device_id: str) -> Optional[Device]:
        """Get Device by device_id."""
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload

        async with self.get_session() as session:
            result = await session.execute(
                select(Device)
                .options(joinedload(Device.site), joinedload(Device.credentials))
                .where(Device.device_id == device_id, Device.is_active.is_(True))
            )
            return result.unique().scalar_one_or_none()

    async def get_devices_by_site_id(
        self, site_id: str, include_unpaired: bool = False
    ) -> List[Device]:
        """Get all devices for a site by site_id string (e.g., 'site-123').

        Args:
            site_id: Business ID of the site (string like 'site-123')
            include_unpaired: If True, include soft-deleted 'unpaired' devices

        Returns:
            List of Device objects for the site (empty if site not found)
        """
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload

        # Verify site exists first (outside of the device query session to avoid nesting)
        site = await self.get_site_by_site_id(site_id)
        if not site:
            return []

        async with self.get_session() as session:
            # Query devices using INTEGER site.id FK
            query = (
                select(Device)
                .options(joinedload(Device.credentials))
                .where(Device.site_id == site.id)
            )

            if not include_unpaired:
                query = query.where(Device.is_active.is_(True))

            query = query.order_by(Device.created_at.desc())

            result = await session.execute(query)
            return list(result.unique().scalars().all())

    # Device operations
    async def create_device(
        self,
        device_id: str,
        name: str,
        device_type: str,
        site_id: int,
        ip_address: Optional[str] = None,
        config: Optional[dict] = None,
        api_key_hash: Optional[str] = None,
        last_seen: Optional[datetime.datetime] = None,
        is_monitored: bool = False,
        enrollment_method: Optional[str] = "pre-provisioned",
        enrollment_token: Optional[str] = None,
        os_details: Optional[str] = None,
    ) -> Device:
        """Create a new device."""
        async with self.get_session() as session:
            device = Device(
                device_id=device_id,
                name=name,
                device_type=device_type,
                site_id=site_id,
                ip_address=ip_address,
                config=config,
                status=DeviceStatus.UNKNOWN,
                lifecycle_state=LifecycleState.PENDING.value,
                api_key_hash=api_key_hash,
                last_seen=last_seen,
                is_monitored=is_monitored,
                enrollment_method=enrollment_method,
                enrollment_token=enrollment_token,
                os_details=os_details,
            )
            session.add(device)
            await session.flush()
            await session.refresh(device)
            return device

    async def update_device(
        self,
        device_id: str,
        name: Optional[str] = None,
        device_type: Optional[str] = None,
        ip_address: Optional[str] = None,
        config: Optional[dict] = None,
    ) -> Optional[Device]:
        """Update an existing device."""
        async with self.get_session() as session:
            result = await session.execute(
                select(Device).where(Device.device_id == device_id)
            )
            device = result.scalars().first()

            if not device:
                return None

            if name is not None:
                device.name = name  # type: ignore
            if device_type is not None:
                device.device_type = device_type  # type: ignore
            if ip_address is not None:
                device.ip_address = ip_address  # type: ignore
            if config is not None:
                # Merge or replace config? For now, let's assume we update keys
                # If config is None in DB, initialize it
                current_config = dict(device.config) if device.config else {}
                current_config.update(config)
                device.config = current_config  # type: ignore

            await session.commit()
            await session.refresh(device)
            return device

    async def delete_device(self, device_id: str) -> bool:
        """Unpair a device, retaining its historical data (soft delete)."""
        async with self.get_session() as session:
            result = await session.execute(
                select(Device).where(Device.device_id == device_id)
            )
            device = result.scalars().first()

            if not device:
                return False

            device.lifecycle_state = LifecycleState.UNPAIRED.value  # type: ignore[assignment]
            device.is_active = False  # type: ignore[assignment]
            device.api_key_hash = None  # type: ignore[assignment]

            # Revoke all active credentials
            cred_result = await session.execute(
                select(DeviceCredential).where(
                    DeviceCredential.device_id == device.id,
                    DeviceCredential.is_active,
                )
            )
            for cred in cred_result.scalars().all():
                cred.is_active = False  # type: ignore[assignment]
                cred.revoked_at = datetime.datetime.now(datetime.timezone.utc)  # type: ignore[assignment]

            audit_log = AuditLog(
                event_type="device_unpaired",
                description=f"Device {device_id} was unpaired and archived.",
                device_id=device.id,
                site_id=device.site_id,
            )
            session.add(audit_log)

            await session.commit()
            return True

    async def get_devices_by_site_and_segment(
        self, site_id: str, segment: Optional[str] = None
    ) -> List[Device]:
        """Get devices by site (using string identifier) and optional segment."""
        from sqlalchemy import select

        async with self.get_session() as session:
            query = (
                select(Device)
                .join(Site)
                .where(Site.site_id == site_id, Device.is_active.is_(True))
            )

            # For POS scenario: filter by device type if segment specified
            if segment == "pos-terminals":
                query = query.where(Device.device_type == "pos_terminal")

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_devices_by_site_and_segment_paginated(
        self,
        site_id: str,
        segment: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Device]:
        """Get devices by site and segment with pagination for scalability."""
        from sqlalchemy import select

        async with self.get_session() as session:
            query = (
                select(Device)
                .join(Site)
                .where(Site.site_id == site_id, Device.is_active.is_(True))
            )

            # For POS scenario: filter by device type if segment specified
            if segment == "pos-terminals":
                query = query.where(Device.device_type == "pos_terminal")

            # Add ordering for consistent pagination
            query = query.order_by(Device.id).limit(limit).offset(offset)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def update_device_status(self, device_id: str, status: DeviceStatus) -> bool:
        """Update device status."""
        from sqlalchemy import update

        async with self.get_session() as session:
            result: Result[Any] = await session.execute(
                update(Device)
                .where(Device.device_id == device_id)
                .values(status=status)
            )
            row_count: int = getattr(result, "rowcount", 0)
            return row_count > 0

    # Job operations
    async def create_job(
        self,
        job_id: str,
        action: str,
        site_id: int,
        created_by: int,
        description: Optional[str] = None,
        device_id: Optional[int] = None,
        segment: Optional[str] = None,
        payload: Optional[dict] = None,
        config_url: Optional[str] = None,
        config_version: Optional[str] = None,
        ttl_seconds: int = 300,
        collapse_key: Optional[str] = None,
        priority: str = "normal",
    ) -> Job:
        """Create a new job."""
        async with self.get_session() as session:
            job = Job(
                job_id=job_id,
                action=action,
                description=description,
                site_id=site_id,
                device_id=device_id,
                segment=segment,
                payload=payload,
                config_url=config_url,
                config_version=config_version,
                ttl_seconds=ttl_seconds,
                collapse_key=collapse_key,
                priority=priority,
                created_by=created_by,
                status=JobStatus.PENDING,
            )
            session.add(job)
            await session.flush()
            await session.refresh(job)
            return job

    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        result: Optional[dict] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update job status and result."""
        from datetime import datetime

        from sqlalchemy import update

        async with self.get_session() as session:
            update_data = {"status": status, "updated_at": datetime.utcnow()}

            if status == JobStatus.COMPLETED and result is not None:
                update_data["result"] = result
                update_data["completed_at"] = datetime.utcnow()
            elif status == JobStatus.FAILED and error_message is not None:
                update_data["error_message"] = error_message
                update_data["completed_at"] = datetime.utcnow()
            elif status == JobStatus.SENT:
                update_data["started_at"] = datetime.utcnow()

            exec_result: Result[Any] = await session.execute(
                update(Job).where(Job.job_id == job_id).values(**update_data)
            )
            row_count: int = getattr(exec_result, "rowcount", 0)
            return row_count > 0

    async def get_job_by_id(self, job_id: str) -> Optional[Job]:
        """Get job by job_id with site relationship loaded."""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        async with self.get_session() as session:
            result = await session.execute(
                select(Job).options(selectinload(Job.site)).where(Job.job_id == job_id)
            )
            return result.scalar_one_or_none()

    async def get_pending_jobs(self, limit: int = 10) -> List[Job]:
        """Get pending jobs for processing."""
        from sqlalchemy import select

        async with self.get_session() as session:
            result = await session.execute(
                select(Job)
                .where(Job.status == JobStatus.PENDING)
                .order_by(Job.priority.desc(), Job.created_at.asc())
                .limit(limit)
            )
            return list(result.scalars().all())

    # Device Command operations
    async def create_device_command(
        self,
        device_id: int,
        command_type: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> DeviceCommand:
        """Create a new device command."""
        import uuid

        async with self.get_session() as session:
            command = DeviceCommand(
                command_id=str(uuid.uuid4()),
                device_id=device_id,
                command_type=command_type,
                payload=payload,
                status=CommandStatus.PENDING,
            )
            session.add(command)
            await session.commit()
            await session.refresh(command)
            return command

    async def get_pending_commands_for_device(
        self, device_id: int
    ) -> List[DeviceCommand]:
        """Get pending commands for a specific device."""
        from sqlalchemy import select

        async with self.get_session() as session:
            result = await session.execute(
                select(DeviceCommand)
                .where(
                    DeviceCommand.device_id == device_id,
                    DeviceCommand.status == CommandStatus.PENDING,
                )
                .order_by(DeviceCommand.created_at.asc())
            )
            return list(result.scalars().all())

    async def update_command_status(
        self,
        command_id: str,
        status: CommandStatus,
        result: Optional[Dict[str, Any]] = None,
    ) -> Optional[DeviceCommand]:
        """Update command status."""
        from datetime import datetime, timezone

        from sqlalchemy import select

        async with self.get_session() as session:
            # Fetch first to ensure existence and get object
            stmt = select(DeviceCommand).where(DeviceCommand.command_id == command_id)
            exec_result = await session.execute(stmt)
            command = exec_result.scalar_one_or_none()

            if command:
                command.status = status  # type: ignore
                if result:
                    command.result = result  # type: ignore
                if status in (CommandStatus.COMPLETED, CommandStatus.FAILED):
                    command.executed_at = datetime.now(timezone.utc)  # type: ignore

                await session.commit()
                await session.refresh(command)
                return command
            return None

    async def get_commands_for_device(
        self, device_id: int, limit: int = 100, offset: int = 0
    ) -> List[DeviceCommand]:
        """Get all commands for a device, sorted by created_at descending."""
        async with self.get_session() as session:
            result = await session.execute(
                select(DeviceCommand)
                .where(DeviceCommand.device_id == device_id)
                .order_by(DeviceCommand.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all())

    async def expire_stale_commands(self, ttl_seconds: int = 300) -> int:
        """Mark PENDING and SENT commands older than ttl_seconds as EXPIRED.

        Returns the number of commands expired.
        """
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            seconds=ttl_seconds
        )
        async with self.get_session() as session:
            result = await session.execute(
                select(DeviceCommand).where(
                    DeviceCommand.status.in_(
                        [CommandStatus.PENDING, CommandStatus.SENT]
                    ),
                    DeviceCommand.created_at < cutoff,
                )
            )
            commands = list(result.scalars().all())
            for cmd in commands:
                cmd.status = CommandStatus.EXPIRED  # type: ignore[assignment]
            await session.commit()
            return len(commands)

    # Health check operations
    async def create_health_check(
        self,
        device_id: Optional[int] = None,
        device_name: Optional[str] = None,
        is_healthy: bool = True,
        response_time_ms: int = 0,
        status_code: int = 200,
        endpoint: str = "/health",
        response_data: Optional[Dict[str, Any]] = None,
    ) -> HealthCheck:
        """Create a new health check record.

        Args:
            device_id: Database ID of the device (optional)
            device_name: Device name/device_id string for lookup (optional)
            is_healthy: Whether the device is healthy
            response_time_ms: Response time in milliseconds
            status_code: HTTP status code
            endpoint: Endpoint that was checked
            response_data: Additional response data
        """
        from sqlalchemy import select

        async with self.get_session() as session:
            # If device_name is provided but device_id is not, look up device_id
            if device_name and device_id is None:
                result = await session.execute(
                    select(Device).where(Device.device_id == device_name)
                )
                device: Optional[Device] = result.scalar_one_or_none()
                if device:
                    device_id = int(device.id)  # type: ignore[arg-type]

            health_check = HealthCheck(
                device_id=device_id,
                is_healthy=is_healthy,
                response_time_ms=response_time_ms,
                status_code=status_code,
                endpoint=endpoint,
                response_data=response_data or {},
            )
            session.add(health_check)
            await session.commit()
            await session.refresh(health_check)
            return health_check

    async def create_audit_log(
        self,
        event_type: str,
        description: str,
        user_id: Optional[int] = None,
        job_id: Optional[int] = None,
        device_id: Optional[int] = None,
        site_id: Optional[int] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        event_metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Create a new audit log entry."""
        async with self.get_session() as session:
            audit_log = AuditLog(
                event_type=event_type,
                description=description,
                user_id=user_id,
                job_id=job_id,
                device_id=device_id,
                site_id=site_id,
                old_values=old_values,
                new_values=new_values,
                event_metadata=event_metadata,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            session.add(audit_log)
            await session.commit()
            await session.refresh(audit_log)
            return audit_log

    async def create_enrolment_intent(
        self,
        intent_id: str,
        site_id: int,
        tenant_id: Optional[int],
        enrolment_method: str,
        claim_token_hash: Optional[str],
        expires_at: datetime.datetime,
        creator_id: int,
        idempotency_key: Optional[str] = None,
        expected_device_identity: Optional[str] = None,
    ) -> EnrolmentIntent:
        """Create a new enrolment intent."""
        async with self.get_session() as session:
            intent = EnrolmentIntent(
                intent_id=intent_id,
                site_id=site_id,
                tenant_id=tenant_id,
                enrolment_method=enrolment_method,
                expected_device_identity=expected_device_identity,
                claim_token_hash=claim_token_hash,
                expires_at=expires_at,
                creator_id=creator_id,
                status=EnrolmentIntentStatus.PENDING,
                idempotency_key=idempotency_key,
            )
            session.add(intent)
            await session.flush()
            await session.refresh(intent)
            return intent

    async def get_enrolment_intent_by_id(
        self, intent_id: str
    ) -> Optional[EnrolmentIntent]:
        """Get an enrolment intent by its public intent_id."""
        async with self.get_session() as session:
            result = await session.execute(
                select(EnrolmentIntent).where(EnrolmentIntent.intent_id == intent_id)
            )
            return result.scalar_one_or_none()

    async def get_enrolment_intent_by_idempotency_key(
        self, idempotency_key: str
    ) -> Optional[EnrolmentIntent]:
        """Get an enrolment intent by its idempotency key."""
        async with self.get_session() as session:
            result = await session.execute(
                select(EnrolmentIntent).where(
                    EnrolmentIntent.idempotency_key == idempotency_key
                )
            )
            return result.scalar_one_or_none()

    async def get_enrolment_intents_by_site(
        self,
        site_id: int,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[EnrolmentIntent]:
        """List enrolment intents for a site, optionally filtered by status."""
        async with self.get_session() as session:
            query = select(EnrolmentIntent).where(EnrolmentIntent.site_id == site_id)
            if status:
                query = query.where(EnrolmentIntent.status == status)
            query = query.order_by(EnrolmentIntent.created_at.desc())
            query = query.limit(limit).offset(offset)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def update_enrolment_intent_status(
        self,
        intent_id: str,
        status: EnrolmentIntentStatus,
        consumed_at: Optional[datetime.datetime] = None,
    ) -> Optional[EnrolmentIntent]:
        """Update the status of an enrolment intent."""
        async with self.get_session() as session:
            result = await session.execute(
                select(EnrolmentIntent).where(EnrolmentIntent.intent_id == intent_id)
            )
            intent = result.scalar_one_or_none()
            if not intent:
                return None
            intent.status = status.value  # type: ignore[assignment]
            if consumed_at:
                intent.consumed_at = consumed_at  # type: ignore[assignment]
            await session.flush()
            await session.refresh(intent)
            return intent

    async def count_enrolment_intents_by_site(
        self, site_id: int, status: Optional[str] = None
    ) -> int:
        """Count enrolment intents for a site."""
        async with self.get_session() as session:
            query = select(EnrolmentIntent).where(EnrolmentIntent.site_id == site_id)
            if status:
                query = query.where(EnrolmentIntent.status == status)
            result = await session.execute(query)
            return len(list(result.scalars().all()))

    async def claim_enrolment_intent_atomic(
        self,
        intent_id: str,
        claim_token: str,
        device_name: Optional[str],
        device_type: str,
        os_details: Optional[str],
        expected_device_identity: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Atomically claim an enrolment intent and create the device.

        Uses ``select_for_update`` to lock the intent row, preventing
        duplicate or concurrent claims.  Validates token hash, expiry,
        scope (expected_device_identity) and unused state.  On success
        creates the device, records a lifecycle epoch, and marks the
        intent as consumed — all in a single transaction.
        """
        import secrets as _secrets

        from passlib.context import CryptContext as _CryptContext

        _pwd = _CryptContext(schemes=["bcrypt"], deprecated="auto")

        async with self.get_session() as session:
            # Lock the intent row for the duration of this transaction
            result = await session.execute(
                select(EnrolmentIntent)
                .where(EnrolmentIntent.intent_id == intent_id)
                .with_for_update()
            )
            intent = result.scalar_one_or_none()
            if not intent:
                raise ValueError("Enrolment intent not found")

            # Validate unused state
            if intent.status != EnrolmentIntentStatus.APPROVED:
                raise ValueError(
                    f"Intent must be approved before claiming (current: {intent.status})"
                )

            # Validate expiry
            if intent.expires_at and intent.expires_at < datetime.datetime.now(
                datetime.timezone.utc
            ):
                raise ValueError("Enrolment intent has expired")

            # Validate token hash
            if not intent.claim_token_hash or not _pwd.verify(
                claim_token, intent.claim_token_hash  # type: ignore[arg-type]
            ):
                raise ValueError("Invalid claim token")

            # Validate expected device identity if set
            if (
                intent.expected_device_identity
                and expected_device_identity != intent.expected_device_identity
            ):
                raise ValueError(
                    f"Expected device identity '{intent.expected_device_identity}' "
                    f"does not match provided '{expected_device_identity}'"
                )

            # Create the device
            new_device_id = f"{device_type}-{_secrets.token_hex(4)}"
            api_key = _secrets.token_urlsafe(32)
            api_key_hash = _pwd.hash(api_key)

            device = Device(
                device_id=new_device_id,
                name=device_name or new_device_id,
                device_type=device_type,
                site_id=intent.site_id,
                api_key_hash=api_key_hash,
                os_details=os_details,
                enrollment_method=intent.enrolment_method,
                lifecycle_state=LifecycleState.PENDING.value,
            )
            session.add(device)
            await session.flush()

            # Create lifecycle epoch
            epoch_id = str(uuid.uuid4())
            epoch = LifecycleEpoch(
                epoch_id=epoch_id,
                device_id=device.id,
                site_id=intent.site_id,
                tenant_id=intent.tenant_id,
                claimed_at=datetime.datetime.now(datetime.timezone.utc),
                claim_token_hash=intent.claim_token_hash,
                enrolment_method=intent.enrolment_method,
            )
            session.add(epoch)
            await session.flush()

            # Link device to its current lifecycle epoch
            device.lifecycle_epoch_id = epoch.id  # type: ignore[assignment]

            # Create tracked credential record
            credential_id = str(uuid.uuid4())
            credential = DeviceCredential(
                credential_id=credential_id,
                device_id=device.id,
                key_hash=api_key_hash,
                is_active=True,
            )
            session.add(credential)

            # Mark intent as consumed
            intent.status = EnrolmentIntentStatus.CONSUMED.value  # type: ignore[assignment]
            intent.consumed_at = datetime.datetime.now(datetime.timezone.utc)  # type: ignore[assignment]

            await session.flush()
            await session.refresh(device)
            await session.refresh(epoch)

        return {
            "device_id": new_device_id,
            "api_key": api_key,
            "site_id": intent.site_id,
            "epoch_id": epoch_id,
        }

    async def regenerate_claim_token(
        self,
        intent_id: str,
    ) -> Dict[str, str]:
        """Regenerate a claim token for an existing pending enrolment intent.

        Returns the new token and its expiry.  Only works on intents
        that are still in PENDING or APPROVED status.
        """
        import secrets as _secrets

        from passlib.context import CryptContext as _CryptContext

        _pwd = _CryptContext(schemes=["bcrypt"], deprecated="auto")

        async with self.get_session() as session:
            result = await session.execute(
                select(EnrolmentIntent)
                .where(EnrolmentIntent.intent_id == intent_id)
                .with_for_update()
            )
            intent = result.scalar_one_or_none()
            if not intent:
                raise ValueError("Enrolment intent not found")

            if intent.status not in (
                EnrolmentIntentStatus.PENDING,
                EnrolmentIntentStatus.APPROVED,
            ):
                raise ValueError(
                    f"Cannot regenerate token for intent in status '{intent.status}'"
                )

            new_token = _secrets.token_urlsafe(32)
            intent.claim_token_hash = _pwd.hash(new_token)  # type: ignore[assignment]
            await session.flush()

            return {"claim_token": new_token}

    async def get_dashboard_summary(
        self,
        site_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get dashboard aggregate counts, optionally scoped to a site.

        Returns device counts grouped by lifecycle_state, connectivity_state,
        and health_state, plus pending enrolment intents and command counts.
        """
        _HB_ONLINE_SECONDS = 120

        async with self.get_session() as session:
            # -- Device counts by lifecycle_state --
            lifecycle_q = select(Device.lifecycle_state, func.count(Device.id)).where(
                Device.is_active.is_(True)
            )
            if site_id is not None:
                lifecycle_q = lifecycle_q.where(Device.site_id == site_id)
            lifecycle_q = lifecycle_q.group_by(Device.lifecycle_state)
            lifecycle_result = await session.execute(lifecycle_q)
            lifecycle_counts: Dict[str, int] = {
                row[0]: row[1] for row in lifecycle_result.all()
            }

            # -- Device counts by health_state --
            health_q = select(
                func.coalesce(Device.health_state, HealthState.UNKNOWN.value),
                func.count(Device.id),
            ).where(Device.is_active.is_(True))
            if site_id is not None:
                health_q = health_q.where(Device.site_id == site_id)
            health_q = health_q.group_by(
                func.coalesce(Device.health_state, HealthState.UNKNOWN.value)
            )
            health_result = await session.execute(health_q)
            health_counts: Dict[str, int] = {
                row[0]: row[1] for row in health_result.all()
            }

            # -- Fetch heartbeats to compute connectivity --
            hb_q = select(Device.last_heartbeat_at).where(Device.is_active.is_(True))
            if site_id is not None:
                hb_q = hb_q.where(Device.site_id == site_id)
            hb_result = await session.execute(hb_q)
            connectivity_counts: Dict[str, int] = defaultdict(int)
            now = datetime.datetime.now(datetime.timezone.utc)
            for hb in hb_result.scalars().all():
                if hb is None:
                    connectivity_counts[ConnectivityState.UNKNOWN.value] += 1
                else:
                    if hb.tzinfo is None:
                        hb = hb.replace(tzinfo=datetime.timezone.utc)
                    delta = now - hb
                    if delta.total_seconds() <= _HB_ONLINE_SECONDS:
                        connectivity_counts[ConnectivityState.ONLINE.value] += 1
                    else:
                        connectivity_counts[ConnectivityState.OFFLINE.value] += 1

            # -- Total device count --
            total_q = select(func.count(Device.id)).where(Device.is_active.is_(True))
            if site_id is not None:
                total_q = total_q.where(Device.site_id == site_id)
            total_result = await session.execute(total_q)
            total_devices = total_result.scalar() or 0

            # -- Pending enrolment intents --
            intents_q = select(func.count(EnrolmentIntent.id)).where(
                EnrolmentIntent.status.in_(
                    [
                        EnrolmentIntentStatus.PENDING,
                        EnrolmentIntentStatus.APPROVED,
                    ]
                )
            )
            if site_id is not None:
                intents_q = intents_q.where(EnrolmentIntent.site_id == site_id)
            intents_result = await session.execute(intents_q)
            pending_intents = intents_result.scalar() or 0

            # -- Pending / expired commands --
            if site_id is not None:
                pending_cmd_q = (
                    select(func.count(DeviceCommand.id))
                    .join(Device, DeviceCommand.device_id == Device.id)
                    .where(
                        DeviceCommand.status == CommandStatus.PENDING,
                        Device.site_id == site_id,
                    )
                )
                expired_cmd_q = (
                    select(func.count(DeviceCommand.id))
                    .join(Device, DeviceCommand.device_id == Device.id)
                    .where(
                        DeviceCommand.status == CommandStatus.EXPIRED,
                        Device.site_id == site_id,
                    )
                )
            else:
                pending_cmd_q = select(func.count(DeviceCommand.id)).where(
                    DeviceCommand.status == CommandStatus.PENDING
                )
                expired_cmd_q = select(func.count(DeviceCommand.id)).where(
                    DeviceCommand.status == CommandStatus.EXPIRED
                )

            pending_cmds_result = await session.execute(pending_cmd_q)
            pending_commands = pending_cmds_result.scalar() or 0

            expired_cmds_result = await session.execute(expired_cmd_q)
            expired_commands = expired_cmds_result.scalar() or 0

        return {
            "total_devices": total_devices,
            "lifecycle_counts": dict(lifecycle_counts),
            "connectivity_counts": dict(connectivity_counts),
            "health_counts": dict(health_counts),
            "pending_enrolment_intents": pending_intents,
            "pending_commands": pending_commands,
            "expired_commands": expired_commands,
        }


# Global database service instance
_db_service: Optional[DatabaseService] = None


async def get_database_service() -> DatabaseService:
    """Get database service singleton."""
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
        await _db_service.initialize()
    return _db_service


async def close_database_service() -> None:
    """Close database service."""
    global _db_service
    if _db_service is not None:
        await _db_service.close()
        _db_service = None


# =============================================================================
# Synchronous Database Support (Legacy & Sync API)
# =============================================================================

# Create sync engine for synchronous operations
_settings = get_settings()
_db_url = _settings.database.url

# Convert async URLs to sync for this synchronous layer
if _db_url.startswith("sqlite+aiosqlite://"):
    _db_url = _db_url.replace("sqlite+aiosqlite://", "sqlite://")
elif _db_url.startswith("postgresql+asyncpg://"):
    _db_url = _db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

# Create sync engine
if _db_url.startswith("sqlite"):
    sync_engine_kwargs: Dict[str, Any] = {
        "connect_args": {"check_same_thread": False},
        "pool_pre_ping": True,
    }
    # SQLite ":memory:" databases are private to the connection that created
    # them. Pin to a single shared connection (StaticPool) so all sessions
    # see the same schema/data instead of each new connection getting a
    # fresh, empty in-memory database.
    if ":memory:" in _db_url:
        from sqlalchemy.pool import StaticPool

        sync_engine_kwargs["poolclass"] = StaticPool
    sync_engine = create_engine(_db_url, **sync_engine_kwargs)
elif _db_url.startswith("postgresql"):
    sync_engine = create_engine(
        _db_url, pool_pre_ping=True, pool_size=5, max_overflow=10
    )
else:
    sync_engine = create_engine(_db_url)

SessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)

# The sync engine is a completely separate connection from the async
# DatabaseService's engine. For file-based/Postgres databases they both
# point at the same underlying storage, but for SQLite ":memory:" URLs each
# engine owns its own private in-memory database. Create the schema here too
# so code paths that use `SessionLocal` (e.g. UserRegisterEndpoint) work
# against an in-memory test database.
if _db_url.startswith("sqlite") and ":memory:" in _db_url:
    Base.metadata.create_all(bind=sync_engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency for getting a sync database session (FastAPI style)."""
    db = None
    try:
        db = SessionLocal()
        yield db
    except Exception as e:
        logger.error("Database session error: %s", e)
        raise
    finally:
        if db is not None:
            db.close()


def execute_update(sql: str, params: Optional[Dict[str, Any]] = None) -> bool:
    """Execute an UPDATE or DELETE statement synchronously."""
    params = params or {}
    with SessionLocal() as session:
        session.execute(text(sql), params)
        session.commit()
        return True
