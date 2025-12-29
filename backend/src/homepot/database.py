"""Database service layer for HOMEPOT Client.

This module provides async database operations and session management
for the HOMEPOT system.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional

from sqlalchemy import Result, create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from homepot.config import get_settings
from homepot.models import (
    AuditLog,
    Base,
    CommandStatus,
    Device,
    DeviceCommand,
    DeviceStatus,
    HealthCheck,
    Job,
    JobStatus,
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

        self.engine = create_async_engine(
            db_url,
            echo=settings.database.echo_sql,
            future=True,
        )

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
        async with self.session_maker() as session:
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
    ) -> Site:
        """Create a new site."""
        async with self.get_session() as session:
            site = Site(
                site_id=site_id,
                name=name,
                description=description,
                location=location,
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

        async with self.get_session() as session:
            result = await session.execute(
                select(Device).where(
                    Device.device_id == device_id, Device.is_active.is_(True)
                )
            )
            return result.scalar_one_or_none()

    async def get_devices_by_site_id(self, site_id: str) -> List[Device]:
        """Get all devices for a site by site_id string (e.g., 'site-123').

        Args:
            site_id: Business ID of the site (string like 'site-123')

        Returns:
            List of Device objects for the site (empty if site not found)
        """
        from sqlalchemy import select

        async with self.get_session() as session:
            # Verify site exists first
            site = await self.get_site_by_site_id(site_id)
            if not site:
                return []

            # Query devices using string site_id FK
            result = await session.execute(
                select(Device)
                .where(Device.site_id == site_id, Device.is_active.is_(True))
                .order_by(Device.created_at.desc())
            )
            return list(result.scalars().all())

    # Device operations
    async def create_device(
        self,
        device_id: str,
        name: str,
        device_type: str,
        site_id: str,
        ip_address: Optional[str] = None,
        config: Optional[dict] = None,
        api_key_hash: Optional[str] = None,
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
                api_key_hash=api_key_hash,
            )
            session.add(device)
            await session.flush()
            await session.refresh(device)
            return device

    async def get_devices_by_site_and_segment(
        self, site_id: str, segment: Optional[str] = None
    ) -> List[Device]:
        """Get devices by site (using string identifier) and optional segment."""
        from sqlalchemy import select

        async with self.get_session() as session:
            query = select(Device).where(
                Device.site_id == site_id, Device.is_active.is_(True)
            )

            # For POS scenario: filter by device type if segment specified
            if segment == "pos-terminals":
                query = query.where(Device.device_type == "pos_terminal")

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
    _db_url = _db_url.replace("sqlite+aiosqlite://", "sqlite:///")
elif _db_url.startswith("postgresql+asyncpg://"):
    _db_url = _db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

# Create sync engine
if _db_url.startswith("sqlite"):
    sync_engine = create_engine(
        _db_url, connect_args={"check_same_thread": False}, pool_pre_ping=True
    )
elif _db_url.startswith("postgresql"):
    sync_engine = create_engine(
        _db_url, pool_pre_ping=True, pool_size=5, max_overflow=10
    )
else:
    sync_engine = create_engine(_db_url)

SessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)


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
