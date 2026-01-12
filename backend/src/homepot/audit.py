"""Audit logging service for HOMEPOT Client.

This module provides comprehensive audit logging functionality for tracking
all system events, user actions, and device interactions for compliance
and monitoring purposes.
"""

from datetime import datetime
from enum import Enum
import logging
from typing import Any, Dict, List, Optional

from homepot.database import get_database_service
from homepot.models import AuditLog

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Audit event types for categorization."""

    # User actions
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_ACTION = "user_action"

    # Site management
    SITE_CREATED = "site_created"
    SITE_UPDATED = "site_updated"
    SITE_DELETED = "site_deleted"

    # Device management
    DEVICE_CREATED = "device_created"
    DEVICE_UPDATED = "device_updated"
    DEVICE_DELETED = "device_deleted"
    DEVICE_STATUS_CHANGED = "device_status_changed"

    # Job management
    JOB_CREATED = "job_created"
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    JOB_CANCELLED = "job_cancelled"

    # Agent interactions
    AGENT_STARTED = "agent_started"
    AGENT_STOPPED = "agent_stopped"
    PUSH_NOTIFICATION_SENT = "push_notification_sent"
    HEALTH_CHECK_PERFORMED = "health_check_performed"
    CONFIG_UPDATE_APPLIED = "config_update_applied"

    # System events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    ERROR_OCCURRED = "error_occurred"

    # Security events
    API_ACCESS = "api_access"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


class AuditLogger:
    """Comprehensive audit logging service."""

    def __init__(self) -> None:
        """Initialize the audit logger with configured logging."""
        self.logger = logging.getLogger(f"{__name__}.AuditLogger")

    async def log_event(
        self,
        event_type: AuditEventType,
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
        """Log an audit event to the database.

        Args:
            event_type: Type of event from AuditEventType enum
            description: Human-readable description of the event
            user_id: ID of the user who triggered the event (optional)
            job_id: ID of the related job (optional)
            device_id: ID of the related device (optional)
            site_id: ID of the related site (optional)
            old_values: Previous values (for update events)
            new_values: New values (for update events)
            event_metadata: Additional event data
            ip_address: IP address of the request (optional)
            user_agent: User agent string (optional)

        Returns:
            Created AuditLog instance
        """
        try:
            db_service = await get_database_service()

            # Create audit log entry
            audit_log = await db_service.create_audit_log(
                event_type=event_type.value,
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

            # Also log to application logger for immediate visibility
            self.logger.info(f"AUDIT: {event_type.value} - {description}")

            return audit_log

        except Exception as e:
            # Audit logging should never break the main application
            self.logger.error(f"Failed to log audit event {event_type.value}: {e}")
            raise

    async def log_user_action(
        self,
        user_id: Optional[int],
        action: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log a user action."""
        return await self.log_event(
            event_type=AuditEventType.USER_ACTION,
            description=f"User action: {action} - {description}",
            user_id=user_id,
            event_metadata={"action": action, **(metadata or {})},
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_job_event(
        self,
        job_id: int,
        event_type: AuditEventType,
        description: str,
        site_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """Log a job-related event."""
        return await self.log_event(
            event_type=event_type,
            description=description,
            job_id=job_id,
            site_id=site_id,
            event_metadata=metadata,
        )

    async def log_device_event(
        self,
        device_id: int,
        event_type: AuditEventType,
        description: str,
        site_id: Optional[int] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """Log a device-related event."""
        return await self.log_event(
            event_type=event_type,
            description=description,
            device_id=device_id,
            site_id=site_id,
            old_values=old_values,
            new_values=new_values,
            event_metadata=metadata,
        )

    async def log_agent_event(
        self,
        device_id: int,
        event_type: AuditEventType,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """Log an agent-related event."""
        return await self.log_event(
            event_type=event_type,
            description=description,
            device_id=device_id,
            event_metadata=metadata,
        )

    async def log_system_event(
        self,
        event_type: AuditEventType,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """Log a system event."""
        return await self.log_event(
            event_type=event_type,
            description=description,
            event_metadata=metadata,
        )

    async def log_api_access(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        response_time_ms: Optional[int] = None,
    ) -> AuditLog:
        """Log API access for monitoring and security."""
        return await self.log_event(
            event_type=AuditEventType.API_ACCESS,
            description=f"{method} {endpoint} - {status_code}",
            user_id=user_id,
            event_metadata={
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "response_time_ms": response_time_ms,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def get_recent_events(
        self,
        limit: int = 50,
        event_types: Optional[List[AuditEventType]] = None,
        user_id: Optional[int] = None,
        device_id: Optional[int] = None,
        site_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent audit events with optional filtering."""
        try:
            db_service = await get_database_service()

            from sqlalchemy import desc, select

            async with db_service.get_session() as session:
                query = (
                    select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
                )

                # Apply filters
                if event_types:
                    event_type_values = [et.value for et in event_types]
                    query = query.where(AuditLog.event_type.in_(event_type_values))

                if user_id:
                    query = query.where(AuditLog.user_id == user_id)

                if device_id:
                    query = query.where(AuditLog.device_id == device_id)

                if site_id:
                    query = query.where(AuditLog.site_id == site_id)

                result = await session.execute(query)
                audit_logs = result.scalars().all()

                # Convert to dict format
                events = []
                for log in audit_logs:
                    events.append(
                        {
                            "id": log.id,
                            "event_type": log.event_type,
                            "description": log.description,
                            "user_id": log.user_id,
                            "job_id": log.job_id,
                            "device_id": log.device_id,
                            "site_id": log.site_id,
                            "old_values": log.old_values,
                            "new_values": log.new_values,
                            "event_metadata": log.event_metadata,
                            "ip_address": log.ip_address,
                            "user_agent": log.user_agent,
                            "created_at": (
                                log.created_at.isoformat() if log.created_at else None
                            ),
                        }
                    )

                return events

        except Exception as e:
            self.logger.error(f"Failed to get recent audit events: {e}")
            return []

    async def get_event_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get audit event statistics for the dashboard."""
        try:
            db_service = await get_database_service()

            from datetime import timedelta

            from sqlalchemy import func, select

            since = datetime.utcnow() - timedelta(hours=hours)

            async with db_service.get_session() as session:
                # Total events
                total_result = await session.execute(
                    select(func.count(AuditLog.id)).where(AuditLog.created_at >= since)
                )
                total_events = total_result.scalar()

                # Events by type
                type_result = await session.execute(
                    select(AuditLog.event_type, func.count(AuditLog.id))
                    .where(AuditLog.created_at >= since)
                    .group_by(AuditLog.event_type)
                )
                events_by_type: Dict[str, int] = {
                    row[0]: row[1] for row in type_result.all()
                }

                # API access count
                api_result = await session.execute(
                    select(func.count(AuditLog.id))
                    .where(AuditLog.created_at >= since)
                    .where(AuditLog.event_type == AuditEventType.API_ACCESS.value)
                )
                api_access_count = api_result.scalar()

                return {
                    "total_events": total_events,
                    "events_by_type": events_by_type,
                    "api_access_count": api_access_count,
                    "time_period_hours": hours,
                    "since": since.isoformat(),
                }

        except Exception as e:
            self.logger.error(f"Failed to get audit statistics: {e}")
            # Return a generic error message, do not expose exception details
            return {
                "total_events": 0,
                "events_by_type": {},
                "api_access_count": 0,
                "time_period_hours": hours,
                "error": "Internal server error",
            }


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get audit logger singleton."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
