"""API endpoints for device job reporting.

Devices (or emulators mimicking them) create and update job records here so the
Dashboard's "Job History" tab can display real-time device activity.
"""

import logging
import uuid
from typing import Any, Dict, Optional, cast

from fastapi import APIRouter, Depends, HTTPException

from homepot.app.auth_utils import get_current_device
from homepot.app.schemas.agent import AgentJobRequest, AgentJobUpdateRequest
from homepot.database import get_database_service
from homepot.models import Device, Job, JobStatus

logger = logging.getLogger(__name__)
router = APIRouter()

# System user used for device-generated jobs (seed admin, id=1)
SYSTEM_USER_ID = 1


def _valid_update_status(status: str) -> Optional[JobStatus]:
    try:
        candidate = JobStatus(status)
    except ValueError:
        return None
    if candidate in {JobStatus.COMPLETED, JobStatus.FAILED}:
        return candidate
    return None


@router.post("/jobs", tags=["Agent"])
async def report_job(
    payload: AgentJobRequest,
    current_device: Device = Depends(get_current_device),
) -> Dict[str, Any]:
    """Create a pending job record linked to the authenticated device."""
    logger.info("Job report received for device_id=%s", payload.device_id)
    if current_device.device_id != payload.device_id:
        raise HTTPException(
            status_code=403,
            detail="Authenticated device does not match payload device_id",
        )
    try:
        db_service = await get_database_service()
        job: Job = await db_service.create_job(
            job_id=str(uuid.uuid4()),
            action=payload.action,
            description=payload.description,
            site_id=cast(Any, current_device.site_id),
            device_id=cast(Any, current_device.id),
            created_by=SYSTEM_USER_ID,
            priority=payload.priority,
            payload=payload.payload,
        )
        return {
            "status": "success",
            "data": {
                "job_id": job.job_id,
                "action": job.action,
                "status": job.status,
                "priority": job.priority,
                "created_at": job.created_at.isoformat(),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create device job: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/jobs/{job_id}", tags=["Agent"])
async def update_job(
    job_id: str,
    payload: AgentJobUpdateRequest,
    current_device: Device = Depends(get_current_device),
) -> Dict[str, Any]:
    """Update the status of a device job (completed/failed)."""
    logger.info(
        "Job update received for device_id=%s job_id=%s", payload.device_id, job_id
    )
    if current_device.device_id != payload.device_id:
        raise HTTPException(
            status_code=403,
            detail="Authenticated device does not match payload device_id",
        )
    new_status = _valid_update_status(payload.status)
    if new_status is None:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported job status '{payload.status}'",
        )
    try:
        db_service = await get_database_service()
        job = await db_service.get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.device_id != cast(Any, current_device.id):
            raise HTTPException(
                status_code=403, detail="Job does not belong to this device"
            )

        updated = await db_service.update_job_status(
            job_id=job_id,
            status=new_status,
            result=payload.result,
            error_message=payload.error_message,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Job not found")

        return {"status": "success", "message": f"Job updated to '{payload.status}'"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update device job: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
