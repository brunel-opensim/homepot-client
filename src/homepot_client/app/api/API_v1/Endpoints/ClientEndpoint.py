import asyncio
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from homepot_client.client import HomepotClient

client_instance: Optional[HomepotClient] = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


router = APIRouter()


def get_client() -> HomepotClient:
    """Dependency to get the client instance."""
    if client_instance is None:
        raise HTTPException(status_code=503, detail="Client not available")
    return client_instance


@router.get("/status", tags=["Client"])
async def get_status(client: HomepotClient = Depends(get_client)) -> Dict[str, Any]:
    """Get detailed client status information."""
    try:
        is_connected = client.is_connected()
        version = client.get_version()

        return {
            "connected": is_connected,
            "version": version,
            "uptime": asyncio.get_event_loop().time(),
            "client_type": "HOMEPOT Client",
        }
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {e}")


@router.post("/connect", tags=["Client"])
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


@router.post("/disconnect", tags=["Client"])
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


@router.get("/version", tags=["Client"])
async def get_version(client: HomepotClient = Depends(get_client)) -> Dict[str, str]:
    """Get the client version information."""
    try:
        version = client.get_version()
        return {"version": version}
    except Exception as e:
        logger.error(f"Version check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get version: {e}")
