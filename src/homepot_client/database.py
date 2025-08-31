"""Database service layer for HOMEPOT Client.

This module provides async database operations and session management
for the HOMEPOT system.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from homepot_client.config import get_settings
from homepot_client.models import (
    AuditLog,
    Base,
    Device,
    DeviceStatus,
    HealthCheck,
    Job,
    JobStatus,
    Site,
    User,
)

logger = logging.getLogger(__name__)


class DatabaseService:
    """Async database service for HOMEPOT operations."""
    
    def __init__(self):
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
    
    async def initialize(self):
        """Initialize database schema."""
        if self._initialized:
            return
        
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            logger.info("Database initialized successfully")
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def close(self):
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
                select(User).where(User.api_key == api_key, User.is_active == True)
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
                select(Site).where(Site.site_id == site_id, Site.is_active == True)
            )
            return result.scalar_one_or_none()
    
    # Device operations
    async def create_device(
        self,
        device_id: str,
        name: str,
        device_type: str,
        site_id: int,
        ip_address: Optional[str] = None,
        config: Optional[dict] = None,
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
            )
            session.add(device)
            await session.flush()
            await session.refresh(device)
            return device
    
    async def get_devices_by_site_and_segment(
        self, site_id: int, segment: Optional[str] = None
    ) -> List[Device]:
        """Get devices by site and optional segment."""
        from sqlalchemy import select
        
        async with self.get_session() as session:
            query = select(Device).where(
                Device.site_id == site_id, Device.is_active == True
            )
            
            # For POS scenario: filter by device type if segment specified
            if segment == "pos-terminals":
                query = query.where(Device.device_type == "pos_terminal")
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def update_device_status(self, device_id: str, status: DeviceStatus) -> bool:
        """Update device status."""
        from sqlalchemy import select, update
        
        async with self.get_session() as session:
            result = await session.execute(
                update(Device)
                .where(Device.device_id == device_id)
                .values(status=status)
            )
            return result.rowcount > 0
    
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
            
            result = await session.execute(
                update(Job).where(Job.job_id == job_id).values(**update_data)
            )
            return result.rowcount > 0
    
    async def get_job_by_id(self, job_id: str) -> Optional[Job]:
        """Get job by job_id with site relationship loaded."""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        
        async with self.get_session() as session:
            result = await session.execute(
                select(Job)
                .options(selectinload(Job.site))
                .where(Job.job_id == job_id)
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
                device = result.scalar_one_or_none()
                if device:
                    device_id = device.id
                    
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
    
    # Audit logging
    async def create_audit_log(
        self,
        event_type: str,
        description: str,
        user_id: Optional[int] = None,
        job_id: Optional[int] = None,
        device_id: Optional[int] = None,
        site_id: Optional[int] = None,
        old_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
        metadata: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Create an audit log entry."""
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
                metadata=metadata,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            session.add(audit_log)
            await session.flush()
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


async def close_database_service():
    """Close database service."""
    global _db_service
    if _db_service is not None:
        await _db_service.close()
        _db_service = None
