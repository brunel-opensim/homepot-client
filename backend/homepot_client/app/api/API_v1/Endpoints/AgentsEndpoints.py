"""API endpoints for managing agents in the HomePot system."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

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


@router.get("/agents", tags=["Agents"])
async def list_agents() -> Dict[str, List[Dict]]:
    """List all active POS agents and their status."""
    try:
        from homepot_client.agents import get_agent_manager

        agent_manager = await get_agent_manager()
        agents_status = await agent_manager.get_all_agents_status()

        return {"agents": agents_status}

    except Exception as e:
        logger.error(f"Failed to list agents: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to list agents. Please check server logs."
        )


@router.get("/agents/{device_id}", tags=["Agents"])
async def get_agent_status(device_id: str) -> Dict[str, Any]:
    """Get detailed status of a specific POS agent."""
    try:
        from homepot_client.agents import get_agent_manager

        agent_manager = await get_agent_manager()
        agent_status = await agent_manager.get_agent_status(device_id)

        if not agent_status:
            raise HTTPException(
                status_code=404, detail=f"Agent for device {device_id} not found"
            )

        return agent_status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to get agent status. Please check server logs.",
        )


@router.post("/agents/{device_id}/push", tags=["Agents"])
async def send_push_notification(
    device_id: str, notification_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Send a direct push notification to a POS agent for testing."""
    try:
        from homepot_client.agents import get_agent_manager

        agent_manager = await get_agent_manager()
        response = await agent_manager.send_push_notification(
            device_id, notification_data
        )

        if not response:
            raise HTTPException(
                status_code=404, detail=f"Agent for device {device_id} not found"
            )

        return {
            "message": f"Push notification sent to {device_id}",
            "device_id": device_id,
            "response": response,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send push notification: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to send push notification. Please check server logs.",
        )
