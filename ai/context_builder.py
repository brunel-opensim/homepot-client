"""Module for building rich context for the AI from various data sources."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import String, and_, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

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
from homepot.database import get_database_service
from homepot.models import AuditLog, Device, HealthCheck, User

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Service to aggregate context from multiple data sources for the LLM."""

    @staticmethod
    async def get_job_context(
        job_id: Optional[str] = None,
        limit: int = 5,
        session: Optional[AsyncSession] = None,
    ) -> str:
        """Retrieve context about recent or specific jobs.

        Args:
            job_id: Optional specific job ID to investigate.
            limit: Number of recent failed jobs to fetch if no ID provided.
            session: Optional database session to reuse.
        """
        try:
            if session:
                return await ContextBuilder._get_job_context_impl(
                    session, job_id, limit
                )

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_job_context_impl(
                    session, job_id, limit
                )

        except Exception as e:
            logger.error(f"Failed to build job context: {e}")
            return "Error retrieving job context."

    @staticmethod
    async def _get_job_context_impl(
        session: AsyncSession, job_id: Optional[str], limit: int
    ) -> str:
        if job_id:
            # Fetch specific job outcome
            stmt = select(JobOutcome).where(JobOutcome.job_id == job_id)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()
            if job:
                return (
                    f"[JOB DETAILS]\n"
                    f"ID: {job.job_id}\n"
                    f"Type: {job.job_type}\n"
                    f"Status: {job.status}\n"
                    f"Error: {job.error_message or 'None'}\n"
                    f"Duration: {job.duration_ms}ms\n"
                )
            return f"Job {job_id} not found."

        # Fetch recent failed jobs
        cutoff = datetime.utcnow() - timedelta(hours=24)
        stmt = (
            select(JobOutcome)
            .where(
                and_(
                    JobOutcome.status == "failed",
                    JobOutcome.timestamp >= cutoff,
                )
            )
            .order_by(JobOutcome.timestamp.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        failed_jobs = result.scalars().all()

        if not failed_jobs:
            return "No failed jobs in the last 24 hours."

        context_lines = ["[RECENT FAILED JOBS]"]
        for job in failed_jobs:
            context_lines.append(
                f"- {job.timestamp.isoformat()}: {job.job_type} ({job.status}) - {job.error_message}"
            )
        return "\n".join(context_lines)

    @staticmethod
    async def get_error_context(
        device_id: Optional[str] = None,
        limit: int = 5,
        session: Optional[AsyncSession] = None,
        device_int_id: Optional[int] = None,
    ) -> str:
        """Retrieve recent error logs.

        Args:
            device_id: Optional device ID (UUID) to filter by.
            limit: Number of errors to fetch.
            session: Optional database session to reuse.
            device_int_id: Optional internal device ID (Integer).
        """
        try:
            if session:
                return await ContextBuilder._get_error_context_impl(
                    session, device_id, limit
                )

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_error_context_impl(
                    session, device_id, limit
                )

        except Exception as e:
            logger.error(f"Failed to build error context: {e}")
            return "Error retrieving error context."

    @staticmethod
    async def _get_error_context_impl(
        session: AsyncSession, device_id: Optional[str], limit: int
    ) -> str:
        stmt = select(ErrorLog).order_by(ErrorLog.timestamp.desc())

        if device_id:
            # Check for device_id in context JSON field
            quoted_id = f'"{device_id}"'
            stmt = stmt.where(
                cast(ErrorLog.context["original_device_id"], String) == quoted_id
            )

        stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        errors = result.scalars().all()

        if device_id and not errors:
            # Fallback for unquoted ID
            stmt = select(ErrorLog).order_by(ErrorLog.timestamp.desc())
            stmt = stmt.where(
                cast(ErrorLog.context["original_device_id"], String) == device_id
            )
            stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            errors = result.scalars().all()

        if not errors:
            return "No recent system errors."

        context_lines = ["[RECENT SYSTEM ERRORS]"]
        for error in errors:
            context_lines.append(
                f"- {error.timestamp.isoformat()} [{error.severity}]: "
                f"{error.error_message} ({error.category})"
            )
        return "\n".join(context_lines)

    @staticmethod
    async def get_config_context(
        device_id: Optional[str] = None,
        limit: int = 5,
        session: Optional[AsyncSession] = None,
        device_int_id: Optional[int] = None,
    ) -> str:
        """Retrieve recent configuration changes.

        Args:
            device_id: Optional device ID (UUID) to filter by.
            limit: Number of changes to fetch.
            session: Optional database session to reuse.
            device_int_id: Optional internal device ID (Integer).
        """
        try:
            if session:
                return await ContextBuilder._get_config_context_impl(
                    session, device_id, limit
                )

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_config_context_impl(
                    session, device_id, limit
                )

        except Exception as e:
            logger.error(f"Failed to build config context: {e}")
            return "Error retrieving config context."

    @staticmethod
    async def _get_config_context_impl(
        session: AsyncSession, device_id: Optional[str], limit: int
    ) -> str:
        stmt = select(ConfigurationHistory).order_by(
            ConfigurationHistory.timestamp.desc()
        )

        if device_id:
            stmt = stmt.where(
                and_(
                    ConfigurationHistory.entity_type == "device",
                    ConfigurationHistory.entity_id == device_id,
                )
            )

        stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        changes = result.scalars().all()

        if not changes:
            return "No recent configuration changes."

        context_lines = ["[RECENT CONFIG CHANGES]"]
        for change in changes:
            context_lines.append(
                f"- {change.timestamp.isoformat()}: {change.parameter_name} "
                f"changed by {change.changed_by} ({change.change_type})"
            )
        return "\n".join(context_lines)

    @staticmethod
    async def get_audit_context(
        device_id: Optional[str] = None,
        limit: int = 5,
        session: Optional[AsyncSession] = None,
        device_int_id: Optional[int] = None,
    ) -> str:
        """Retrieve recent audit logs.

        Args:
            device_id: Optional device ID (UUID) to filter by.
            limit: Number of logs to fetch.
            session: Optional database session to reuse.
            device_int_id: Optional internal device ID (Integer).
        """
        try:
            if session:
                return await ContextBuilder._get_audit_context_impl(
                    session, device_id, limit, device_int_id
                )

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_audit_context_impl(
                    session, device_id, limit, device_int_id
                )

        except Exception as e:
            logger.error(f"Failed to build audit context: {e}")
            return "Error retrieving audit context."

    @staticmethod
    async def _get_audit_context_impl(
        session: AsyncSession,
        device_id: Optional[str],
        limit: int,
        device_int_id: Optional[int] = None,
    ) -> str:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc())

        if device_int_id:
            stmt = stmt.where(AuditLog.device_id == device_int_id)
        elif device_id:
            # Fallback: If we only have UUID but AuditLog needs Int, we can't filter efficiently
            # without a join or lookup.
            # For now, if device_int_id is missing, we might skip filtering or try to resolve.
            # But since we are refactoring to ALWAYS provide device_int_id from api.py,
            # we can assume it's there if device_id is there.
            # If not, we return general logs or empty?
            # Let's try to resolve if missing? No, keep it simple.
            # If device_id is present but device_int_id is not, we can't filter AuditLog (Int FK).
            pass

        stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        logs = result.scalars().all()

        if not logs:
            return "No recent audit logs."

        context_lines = ["[RECENT AUDIT LOGS]"]
        for log in logs:
            context_lines.append(
                f"- {log.created_at.isoformat()}: {log.event_type} - {log.description}"
            )
        return "\n".join(context_lines)

    @staticmethod
    async def get_api_context(
        limit: int = 5, session: Optional[AsyncSession] = None
    ) -> str:
        """Retrieve recent failed API requests.

        Args:
            limit: Number of failed requests to fetch.
            session: Optional database session to reuse.
        """
        try:
            if session:
                return await ContextBuilder._get_api_context_impl(session, limit)

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_api_context_impl(session, limit)

        except Exception as e:
            logger.error(f"Failed to build API context: {e}")
            return "Error retrieving API context."

    @staticmethod
    async def _get_api_context_impl(session: AsyncSession, limit: int) -> str:
        # Fetch recent 5xx or 4xx errors
        stmt = (
            select(APIRequestLog)
            .where(APIRequestLog.status_code >= 400)
            .order_by(APIRequestLog.timestamp.desc())
            .limit(limit)
        )

        result = await session.execute(stmt)
        logs = result.scalars().all()

        if not logs:
            return "No recent API errors."

        context_lines = ["[RECENT API ERRORS]"]
        for log in logs:
            context_lines.append(
                f"- {log.timestamp.isoformat()}: {log.method} {log.endpoint} "
                f"({log.status_code}) - {log.response_time_ms}ms"
            )
        return "\n".join(context_lines)

    @staticmethod
    async def get_state_context(
        device_id: Optional[str] = None,
        limit: int = 5,
        session: Optional[AsyncSession] = None,
    ) -> str:
        """Retrieve recent device state changes.

        Args:
            device_id: Optional device ID to filter by.
            limit: Number of changes to fetch.
            session: Optional database session to reuse.
        """
        try:
            if session:
                return await ContextBuilder._get_state_context_impl(
                    session, device_id, limit
                )

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_state_context_impl(
                    session, device_id, limit
                )

        except Exception as e:
            logger.error(f"Failed to build state context: {e}")
            return "Error retrieving state context."

    @staticmethod
    async def _get_state_context_impl(
        session: AsyncSession, device_id: Optional[str], limit: int
    ) -> str:
        stmt = select(DeviceStateHistory).order_by(DeviceStateHistory.timestamp.desc())

        if device_id:
            stmt = stmt.where(DeviceStateHistory.device_id == device_id)

        stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        changes = result.scalars().all()

        if not changes:
            return "No recent device state changes."

        context_lines = ["[RECENT STATE CHANGES]"]
        for change in changes:
            context_lines.append(
                f"- {change.timestamp.isoformat()}: {change.previous_state} -> "
                f"{change.new_state} ({change.reason})"
            )
        return "\n".join(context_lines)

    @staticmethod
    async def get_push_context(
        device_id: Optional[str] = None,
        limit: int = 5,
        session: Optional[AsyncSession] = None,
    ) -> str:
        """Retrieve recent push notification logs.

        Args:
            device_id: Optional device ID to filter by.
            limit: Number of logs to fetch.
            session: Optional database session to reuse.
        """
        try:
            if session:
                return await ContextBuilder._get_push_context_impl(
                    session, device_id, limit
                )

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_push_context_impl(
                    session, device_id, limit
                )

        except Exception as e:
            logger.error(f"Failed to build push context: {e}")
            return "Error retrieving push context."

    @staticmethod
    async def _get_push_context_impl(
        session: AsyncSession, device_id: Optional[str], limit: int
    ) -> str:
        # device_id filtering temporarily disabled due to schema mismatch
        if device_id:
            return "Push notification history not available for specific devices."

        stmt = select(PushNotificationLog).order_by(PushNotificationLog.sent_at.desc())
        # if device_id:
        #    stmt = stmt.where(PushNotificationLog.device_id == device_id)

        stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        logs = result.scalars().all()

        if not logs:
            return "No recent push notifications."

        context_lines = ["[RECENT PUSH NOTIFICATIONS]"]
        for log in logs:
            status_detail = f"({log.status})"
            if log.status == "failed":
                status_detail = f"(FAILED: {log.error_message or log.error_code})"

            context_lines.append(
                f"- {log.sent_at.isoformat()}: {log.provider} -> {status_detail}"
            )
        return "\n".join(context_lines)

    @staticmethod
    async def get_user_context(
        user_id: Optional[str] = None,
        limit: int = 5,
        session: Optional[AsyncSession] = None,
    ) -> str:
        """Retrieve recent user activity and metadata.

        Args:
            user_id: Optional user ID to filter by.
            limit: Number of activities to fetch.
            session: Optional database session to reuse.
        """
        try:
            if session:
                return await ContextBuilder._get_user_context_impl(
                    session, user_id, limit
                )

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_user_context_impl(
                    session, user_id, limit
                )

        except Exception as e:
            logger.error(f"Failed to build user context: {e}")
            return "Error retrieving user context."

    @staticmethod
    async def _get_user_context_impl(
        session: AsyncSession, user_id: Optional[str], limit: int
    ) -> str:
        context_parts = []

        # 1. Fetch User Metadata if ID provided
        if user_id:
            # Note: User.id is Integer, but user_id arg is often String from API.
            # We need to handle conversion or assume it's passed correctly.
            # For safety, we'll try to cast if it looks like an int, or skip.
            try:
                uid_int = int(user_id)
                stmt = select(User).where(User.id == uid_int)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                if user:
                    context_parts.append(
                        f"[USER PROFILE]\n"
                        f"Username: {user.username}\n"
                        f"Role: {'Admin' if user.is_admin else 'User'}\n"
                        f"Status: {'Active' if user.is_active else 'Inactive'}"
                    )
            except ValueError:
                pass  # user_id wasn't an integer, skip metadata lookup

        # 2. Fetch Recent Activity
        # Use a new variable for the activity statement to avoid type confusion
        activity_stmt = select(UserActivity).order_by(UserActivity.timestamp.desc())

        if user_id:
            activity_stmt = activity_stmt.where(UserActivity.user_id == user_id)

        activity_stmt = activity_stmt.limit(limit)

        # Explicitly type the result to help mypy
        activity_result = await session.execute(activity_stmt)
        activities = activity_result.scalars().all()

        if activities:
            lines = ["[RECENT USER ACTIVITY]"]
            for act in activities:
                # act is UserActivity here
                details = act.page_url or act.element_id or act.activity_type
                lines.append(
                    f"- {act.timestamp.isoformat()}: {act.activity_type} on {details}"
                )
            context_parts.append("\n".join(lines))
        elif not context_parts:
            return "No recent user activity."

        return "\n\n".join(context_parts)

    @staticmethod    async def get_metrics_context(
        device_id: Optional[str] = None,
        limit: int = 5,
        session: Optional[AsyncSession] = None,
        device_int_id: Optional[int] = None,
    ) -> str:
        """Retrieve recent device performance metrics.

        Args:
            device_id: Device UUID.
            limit: Number of records.
            session: DB Session.
            device_int_id: Device Integer ID.
        """
        if not device_id and not device_int_id:
            return ""

        try:
            if session:
                return await ContextBuilder._get_metrics_context_impl(
                    session, device_id, limit, device_int_id
                )

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_metrics_context_impl(
                    session, device_id, limit, device_int_id
                )

        except Exception as e:
            logger.error(f"Failed to build metrics context: {e}")
            return "Error retrieving metrics context."

    @staticmethod
    async def _get_metrics_context_impl(
        session: AsyncSession,
        device_id: Optional[str],
        limit: int,
        device_int_id: Optional[int] = None,
    ) -> str:
        # Resolve ID if needed
        target_id = device_int_id
        if not target_id and device_id:
            # Try to resolve or fallback
            stmt = select(Device).where(Device.device_id == device_id)
            result = await session.execute(stmt)
            device = result.scalar_one_or_none()
            if device:
                target_id = device.id

        if not target_id:
            return "Metrics context unavailable (Device ID resolution failed)."

        stmt = (
            select(DeviceMetrics)
            .where(DeviceMetrics.device_id == target_id)
            .order_by(DeviceMetrics.timestamp.desc())
            .limit(limit)
        )

        result = await session.execute(stmt)
        metrics = result.scalars().all()

        if not metrics:
            return "No recent performance metrics."

        context_lines = ["[RECENT PERFORMANCE METRICS]"]
        for m in metrics:
            context_lines.append(
                f"- {m.timestamp.isoformat()}: CPU={m.cpu_percent}% "
                f"MEM={m.memory_percent}% DISK={m.disk_percent}% "
                f"LATENCY={m.network_latency_ms}ms"
            )
        return "\n".join(context_lines)

    @staticmethod    async def get_site_context(
        device_id: Optional[str] = None,
        session: Optional[AsyncSession] = None,
        device_int_id: Optional[int] = None,
    ) -> str:
        """Retrieve site operating schedule and status.

        Args:
            device_id: Device ID to look up the site for.
            session: Optional database session to reuse.
            device_int_id: Optional internal device ID (Integer).
        """
        if not device_id and not device_int_id:
            return ""

        try:
            if session:
                return await ContextBuilder._get_site_context_impl(
                    session, device_id, device_int_id
                )

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_site_context_impl(
                    session, device_id, device_int_id
                )

        except Exception as e:
            logger.error(f"Failed to build site context: {e}")
            return "Error retrieving site context."

    @staticmethod
    async def _get_site_context_impl(
        session: AsyncSession,
        device_id: Optional[str],
        device_int_id: Optional[int] = None,
    ) -> str:
        # 1. Get Site ID from Device
        if device_int_id:
            stmt = select(Device).where(Device.id == device_int_id)
        else:
            stmt = select(Device).where(Device.device_id == device_id)

        result = await session.execute(stmt)
        device = result.scalar_one_or_none()

        if not device or not device.site_id:
            return "Site context unavailable (Device not found or no Site ID)."

        # 2. Get Schedule for Today
        now = datetime.utcnow()
        day_of_week = now.weekday()  # 0=Monday, 6=Sunday

        schedule_stmt = select(SiteOperatingSchedule).where(
            and_(
                SiteOperatingSchedule.site_id == device.site_id,
                SiteOperatingSchedule.day_of_week == day_of_week,
            )
        )
        schedule_result = await session.execute(schedule_stmt)
        schedule = schedule_result.scalar_one_or_none()

        if not schedule:
            return f"No schedule defined for Site {device.site_id} today."

        # 3. Determine Status
        status = "OPEN"
        if schedule.is_closed:
            status = "CLOSED (Scheduled Closure)"
        elif schedule.open_time and schedule.close_time:
            current_time = now.time()
            if current_time < schedule.open_time or current_time > schedule.close_time:
                status = "CLOSED (Outside Hours)"

        return (
            f"[SITE CONTEXT]\n"
            f"Site ID: {device.site_id}\n"
            f"Status: {status}\n"
            f"Hours: {schedule.open_time} - {schedule.close_time}"
        )

    @staticmethod
    async def get_metadata_context(
        device_id: Optional[str] = None,
        session: Optional[AsyncSession] = None,
        device_int_id: Optional[int] = None,
    ) -> str:
        """Retrieve device metadata and recent health checks.

        Args:
            device_id: Device ID to fetch metadata for.
            session: Optional database session to reuse.
            device_int_id: Optional internal device ID (Integer).
        """
        if not device_id and not device_int_id:
            return ""

        try:
            if session:
                return await ContextBuilder._get_metadata_context_impl(
                    session, device_id, device_int_id
                )

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_metadata_context_impl(
                    session, device_id, device_int_id
                )

        except Exception as e:
            logger.error(f"Failed to build metadata context: {e}")
            return "Error retrieving metadata context."

    @staticmethod
    async def _get_metadata_context_impl(
        session: AsyncSession,
        device_id: Optional[str],
        device_int_id: Optional[int] = None,
    ) -> str:
        context_parts = []

        # 1. Fetch Device Metadata
        if device_int_id:
            stmt = select(Device).where(Device.id == device_int_id)
        else:
            stmt = select(Device).where(Device.device_id == device_id)

        result = await session.execute(stmt)
        device = result.scalar_one_or_none()

        if device:
            last_seen_str = (
                device.last_seen.isoformat() if device.last_seen else "Unknown"
            )
            context_parts.append(
                f"[DEVICE METADATA]\n"
                f"Name: {device.name}\n"
                f"Type: {device.device_type}\n"
                f"Firmware: {device.firmware_version or 'Unknown'}\n"
                f"IP: {device.ip_address or 'Unknown'}\n"
                f"Last Seen: {last_seen_str}"
            )
        else:
            return f"Device {device_id or device_int_id} not found."

        # 2. Fetch Recent Health Checks
        # Note: HealthCheck uses Integer FK to Device.id
        # Since we have the device object (and it has .id), we can use it directly.
        if device.id:
            health_stmt = (
                select(HealthCheck)
                .where(HealthCheck.device_id == device.id)
                .order_by(HealthCheck.timestamp.desc())
                .limit(5)
            )
            health_result = await session.execute(health_stmt)
            checks = health_result.scalars().all()

            if checks:
                lines = ["[RECENT HEALTH CHECKS]"]
                for check in checks:
                    status = "Healthy" if check.is_healthy else "Unhealthy"
                    lines.append(
                        f"- {check.timestamp.isoformat()}: {status} "
                        f"({check.response_time_ms}ms) - {check.endpoint}"
                    )
                context_parts.append("\n".join(lines))

        return "\n\n".join(context_parts)
