"""API endpoint for storing and retrieving agent telemetry metrics."""

import logging
from typing import Any, Dict, List, Union

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from homepot.app.api.API_v1.Endpoints.agent_permission_gate import require_monitor
from homepot.app.auth_utils import get_current_device
from homepot.app.schemas.agent import AgentTelemetryRequest
from homepot.app.services.agent_service import AgentService
from homepot.database import get_db
from homepot.models import Device

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/telemetry", tags=["Agent"])
def save_telemetry(
    payload: Union[AgentTelemetryRequest, List[AgentTelemetryRequest]],
    current_device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Save one or many telemetry records for a device."""
    try:
        if isinstance(payload, list) and not payload:
            raise ValueError("Telemetry payload list cannot be empty")

        telemetry_count = len(payload) if isinstance(payload, list) else 1
        device_ref = (
            payload[0].device_id if isinstance(payload, list) else payload.device_id
        )
        logger.info(
            "Telemetry request received for device_id=%s count=%s",
            device_ref,
            telemetry_count,
        )
        device_ids = (
            {item.device_id for item in payload}
            if isinstance(payload, list)
            else {payload.device_id}
        )
        if device_ids != {current_device.device_id}:
            raise HTTPException(
                status_code=403,
                detail="Authenticated device does not match payload device_id",
            )

        service = AgentService(db)
        result = service.save_telemetry(payload)
        return {
            "status": "success",
            "message": "Telemetry saved successfully",
            "data": result,
        }
    except (LookupError, ValueError) as e:
        logger.error("Telemetry validation failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected telemetry error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{device_id}/metrics", tags=["Agent"])
def get_latest_metrics(
    device_id: str,
    current_device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return the latest telemetry metrics for the authenticated device.

    The device authenticates via ``X-Device-ID`` and ``X-API-Key`` headers
    and can only read its own metrics (Monitor-gated).
    """
    try:
        if current_device.device_id != device_id:
            raise HTTPException(
                status_code=403,
                detail="Authenticated device can only read its own metrics",
            )
        require_monitor(current_device)
        service = AgentService(db)
        result = service.get_latest_metrics(device_id)
        return {
            "status": "success",
            "message": "Latest device metrics fetched successfully",
            "data": result,
        }
    except LookupError as e:
        logger.error("Metrics lookup failed: %s", e)
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected metrics error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{device_id}/metrics/history", tags=["Agent"])
def get_metrics_history(
    device_id: str,
    limit: int = 100,
    current_device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return a time-ordered sample of telemetry metrics for a device.

    The device authenticates via ``X-Device-ID`` and ``X-API-Key`` headers
    and can only read its own history (Monitor-gated).
    """
    try:
        if current_device.device_id != device_id:
            raise HTTPException(
                status_code=403,
                detail="Authenticated device can only read its own metrics",
            )
        require_monitor(current_device)
        service = AgentService(db)
        result = service.get_metrics_history(device_id, limit=limit)
        return {
            "status": "success",
            "message": "Device metrics history fetched successfully",
            "data": result,
        }
    except LookupError as e:
        logger.error("Metrics history lookup failed: %s", e)
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected metrics history error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
