"""Centralized error logging utility for AI training data collection.

This module provides a unified interface for logging errors to the error_logs
table for AI analysis and system health monitoring.
"""

from datetime import datetime
import logging
import traceback
from typing import Any, Dict, Optional

from homepot.app.models.AnalyticsModel import ErrorLog
from homepot.database import get_database_service

logger = logging.getLogger(__name__)


async def log_error(
    category: str,
    severity: str,
    error_message: str,
    error_code: Optional[str] = None,
    exception: Optional[Exception] = None,
    endpoint: Optional[str] = None,
    user_id: Optional[str] = None,
    device_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """Log an error to the error_logs table for AI training.

    Args:
        category: Error category (api, database, external_service, validation)
        severity: Error severity (critical, error, warning, info)
        error_message: Human-readable error message
        error_code: Optional error code for categorization
        exception: Optional exception object to extract stack trace
        endpoint: API endpoint where error occurred
        user_id: User ID if available
        device_id: Device ID if available
        context: Additional context data
    """
    try:
        # Extract stack trace if exception provided
        stack_trace = None
        if exception:
            stack_trace = "".join(
                traceback.format_exception(
                    type(exception), exception, exception.__traceback__
                )
            )

        # Prepare context data
        error_context = context or {}
        if exception:
            error_context["exception_type"] = type(exception).__name__
        if device_id:
            error_context["original_device_id"] = device_id

        # Log to database
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            error_log = ErrorLog(
                timestamp=datetime.utcnow(),
                category=category,
                severity=severity,
                error_code=error_code,
                error_message=error_message,
                stack_trace=stack_trace,
                endpoint=endpoint,
                user_id=user_id,
                # device_id removed from model because it doesn't exist in DB
                context=error_context,
            )
            session.add(error_log)
            logger.debug(
                f"Logged {severity} error in category {category}: {error_message}"
            )

    except Exception as log_error:
        # Don't let error logging break the application
        logger.error(f"Failed to log error to database: {log_error}", exc_info=True)
