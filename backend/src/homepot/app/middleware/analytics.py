"""Middleware for automatic API request logging and performance monitoring."""

import asyncio
import logging
import time
from typing import Callable, Optional

from fastapi import Request, Response
import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from homepot.app.auth_utils import ALGORITHM, COOKIE_NAME, SECRET_KEY
from homepot.app.models.AnalyticsModel import APIRequestLog

logger = logging.getLogger(__name__)

# Paths that are never written to the API request log.
#
# The first group are pure noise (health probes, metrics scraping, docs).
# The second group is the high-frequency machine-to-machine reporting surface:
# every registered device posts heartbeat/telemetry/logs/alerts on a 30s
# cadence, and those requests already land in their own dedicated tables
# (``device_metrics``, ``health_checks``, etc.). Writing an ``api_request_logs``
# row for each one multiplies write load for no analytical value and was a
# major contributor to the production database pool-exhaustion outages.
#
# Matching is by ``startswith`` on the full path (which includes the
# ``/api/v1`` prefix), so each entry here must cover the prefixed form too.
_SKIP_PATHS = (
    "/health",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/favicon.ico",
    # Device/agent machine-to-machine reporting (30s cadence per device).
    "/api/v1/agent/",
    # API-level liveness used by load balancers and monitoring.
    "/api/v1/health",
    "/api/v1/metrics",
)

# Cap the number of concurrent analytics writes. Analytics logging is
# best-effort: when this many writes are already in flight, further samples are
# dropped rather than queueing up and starving the shared connection pool (and,
# transitively, real request traffic) under load.
_ANALYTICS_MAX_CONCURRENT_WRITES = 16
_analytics_write_semaphore = asyncio.Semaphore(_ANALYTICS_MAX_CONCURRENT_WRITES)


class AnalyticsMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically log all API requests for analytics."""

    def __init__(self, app: ASGIApp, enable_logging: bool = True):
        """Initialize analytics middleware with optional logging control."""
        super().__init__(app)
        self.enable_logging = enable_logging

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:  # type: ignore[override]
        """Process request and log analytics data."""
        if not self.enable_logging:
            response: Response = await call_next(request)
            return response

        # Skip logging for health check, metrics, and machine-to-machine
        # endpoints to avoid noise and write amplification.
        if any(request.url.path.startswith(path) for path in _SKIP_PATHS):
            response = await call_next(request)
            return response

        # Record start time
        start_time = time.time()

        # Get request details
        method = request.method
        endpoint = request.url.path
        user_agent = request.headers.get("user-agent", "")
        ip_address: Optional[str] = request.client.host if request.client else None

        # Get user from auth header/cookie if available
        user_id: Optional[str] = None
        try:
            # Try to extract user from authorization header or cookie
            token = None
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

            if not token:
                token = request.cookies.get(COOKIE_NAME)

            if token:
                # Decode token to get user email
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                user_id = payload.get("sub")
        except Exception:
            # If token is invalid or expired, we just don't log the user_id
            # We don't want to block the request here (auth middleware handles 401s)
            pass

        # Process request
        response = await call_next(request)

        # Calculate response time
        response_time_ms = (time.time() - start_time) * 1000

        # Log to database asynchronously (non-blocking, best-effort). The write
        # runs as a detached task on the async engine, so it can never block
        # the event loop on a synchronous commit or exhaust a small sync pool —
        # the previous behaviour that stalled requests under load.
        try:
            asyncio.create_task(
                self._log_request(
                    endpoint=endpoint,
                    method=method,
                    status_code=response.status_code,
                    response_time_ms=response_time_ms,
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
            )
        except Exception as e:
            # Don't fail the request if scheduling the log fails
            logger.debug("Failed to schedule API request log: %s", e)

        return response

    async def _log_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: float,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Write one request-log row, dropping the sample under backpressure."""
        # Drop the sample if the write queue is already saturated. Analytics is
        # best-effort; never let it queue unbounded work against the pool.
        if _analytics_write_semaphore.locked():
            return

        async with _analytics_write_semaphore:
            try:
                from homepot.database import get_database_service

                db_service = await get_database_service()
                async with db_service.get_session() as session:
                    session.add(
                        APIRequestLog(
                            endpoint=endpoint,
                            method=method,
                            status_code=status_code,
                            response_time_ms=response_time_ms,
                            user_id=user_id,
                            ip_address=ip_address,
                            user_agent=user_agent,
                        )
                    )
                    # get_session() commits on clean exit and rolls back on error.
            except Exception as e:
                # Never raise out of the analytics path.
                logger.debug("Error writing API request log: %s", e)
