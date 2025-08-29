"""
HOMEPOT Client FastAPI Application.

This module provides the main FastAPI application for the HOMEPOT client,
exposing REST API endpoints for device management and monitoring.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from homepot_client.client import HomepotClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global client instance
client_instance: HomepotClient = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    global client_instance

    # Startup
    logger.info("Starting HOMEPOT Client application...")
    client_instance = HomepotClient()
    try:
        await client_instance.connect()
        logger.info("HOMEPOT Client connected successfully")
    except Exception as e:
        logger.warning(f"Failed to connect client on startup: {e}")

    yield

    # Shutdown
    logger.info("Shutting down HOMEPOT Client application...")
    if client_instance and client_instance.is_connected():
        await client_instance.disconnect()
        logger.info("HOMEPOT Client disconnected")


# Create FastAPI application
app = FastAPI(
    title="HOMEPOT Client API",
    description="REST API for HOMEPOT device management and monitoring",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_client() -> HomepotClient:
    """Dependency to get the client instance."""
    if client_instance is None:
        raise HTTPException(status_code=503, detail="Client not available")
    return client_instance


@app.get("/", tags=["Root"])
async def root() -> Dict[str, str]:
    """Root endpoint providing basic information."""
    return {
        "message": "HOMEPOT Client API",
        "version": "0.1.0",
        "docs": "/docs",
        "status": "operational",
    }


@app.get("/health", tags=["Health"])
async def health_check(client: HomepotClient = Depends(get_client)) -> Dict[str, Any]:
    """Health check endpoint for monitoring and load balancers."""
    try:
        is_connected = client.is_connected()
        version = await client.get_version()

        return {
            "status": "healthy" if is_connected else "degraded",
            "client_connected": is_connected,
            "version": version,
            "timestamp": asyncio.get_event_loop().time(),
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": asyncio.get_event_loop().time(),
        }


@app.get("/status", tags=["Client"])
async def get_status(client: HomepotClient = Depends(get_client)) -> Dict[str, Any]:
    """Get detailed client status information."""
    try:
        is_connected = client.is_connected()
        version = await client.get_version()

        return {
            "connected": is_connected,
            "version": version,
            "uptime": asyncio.get_event_loop().time(),
            "client_type": "HOMEPOT Client",
        }
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {e}")


@app.post("/connect", tags=["Client"])
async def connect_client(client: HomepotClient = Depends(get_client)) -> Dict[str, str]:
    """Connect the HOMEPOT client."""
    try:
        if client.is_connected():
            return {"message": "Client already connected", "status": "connected"}

        await client.connect()
        return {"message": "Client connected successfully", "status": "connected"}
    except Exception as e:
        logger.error(f"Connect failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect: {e}")


@app.post("/disconnect", tags=["Client"])
async def disconnect_client(
    client: HomepotClient = Depends(get_client),
) -> Dict[str, str]:
    """Disconnect the HOMEPOT client."""
    try:
        if not client.is_connected():
            return {"message": "Client already disconnected", "status": "disconnected"}

        await client.disconnect()
        return {"message": "Client disconnected successfully", "status": "disconnected"}
    except Exception as e:
        logger.error(f"Disconnect failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to disconnect: {e}")


@app.get("/version", tags=["Client"])
async def get_version(client: HomepotClient = Depends(get_client)) -> Dict[str, str]:
    """Get the client version information."""
    try:
        version = await client.get_version()
        return {"version": version}
    except Exception as e:
        logger.error(f"Version check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get version: {e}")


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status_code": exc.status_code},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500, content={"detail": "Internal server error", "status_code": 500}
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
