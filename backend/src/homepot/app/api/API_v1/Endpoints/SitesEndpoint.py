"""API endpoints for managing sites in the HomePot system."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from homepot.audit import AuditEventType, get_audit_logger
from homepot.client import HomepotClient
from homepot.database import get_database_service
from homepot.error_logger import log_error

client_instance: Optional[HomepotClient] = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


router = APIRouter()


class SiteHealthResponse(BaseModel):
    """Response model for site health status."""

    site_id: str
    total_devices: int
    healthy_devices: int
    offline_devices: int
    error_devices: int
    health_percentage: float
    status_summary: str
    devices: List[Dict]
    last_updated: str


class CreateSiteRequest(BaseModel):
    """Request model for creating a new site."""

    site_id: str
    name: str
    description: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "site_id": "site-123",
                "name": "Main Retail Store",
                "description": "Primary retail location with 5 POS terminals",
                "location": "London, UK",
                "latitude": 51.5074,
                "longitude": -0.1278,
            }
        }
    )


def get_client() -> HomepotClient:
    """Dependency to get the client instance."""
    if client_instance is None:
        raise HTTPException(status_code=503, detail="Client not available")
    return client_instance


@router.post("/", tags=["Sites"], response_model=Dict[str, str])
async def create_site(site_request: CreateSiteRequest) -> Dict[str, str]:
    """Create a new site for device management."""
    try:
        db_service = await get_database_service()

        # Check if site already exists
        existing_site = await db_service.get_site_by_site_id(site_request.site_id)
        if existing_site:
            raise HTTPException(
                status_code=409, detail=f"Site {site_request.site_id} already exists"
            )

        # Create new site
        site = await db_service.create_site(
            site_id=site_request.site_id,
            name=site_request.name,
            description=site_request.description,
            location=site_request.location,
            latitude=site_request.latitude,
            longitude=site_request.longitude,
        )

        # Log audit event
        audit_logger = get_audit_logger()
        await audit_logger.log_event(
            AuditEventType.SITE_CREATED,
            f"Site '{site.name}' created with ID {site.site_id}",
            site_id=int(site.id),
            new_values={
                "site_id": str(site.site_id),
                "name": str(site.name),
                "description": str(site.description),
                "location": site.location,
                "latitude": site.latitude,
                "longitude": site.longitude,
            },
        )

        logger.info(f"Created site {site.site_id}")
        return {
            "message": f"Site {site.site_id} created successfully",
            "site_id": str(site.site_id),
            "name": str(site.name),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create site: {e}", exc_info=True)
        # Log error for AI training
        await log_error(
            category="api",
            severity="error",
            error_message="Failed to create site",
            exception=e,
            endpoint="/api/v1/sites",
            context={"site_data": site_request.model_dump()},
        )
        raise HTTPException(
            status_code=500, detail="Failed to create site. Please check server logs."
        )


@router.get("/", tags=["Sites"])
async def list_sites() -> Dict[str, List[Dict]]:
    """List all sites."""
    try:
        db_service = await get_database_service()

        # For demo, we'll create a simple query (in real app, add pagination)
        from sqlalchemy import select

        from homepot.models import Device, Site

        async with db_service.get_session() as session:
            result = await session.execute(
                select(Site)
                .where(Site.is_active.is_(True))
                .order_by(Site.created_at.desc())
            )
            sites = result.scalars().all()

            site_list = []
            for site in sites:
                # Fetch devices for this site to determine status and OS types
                devices_result = await session.execute(
                    select(Device).where(
                        Device.site_id == site.id, Device.is_active.is_(True)
                    )
                )
                devices = devices_result.scalars().all()

                # Determine status
                status = "Offline"
                if devices:
                    if any(d.status == "error" for d in devices):
                        status = "Warning"
                    elif any(d.status == "online" for d in devices):
                        status = "Online"

                # Collect OS types
                os_types = set()
                for device in devices:
                    if device.config and "os" in device.config:
                        os_types.add(device.config["os"])

                site_list.append(
                    {
                        "site_id": site.site_id,
                        "name": site.name,
                        "description": site.description,
                        "location": site.location,
                        "is_monitored": site.is_monitored,
                        "status": status,
                        "os_types": list(os_types),
                        "created_at": (
                            site.created_at.isoformat() if site.created_at else None
                        ),
                    }
                )

            return {"sites": site_list}

    except Exception as e:
        logger.error(f"Failed to list sites: {e}", exc_info=True)
        # Log error for AI training
        await log_error(
            category="api",
            severity="error",
            error_message="Failed to list sites",
            exception=e,
            endpoint="/api/v1/sites",
            context={"action": "list_sites"},
        )
        raise HTTPException(
            status_code=500, detail="Failed to list sites. Please check server logs."
        )


@router.get("/{site_id}", tags=["Sites"])
async def get_site(site_id: str) -> Dict[str, Any]:
    """Get a specific site by site_id."""
    try:
        db_service = await get_database_service()

        # Look up site by site_id
        site = await db_service.get_site_by_site_id(site_id)

        if not site:
            raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")

        return {
            "site_id": site.site_id,
            "name": site.name,
            "description": site.description,
            "location": site.location,
            "is_monitored": site.is_monitored,
            "is_active": site.is_active,
            "created_at": site.created_at.isoformat() if site.created_at else None,
            "updated_at": site.updated_at.isoformat() if site.updated_at else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get site {site_id}: {e}", exc_info=True)
        # Log error for AI training
        await log_error(
            category="api",
            severity="error",
            error_message=f"Failed to get site {site_id}",
            exception=e,
            endpoint=f"/api/v1/sites/{site_id}",
            context={"site_id": site_id, "action": "get_site"},
        )
        raise HTTPException(
            status_code=500, detail="Failed to get site. Please check server logs."
        )


@router.delete("/{site_id}", tags=["Sites"])
async def delete_site(site_id: str) -> Dict[str, str]:
    """Delete a site and ALL associated resources (metrics, logs, history)."""
    try:
        db_service = await get_database_service()
        from sqlalchemy import delete, select

        # Import analytics models for comprehensive cleanup
        from homepot.app.models.AnalyticsModel import (
            APIRequestLog,
            ConfigurationHistory,
            DeviceMetrics,
            DeviceStateHistory,
            ErrorLog,
            JobOutcome,
            PushNotificationLog,
            SiteOperatingSchedule,
        )
        from homepot.models import (
            AuditLog,
            Device,
            DeviceCommand,
            HealthCheck,
            Job,
            Site,
        )

        async with db_service.get_session() as session:
            # 1. Get the site
            result = await session.execute(select(Site).where(Site.site_id == site_id))
            site = result.scalars().first()

            if not site:
                raise HTTPException(
                    status_code=404, detail=f"Site '{site_id}' not found"
                )

            # Capture site details before deletion for audit logging (of the deletion event itself)
            site_pk = site.id
            site_name = site.name
            site_str_id = site.site_id

            # Get all devices for this site to clean up their related data
            # We need both Integer IDs (for FKs) and String IDs (for Analytics)
            devices_result = await session.execute(
                select(Device).where(Device.site_id == site.site_id)
            )
            devices = devices_result.scalars().all()
            device_pk_ids = [d.id for d in devices]
            device_str_ids = [d.device_id for d in devices]

            # --- PHASE 1: Clean up Device-Specific Analytics & History ---
            if device_str_ids:
                # Device Metrics
                await session.execute(
                    delete(DeviceMetrics).where(
                        DeviceMetrics.device_id.in_(device_str_ids)
                    )
                )
                # Device State History
                await session.execute(
                    delete(DeviceStateHistory).where(
                        DeviceStateHistory.device_id.in_(device_str_ids)
                    )
                )
                # Push Notification Logs
                await session.execute(
                    delete(PushNotificationLog).where(
                        PushNotificationLog.device_id.in_(device_str_ids)
                    )
                )
                # Error Logs (linked to devices)
                await session.execute(
                    delete(ErrorLog).where(ErrorLog.device_id.in_(device_str_ids))
                )
                # Job Outcomes (linked to devices)
                await session.execute(
                    delete(JobOutcome).where(JobOutcome.device_id.in_(device_str_ids))
                )
                # Configuration History (linked to devices)
                await session.execute(
                    delete(ConfigurationHistory).where(
                        ConfigurationHistory.entity_type == "device",
                        ConfigurationHistory.entity_id.in_(device_str_ids),
                    )
                )

            # --- PHASE 2: Clean up Site-Specific Analytics & History ---
            # Site Operating Schedules
            await session.execute(
                delete(SiteOperatingSchedule).where(
                    SiteOperatingSchedule.site_id == site_str_id
                )
            )
            # Configuration History (linked to site)
            await session.execute(
                delete(ConfigurationHistory).where(
                    ConfigurationHistory.entity_type == "site",
                    ConfigurationHistory.entity_id == site_str_id,
                )
            )
            # API Request Logs (Best effort: matching endpoint path)
            # Deletes logs like /api/v1/sites/site-123...
            await session.execute(
                delete(APIRequestLog).where(
                    APIRequestLog.endpoint.like(f"%/{site_str_id}%")
                )
            )

            # --- PHASE 3: Clean up Core Relational Data ---
            if device_pk_ids:
                # Delete DeviceCommands
                await session.execute(
                    delete(DeviceCommand).where(
                        DeviceCommand.device_id.in_(device_pk_ids)
                    )
                )
                # Delete HealthChecks
                await session.execute(
                    delete(HealthCheck).where(HealthCheck.device_id.in_(device_pk_ids))
                )
                # Delete AuditLogs for devices
                await session.execute(
                    delete(AuditLog).where(AuditLog.device_id.in_(device_pk_ids))
                )

            # Delete AuditLogs for the site
            await session.execute(delete(AuditLog).where(AuditLog.site_id == site.id))

            # Get associated Jobs to delete their AuditLogs
            jobs_result = await session.execute(
                select(Job.id).where(Job.site_id == site.id)
            )
            job_ids = jobs_result.scalars().all()

            if job_ids:
                # Delete AuditLogs for jobs
                await session.execute(
                    delete(AuditLog).where(AuditLog.job_id.in_(job_ids))
                )

            # Delete associated Jobs
            await session.execute(delete(Job).where(Job.site_id == site.id))

            # Delete associated Devices
            await session.execute(delete(Device).where(Device.site_id == site.site_id))

            # Delete the Site itself
            await session.delete(site)
            await session.commit()

            # Log audit event (This will be the ONLY record left of this site,
            # and it won't be linked via FK, so it's safe)
            audit_logger = get_audit_logger()
            await audit_logger.log_event(
                AuditEventType.SITE_DELETED,
                f"Site '{site_name}' and ALL associated data (metrics, logs) deleted",
                site_id=None,
                old_values={
                    "site_id": site_str_id,
                    "name": site_name,
                    "db_id": site_pk,
                    "cleanup_policy": "hard_delete_all_associated_data",
                },
            )

            return {
                "message": f"Site {site_id} and all associated data deleted successfully"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete site {site_id}: {e}", exc_info=True)
        await log_error(
            category="api",
            severity="error",
            error_message=f"Failed to delete site {site_id}",
            exception=e,
            endpoint=f"/api/v1/sites/{site_id}",
            context={"site_id": site_id, "action": "delete_site"},
        )
        raise HTTPException(status_code=500, detail="Failed to delete site")


@router.put("/{site_id}/monitor", tags=["Sites"])
async def toggle_site_monitor(site_id: str, monitor: bool) -> Dict[str, Any]:
    """Toggle the monitoring status of a site."""
    try:
        db_service = await get_database_service()

        # We need to implement update_site in db_service or do it manually here
        # For now, let's do it manually via session
        from sqlalchemy import select

        from homepot.models import Site

        async with db_service.get_session() as session:
            result = await session.execute(select(Site).where(Site.site_id == site_id))
            site = result.scalars().first()

            if not site:
                raise HTTPException(
                    status_code=404, detail=f"Site '{site_id}' not found"
                )

            site.is_monitored = monitor  # type: ignore
            await session.commit()

            return {
                "message": f"Site monitoring {'enabled' if monitor else 'disabled'}",
                "site_id": site.site_id,
                "is_monitored": site.is_monitored,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update site monitor status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
