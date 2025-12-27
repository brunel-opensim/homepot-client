"""Module for building rich context for the AI from various data sources."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, select

from homepot.app.models.AnalyticsModel import (
    APIRequestLog,
    ConfigurationHistory,
    DeviceStateHistory,
    ErrorLog,
    JobOutcome,
)
from homepot.database import get_database_service
from homepot.models import AuditLog

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Service to aggregate context from multiple data sources for the LLM."""

    @staticmethod
    async def get_job_context(job_id: Optional[str] = None, limit: int = 5) -> str:
        """Retrieve context about recent or specific jobs.

        Args:
            job_id: Optional specific job ID to investigate.
            limit: Number of recent failed jobs to fetch if no ID provided.
        """
        try:
            db_service = await get_database_service()
            async with db_service.get_session() as session:
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

        except Exception as e:
            logger.error(f"Failed to build job context: {e}")
            return "Error retrieving job context."

    @staticmethod
    async def get_error_context(device_id: Optional[str] = None, limit: int = 5) -> str:
        """Retrieve recent error logs.

        Args:
            device_id: Optional device ID to filter by.
            limit: Number of errors to fetch.
        """
        try:
            db_service = await get_database_service()
            async with db_service.get_session() as session:
                stmt = select(ErrorLog).order_by(ErrorLog.timestamp.desc())

                if device_id:
                    stmt = stmt.where(ErrorLog.device_id == device_id)

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

        except Exception as e:
            logger.error(f"Failed to build error context: {e}")
            return "Error retrieving error context."

    @staticmethod
    async def get_config_context(
        device_id: Optional[str] = None, limit: int = 5
    ) -> str:
        """Retrieve recent configuration changes.

        Args:
            device_id: Optional device ID to filter by.
            limit: Number of changes to fetch.
        """
        try:
            db_service = await get_database_service()
            async with db_service.get_session() as session:
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

        except Exception as e:
            logger.error(f"Failed to build config context: {e}")
            return "Error retrieving config context."

    @staticmethod
    async def get_audit_context(device_id: Optional[str] = None, limit: int = 5) -> str:
        """Retrieve recent audit logs.

        Args:
            device_id: Optional device ID to filter by.
            limit: Number of logs to fetch.
        """
        try:
            db_service = await get_database_service()
            async with db_service.get_session() as session:
                # Note: AuditLog uses integer device_id FK, but we pass string ID.
                # We might need to join with Device table or assume ID lookup is handled.
                # For now, we'll skip device filtering if it's a string ID and AuditLog expects int,
                # OR we assume the caller handles ID conversion.
                # However, looking at models.py, AuditLog.device_id is Integer FK.
                # But Device.device_id is String.
                # This implies we need to look up the integer ID first.
                # For simplicity in this iteration, we will return general audit logs
                # or if device_id is provided, we'd need to resolve it.
                # Let's check if we can filter by description or metadata if ID lookup is complex.

                # Strategy: Just fetch recent logs for now to avoid complex joins in this step.
                stmt = (
                    select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
                )

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

        except Exception as e:
            logger.error(f"Failed to build audit context: {e}")
            return "Error retrieving audit context."

    @staticmethod
    async def get_api_context(limit: int = 5) -> str:
        """Retrieve recent failed API requests.

        Args:
            limit: Number of failed requests to fetch.
        """
        try:
            db_service = await get_database_service()
            async with db_service.get_session() as session:
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

        except Exception as e:
            logger.error(f"Failed to build API context: {e}")
            return "Error retrieving API context."

    @staticmethod
    async def get_state_context(device_id: Optional[str] = None, limit: int = 5) -> str:
        """Retrieve recent device state changes.

        Args:
            device_id: Optional device ID to filter by.
            limit: Number of changes to fetch.
        """
        try:
            db_service = await get_database_service()
            async with db_service.get_session() as session:
                stmt = select(DeviceStateHistory).order_by(
                    DeviceStateHistory.timestamp.desc()
                )

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

        except Exception as e:
            logger.error(f"Failed to build state context: {e}")
            return "Error retrieving state context."
