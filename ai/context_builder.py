"""Module for building rich context for the AI from various data sources."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_

from homepot.app.models.AnalyticsModel import ErrorLog, JobOutcome
from homepot.database import get_database_service

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
                            JobOutcome.timestamp >= cutoff
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
                        f"- {error.timestamp.isoformat()} [{error.severity}]: {error.error_message} ({error.category})"
                    )
                return "\n".join(context_lines)

        except Exception as e:
            logger.error(f"Failed to build error context: {e}")
            return "Error retrieving error context."
