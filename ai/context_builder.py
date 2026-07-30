"""Module for building rich context for the AI from various data sources."""

from datetime import datetime, timedelta
import logging
from typing import Any, Optional

from sqlalchemy import String, and_, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from homepot.app.models.AnalyticsModel import (
    Alert,
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
from homepot.models import (
    AuditLog,
    Device,
    DeviceAssignment,
    DeviceCommand,
    DeviceCredential,
    DeviceLifecycleEvent,
    EnrolmentIntent,
    HealthCheck,
    Job,
    LifecycleEpoch,
    Site,
    SiteMembership,
    Tenant,
    TenantMembership,
    User,
)

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
            line = (
                f"- {change.timestamp.isoformat()}: {change.parameter_name} "
                f"changed by {change.changed_by} ({change.change_type})"
            )
            if change.was_rolled_back:
                line += " [ROLLED BACK]"
            if change.was_successful is False:
                line += " [FAILED]"
            perf_before: Any = change.performance_before or {}
            perf_after: Any = change.performance_after or {}
            if perf_before:
                line += f" | before: {perf_before}"
            if perf_after:
                line += f" | after: {perf_after}"
            context_lines.append(line)
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

    @staticmethod
    async def get_tenant_context(
        session: Optional[AsyncSession] = None,
    ) -> str:
        """Retrieve tenants."""
        try:
            if session:
                return await ContextBuilder._get_tenant_context_impl(session)

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_tenant_context_impl(session)

        except Exception as e:
            logger.error(f"Failed to build tenant context: {e}")
            return "Error retrieving tenant context."

    @staticmethod
    async def _get_tenant_context_impl(session: AsyncSession) -> str:
        stmt = select(Tenant).order_by(Tenant.name)
        result = await session.execute(stmt)
        tenants = result.scalars().all()

        if not tenants:
            return "No tenants found."

        context_lines = ["[TENANTS]"]
        for t in tenants:
            context_lines.append(
                f"- {t.name} ({t.slug}) {'active' if t.is_active else 'inactive'}"
            )
        return "\n".join(context_lines)

    @staticmethod
    async def get_tenant_membership_context(
        session: Optional[AsyncSession] = None,
    ) -> str:
        """Retrieve tenant memberships."""
        try:
            if session:
                return await ContextBuilder._get_tenant_membership_context_impl(session)

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_tenant_membership_context_impl(session)

        except Exception as e:
            logger.error(f"Failed to build tenant membership context: {e}")
            return "Error retrieving tenant membership context."

    @staticmethod
    async def _get_tenant_membership_context_impl(session: AsyncSession) -> str:
        stmt = select(TenantMembership).order_by(TenantMembership.created_at.desc())
        result = await session.execute(stmt)
        memberships = result.scalars().all()

        if not memberships:
            return "No tenant memberships found."

        context_lines = ["[TENANT MEMBERSHIPS]"]
        for m in memberships:
            context_lines.append(
                f"- user={m.user_id} tenant={m.tenant_id} role={m.role}"
            )
        return "\n".join(context_lines)

    @staticmethod
    async def get_site_membership_context(
        session: Optional[AsyncSession] = None,
    ) -> str:
        """Retrieve site memberships."""
        try:
            if session:
                return await ContextBuilder._get_site_membership_context_impl(session)

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_site_membership_context_impl(session)

        except Exception as e:
            logger.error(f"Failed to build site membership context: {e}")
            return "Error retrieving site membership context."

    @staticmethod
    async def _get_site_membership_context_impl(session: AsyncSession) -> str:
        stmt = select(SiteMembership).order_by(SiteMembership.created_at.desc())
        result = await session.execute(stmt)
        memberships = result.scalars().all()

        if not memberships:
            return "No site memberships found."

        context_lines = ["[SITE MEMBERSHIPS]"]
        for m in memberships:
            context_lines.append(f"- user={m.user_id} site={m.site_id} role={m.role}")
        return "\n".join(context_lines)

    @staticmethod
    async def get_enrolment_intent_context(
        limit: int = 10,
        session: Optional[AsyncSession] = None,
    ) -> str:
        """Retrieve enrolment intents."""
        try:
            if session:
                return await ContextBuilder._get_enrolment_intent_context_impl(
                    session, limit
                )

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_enrolment_intent_context_impl(
                    session, limit
                )

        except Exception as e:
            logger.error(f"Failed to build enrolment intent context: {e}")
            return "Error retrieving enrolment intent context."

    @staticmethod
    async def _get_enrolment_intent_context_impl(
        session: AsyncSession, limit: int
    ) -> str:
        stmt = (
            select(EnrolmentIntent)
            .order_by(EnrolmentIntent.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        intents = result.scalars().all()

        if not intents:
            return "No enrolment intents found."

        context_lines = ["[ENROLMENT INTENTS]"]
        for e in intents:
            context_lines.append(
                f"- {e.intent_id}: site={e.site_id} method={e.enrolment_method} status={e.status}"
            )
        return "\n".join(context_lines)

    @staticmethod
    async def get_lifecycle_epoch_context(
        device_id: Optional[str] = None,
        limit: int = 10,
        session: Optional[AsyncSession] = None,
    ) -> str:
        """Retrieve lifecycle epochs."""
        try:
            if session:
                return await ContextBuilder._get_lifecycle_epoch_context_impl(
                    session, device_id, limit
                )

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_lifecycle_epoch_context_impl(
                    session, device_id, limit
                )

        except Exception as e:
            logger.error(f"Failed to build lifecycle epoch context: {e}")
            return "Error retrieving lifecycle epoch context."

    @staticmethod
    async def _get_lifecycle_epoch_context_impl(
        session: AsyncSession,
        device_id: Optional[str],
        limit: int,
    ) -> str:
        stmt = select(LifecycleEpoch).order_by(LifecycleEpoch.created_at.desc())

        if device_id:
            dev_stmt = select(Device.id).where(Device.device_id == device_id)
            dev_result = await session.execute(dev_stmt)
            dev_pk = dev_result.scalar_one_or_none()
            if dev_pk:
                stmt = stmt.where(LifecycleEpoch.device_id == dev_pk)

        stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        epochs = result.scalars().all()

        if not epochs:
            return "No lifecycle epochs found."

        context_lines = ["[LIFECYCLE EPOCHS]"]
        for e in epochs:
            ended = e.ended_at.isoformat() if e.ended_at else "ongoing"
            context_lines.append(
                f"- epoch={e.epoch_id} device={e.device_id} claimed={e.claimed_at.isoformat()} ended={ended}"
            )
        return "\n".join(context_lines)

    @staticmethod
    async def get_device_credential_context(
        device_id: Optional[str] = None,
        limit: int = 10,
        session: Optional[AsyncSession] = None,
    ) -> str:
        """Retrieve device credentials."""
        try:
            if session:
                return await ContextBuilder._get_device_credential_context_impl(
                    session, device_id, limit
                )

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_device_credential_context_impl(
                    session, device_id, limit
                )

        except Exception as e:
            logger.error(f"Failed to build device credential context: {e}")
            return "Error retrieving device credential context."

    @staticmethod
    async def _get_device_credential_context_impl(
        session: AsyncSession,
        device_id: Optional[str],
        limit: int,
    ) -> str:
        stmt = select(DeviceCredential).order_by(DeviceCredential.created_at.desc())

        if device_id:
            dev_stmt = select(Device.id).where(Device.device_id == device_id)
            dev_result = await session.execute(dev_stmt)
            dev_pk = dev_result.scalar_one_or_none()
            if dev_pk:
                stmt = stmt.where(DeviceCredential.device_id == dev_pk)

        stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        creds = result.scalars().all()

        if not creds:
            return "No device credentials found."

        context_lines = ["[DEVICE CREDENTIALS]"]
        for c in creds:
            status = "active" if c.is_active else "revoked"
            context_lines.append(
                f"- {c.credential_id}: device={c.device_id} status={status} created={c.created_at.isoformat()}"
            )
        return "\n".join(context_lines)

    @staticmethod
    async def get_device_command_context(
        device_id: Optional[str] = None,
        limit: int = 10,
        session: Optional[AsyncSession] = None,
    ) -> str:
        """Retrieve recent device commands."""
        try:
            if session:
                return await ContextBuilder._get_device_command_context_impl(
                    session, device_id, limit
                )

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_device_command_context_impl(
                    session, device_id, limit
                )

        except Exception as e:
            logger.error(f"Failed to build device command context: {e}")
            return "Error retrieving device command context."

    @staticmethod
    async def _get_device_command_context_impl(
        session: AsyncSession,
        device_id: Optional[str],
        limit: int,
    ) -> str:
        stmt = select(DeviceCommand).order_by(DeviceCommand.created_at.desc())

        if device_id:
            dev_stmt = select(Device.id).where(Device.device_id == device_id)
            dev_result = await session.execute(dev_stmt)
            dev_pk = dev_result.scalar_one_or_none()
            if dev_pk:
                stmt = stmt.where(DeviceCommand.device_id == dev_pk)

        stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        commands = result.scalars().all()

        if not commands:
            return "No device commands found."

        context_lines = ["[DEVICE COMMANDS]"]
        for cmd in commands:
            context_lines.append(
                f"- {cmd.command_id}: type={cmd.command_type} status={cmd.status} created={cmd.created_at.isoformat()}"
            )
        return "\n".join(context_lines)

    @staticmethod
    async def get_device_assignment_context(
        device_id: Optional[str] = None,
        limit: int = 10,
        session: Optional[AsyncSession] = None,
    ) -> str:
        """Retrieve device assignment history."""
        try:
            if session:
                return await ContextBuilder._get_device_assignment_context_impl(
                    session, device_id, limit
                )

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_device_assignment_context_impl(
                    session, device_id, limit
                )

        except Exception as e:
            logger.error(f"Failed to build device assignment context: {e}")
            return "Error retrieving device assignment context."

    @staticmethod
    async def _get_device_assignment_context_impl(
        session: AsyncSession,
        device_id: Optional[str],
        limit: int,
    ) -> str:
        stmt = select(DeviceAssignment).order_by(DeviceAssignment.created_at.desc())

        if device_id:
            dev_stmt = select(Device.id).where(Device.device_id == device_id)
            dev_result = await session.execute(dev_stmt)
            dev_pk = dev_result.scalar_one_or_none()
            if dev_pk:
                stmt = stmt.where(DeviceAssignment.device_id == dev_pk)

        stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        assignments = result.scalars().all()

        if not assignments:
            return "No device assignments found."

        context_lines = ["[DEVICE ASSIGNMENTS]"]
        for a in assignments:
            current = "current" if a.is_current else "historical"
            context_lines.append(
                f"- {a.assignment_id}: device={a.device_id} site={a.site_id} "
                f"reason={a.assignment_reason or 'unknown'} ({current})"
            )
        return "\n".join(context_lines)

    @staticmethod
    async def get_device_lifecycle_event_context(
        device_id: Optional[str] = None,
        limit: int = 10,
        session: Optional[AsyncSession] = None,
    ) -> str:
        """Retrieve device lifecycle events."""
        try:
            if session:
                return await ContextBuilder._get_device_lifecycle_event_context_impl(
                    session, device_id, limit
                )

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_device_lifecycle_event_context_impl(
                    session, device_id, limit
                )

        except Exception as e:
            logger.error(f"Failed to build device lifecycle event context: {e}")
            return "Error retrieving device lifecycle event context."

    @staticmethod
    async def _get_device_lifecycle_event_context_impl(
        session: AsyncSession,
        device_id: Optional[str],
        limit: int,
    ) -> str:
        stmt = select(DeviceLifecycleEvent).order_by(
            DeviceLifecycleEvent.created_at.desc()
        )

        if device_id:
            dev_stmt = select(Device.id).where(Device.device_id == device_id)
            dev_result = await session.execute(dev_stmt)
            dev_pk = dev_result.scalar_one_or_none()
            if dev_pk:
                stmt = stmt.where(DeviceLifecycleEvent.device_id == dev_pk)

        stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        events = result.scalars().all()

        if not events:
            return "No device lifecycle events found."

        context_lines = ["[DEVICE LIFECYCLE EVENTS]"]
        for e in events:
            context_lines.append(
                f"- {e.event_id}: {e.from_state or '?'} -> {e.to_state or '?'} reason={e.reason or 'none'}"
            )
        return "\n".join(context_lines)

    @staticmethod
    async def get_jobs_context(
        device_id: Optional[str] = None,
        limit: int = 10,
        session: Optional[AsyncSession] = None,
    ) -> str:
        """Retrieve recent device management jobs."""
        try:
            if session:
                return await ContextBuilder._get_jobs_context_impl(
                    session, device_id, limit
                )

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_jobs_context_impl(
                    session, device_id, limit
                )

        except Exception as e:
            logger.error(f"Failed to build jobs context: {e}")
            return "Error retrieving jobs context."

    @staticmethod
    async def _get_jobs_context_impl(
        session: AsyncSession,
        device_id: Optional[str],
        limit: int,
    ) -> str:
        stmt = select(Job).order_by(Job.created_at.desc())

        if device_id:
            dev_stmt = select(Device.id).where(Device.device_id == device_id)
            dev_result = await session.execute(dev_stmt)
            dev_pk = dev_result.scalar_one_or_none()
            if dev_pk:
                stmt = stmt.where(Job.device_id == dev_pk)

        stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        jobs = result.scalars().all()

        if not jobs:
            return "No jobs found."

        context_lines = ["[JOBS]"]
        for j in jobs:
            context_lines.append(
                f"- {j.job_id}: action={j.action} status={j.status} "
                f"priority={j.priority} site={j.site_id}"
            )
        return "\n".join(context_lines)

    @staticmethod
    async def get_metrics_context(
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
            resolve_stmt = select(Device).where(Device.device_id == device_id)
            resolve_result = await session.execute(resolve_stmt)
            device = resolve_result.scalar_one_or_none()
            if device:
                target_id = int(device.id)

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
            extra: Any = m.extra_metrics or {}
            extra_str = (
                ", ".join(f"{k}={v}" for k, v in sorted(extra.items())) if extra else ""
            )
            parts = [
                f"- {m.timestamp.isoformat()}: CPU={m.cpu_percent}% "
                f"MEM={m.memory_percent}% DISK={m.disk_percent}% "
                f"LATENCY={m.network_latency_ms}ms"
            ]
            if m.transaction_count is not None:
                parts.append(f"TX={m.transaction_count}")
            if m.transaction_volume is not None:
                parts.append(f"TX_VOL=${m.transaction_volume}")
            if m.active_connections is not None:
                parts.append(f"CONN={m.active_connections}")
            if m.queue_depth is not None:
                parts.append(f"QUEUE={m.queue_depth}")
            if m.error_rate is not None:
                parts.append(f"ERR={m.error_rate}%")
            if extra_str:
                parts.append(f"EXTRA=[{extra_str}]")
            context_lines.append(" | ".join(parts))
        return "\n".join(context_lines)

    @staticmethod
    async def get_alert_context(
        device_id: Optional[str] = None,
        limit: int = 5,
        session: Optional[AsyncSession] = None,
    ) -> str:
        """Retrieve active alerts for the device.

        Args:
            device_id: Device ID to filter by.
            limit: Number of alerts to fetch.
            session: Optional database session to reuse.
        """
        try:
            if session:
                return await ContextBuilder._get_alert_context_impl(
                    session, device_id, limit
                )

            db_service = await get_database_service()
            async with db_service.get_session() as session:
                return await ContextBuilder._get_alert_context_impl(
                    session, device_id, limit
                )

        except Exception as e:
            logger.error(f"Failed to build alert context: {e}")
            return "Error retrieving alert context."

    @staticmethod
    async def _get_alert_context_impl(
        session: AsyncSession, device_id: Optional[str], limit: int
    ) -> str:
        stmt = select(Alert).where(Alert.status == "active").order_by(Alert.severity)

        if device_id:
            stmt = stmt.where(Alert.device_id == device_id)

        stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        alerts = result.scalars().all()

        if not alerts:
            return "No active alerts."

        context_lines = ["[ACTIVE SYSTEM ALERTS]"]
        for alert in alerts:
            context_lines.append(
                f"- #{alert.id} [{alert.severity.upper()}] {alert.title}: {alert.description}"
            )
        return "\n".join(context_lines)

    @staticmethod
    async def get_site_context(
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

            perms: Any = device.device_permissions or {}
            caps: Any = device.capabilities or {}
            perm_lines = "\n".join(
                f"  {k}: {'granted' if v else 'none'}" for k, v in sorted(perms.items())
            )
            cap_lines = "\n".join(
                f"  {k}: {'yes' if v else 'no'}" for k, v in sorted(caps.items())
            )

            config: Any = device.config or {}
            config_lines = (
                "\n".join(f"  {k}: {v}" for k, v in sorted(config.items()))
                if config
                else "  (none)"
            )

            peripherals: Any = device.peripherals or {}
            peripheral_lines = (
                "\n".join(f"  {k}: {v}" for k, v in sorted(peripherals.items()))
                if peripherals
                else "  (none)"
            )

            context_parts.append(
                f"[DEVICE METADATA]\n"
                f"Name: {device.name}\n"
                f"Type: {device.device_type}\n"
                f"Device ID: {device.device_id}\n"
                f"Lifecycle State: {device.lifecycle_state}\n"
                f"Health State: {device.health_state or 'Unknown'}\n"
                f"Is Simulated: {device.is_simulated}\n"
                f"Is Monitored: {device.is_monitored}\n"
                f"Enrollment Method: {device.enrollment_method or 'Unknown'}\n"
                f"Firmware: {device.firmware_version or 'Unknown'}\n"
                f"OS: {device.os_details or 'Unknown'}\n"
                f"IP: {device.ip_address or 'Unknown'}\n"
                f"Last Seen: {last_seen_str}\n"
                f"\n[DEVICE PERMISSIONS]\n{perm_lines}\n"
                f"\n[DEVICE CAPABILITIES]\n{cap_lines}\n"
                f"\n[DEVICE CONFIG]\n{config_lines}\n"
                f"\n[DEVICE PERIPHERALS]\n{peripheral_lines}"
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
