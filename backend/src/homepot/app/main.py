"""Imports for the app."""

import logging
from logging.handlers import RotatingFileHandler
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from homepot.app.api.API_v1.Api import api_v1_router
from homepot.app.middleware.analytics import AnalyticsMiddleware
from homepot.app.utils.limiter import limiter
from homepot.config import get_settings

# Configure Log Rotation
# This ensures backend.log doesn't grow infinitely
# Assumes the application is run from the 'backend' directory
try:
    log_dir = os.path.abspath(os.path.join(os.getcwd(), "../logs"))
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "backend.log")

    # Rotate at 10MB, keep 5 backups
    handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    # Configure root logger to capture all logs (including uvicorn)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

    # Remove default handlers to avoid duplication if needed,
    # but keeping them ensures console output still works for development.

except Exception as e:
    print(f"Failed to setup log rotation: {e}")

cors_origins = get_settings().cors.cors_origins

# App declaration
app = FastAPI(
    title="HOMEPOT Client API",
    description="REST API for HOMEPOT device management and monitoring",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    # lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore


# Create tables
# database.CreateTables()

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Analytics middleware for automatic API request logging
app.add_middleware(AnalyticsMiddleware, enable_logging=True)


# Add to openAPI documentation
# config.idp.add_swagger_config(app)


# TEST BASE URL API (insecure/test)
@app.get("/")
def root() -> dict:
    """Root endpoint to test if the API is alive."""
    return {"message": "I Am Alive"}


# Incluse all routes from API v1
app.include_router(api_v1_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")  # nosec B104
