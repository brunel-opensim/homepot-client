"""API endpoints for managing jobs in the HomePot system."""

import logging
from datetime import datetime
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from homepot.app.models.AnalyticsModel import ConfigurationHistory
from homepot.audit import AuditEventType, get_audit_logger
from homepot.client import HomepotClient
from homepot.database import get_database_service
from homepot.models import JobPriority
from homepot.orchestrator import get_job_orchestrator

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
    device_id: Optional[str] = None  # Added to support device-specific jobs

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "action": "Update POS payment config",
                "description": "Fix payment gateway configuration for site-123",
                "priority": "high",
            }
        }
    )


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
            device_id=job_request.device_id,
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

        # Log configuration change intent for AI training
        if job_request.config_url and job_request.config_version:
            try:
                db_service = await get_database_service()
                async with db_service.get_session() as session:
                    config_history = ConfigurationHistory(
                        timestamp=datetime.utcnow(),
                        entity_type="site",
                        entity_id=site_id,
                        parameter_name="config_update_job",
                        old_value=None,
                        new_value={
                            "job_id": job_id,
                            "action": job_request.action,
                            "config_url": job_request.config_url,
                            "config_version": job_request.config_version,
                        },
                        changed_by="api_user",
                        change_reason=job_request.description,
                        change_type="manual",
                    )
                    session.add(config_history)
                    logger.debug(
                        f"Logged configuration change intent for site {site_id}"
                    )
            except Exception as log_err:
                logger.error(f"Failed to log configuration history: {log_err}")

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


@router.get("/{job_id}", tags=["Jobs"], response_model=JobStatusResponse)
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
