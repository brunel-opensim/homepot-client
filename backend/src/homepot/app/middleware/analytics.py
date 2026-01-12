"""Middleware for automatic API request logging and performance monitoring."""

import logging
import time
from typing import Callable, Optional

from fastapi import Request, Response
import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from homepot.app.auth_utils import ALGORITHM, COOKIE_NAME, SECRET_KEY
from homepot.app.models.AnalyticsModel import APIRequestLog
from homepot.database import SessionLocal

logger = logging.getLogger(__name__)


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

        # Skip logging for health check and metrics endpoints to avoid noise
        skip_paths = ["/health", "/metrics", "/docs", "/openapi.json", "/favicon.ico"]
        if any(request.url.path.startswith(path) for path in skip_paths):
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

        # Log to database asynchronously (non-blocking)
        try:
            self._log_request(
                endpoint=endpoint,
                method=method,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except Exception as e:
            # Don't fail the request if logging fails
            logger.error(f"Failed to log API request: {str(e)}")

        return response

    def _log_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: float,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Log request to database."""
        db = SessionLocal()
        try:
            log_entry = APIRequestLog(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                response_time_ms=response_time_ms,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            logger.error(f"Error writing API log: {str(e)}")
            db.rollback()
        finally:
            db.close()
