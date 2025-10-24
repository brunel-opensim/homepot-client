"""API endpoints for managing jobs in the HomePot system."""

import logging
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from homepot_client.audit import AuditEventType, get_audit_logger
from homepot_client.client import HomepotClient
from homepot_client.models import JobPriority
from homepot_client.orchestrator import get_job_orchestrator

client_instance: Optional[HomepotClient] = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


router = APIRouter()


class JobStatusResponse(BaseModel):
    """Response model for job status."""

    job_id: str
    action: str
    status: str
    priority: str
    site_id: Optional[str] = None
    segment: Optional[str] = None
    config_url: Optional[str] = None
    config_version: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict] = None
    error_message: Optional[str] = None


# Pydantic models for API requests/responses
class CreateJobRequest(BaseModel):
    """Request model for creating a new job."""

    action: str = "Update POS payment config"
    description: Optional[str] = None
    config_url: Optional[str] = None
    config_version: Optional[str] = None
    priority: str = JobPriority.HIGH

    class Config:
        """Pydantic model configuration with example data."""

        schema_extra = {
            "example": {
                "action": "Update POS payment config",
                "description": "Fix payment gateway configuration for site-123",
                "priority": "high",
            }
        }


@router.post("/sites/{site_id}/jobs", tags=["Jobs"], response_model=Dict[str, str])
async def create_pos_config_job(
    site_id: str, job_request: CreateJobRequest
) -> Dict[str, str]:
    """Create a POS configuration update job (Step 1-2 from scenario).

    This endpoint implements:
    1. Tech logs in and selects site → Action: "Update POS payment config"
    2. Core API enqueues a job to segment: site-123/pos-terminals
    """
    try:
        orchestrator = await get_job_orchestrator()

        # Create the job using orchestrator
        job_id = await orchestrator.create_pos_config_update_job(
            site_id=site_id,
            action=job_request.action,
            description=job_request.description,
            config_url=job_request.config_url,
            config_version=job_request.config_version,
            priority=job_request.priority,
        )

        # Log audit event
        audit_logger = get_audit_logger()
        await audit_logger.log_event(
            AuditEventType.JOB_CREATED,
            f"Job {job_id} created for site {site_id}: {job_request.action}",
            # job_id would need to be resolved to database ID - simplified for demo
            event_metadata={
                "job_id": job_id,
                "site_id": site_id,
                "action": job_request.action,
                "description": job_request.description,
                "config_url": job_request.config_url,
                "config_version": job_request.config_version,
                "priority": job_request.priority,
            },
        )

        logger.info(f"Created job {job_id} for site {site_id}")
        return {
            "message": f"Job created successfully for site {site_id}",
            "job_id": job_id,
            "site_id": site_id,
            "action": job_request.action,
            "status": "queued",
        }

    except ValueError:
        raise HTTPException(
            status_code=404, detail="Operation failed. Please check server logs."
        )
    except Exception as e:
        logger.error(f"Failed to create job: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to create job. Please check server logs."
        )


@router.get("/jobs/{job_id}", tags=["Jobs"], response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Get job status and details (real-time tracking)."""
    try:
        orchestrator = await get_job_orchestrator()

        job_status = await orchestrator.get_job_status(job_id)
        if not job_status:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        return JobStatusResponse(**job_status)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to get job status. Please check server logs.",
        )
