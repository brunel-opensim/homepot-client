"""API endpoints for managing sites in the HomePot system."""

import logging
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session as SASession

from homepot.app.auth_utils import (
    UserDict,
    get_accessible_site_ids,
    require_user,
    verify_site_access_for_user,
)
from homepot.app.schemas.permissions import os_family
from homepot.audit import AuditEventType, get_audit_logger

# Canonical site IDs live in the shared canonical_ids module (which also
# hosts canonical device IDs); re-export the previous public names so
# existing imports (e.g. seed_data, tests) keep working.
from homepot.canonical_ids import _SITE_ID_PATTERN as _SITE_ID_PATTERN  # noqa: F401
from homepot.canonical_ids import generate_site_id as generate_site_id
from homepot.client import HomepotClient
from homepot.database import get_database_service, get_db
from homepot.error_logger import log_error
from homepot.models import (
    Device,
    DeviceStatus,
    LifecycleState,
    Site,
    SiteLifecycleState,
    User,
)

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
    """Request model for creating a new site.

    ``site_id`` is auto-generated server-side (``SITE-XXXX-XXXX``), so a
    caller-name ``site_id`` is not required. It is still accepted for
    backwards compatibility but ignored in favour of the generated value.
    """

    site_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
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
async def create_site(
    site_request: CreateSiteRequest,
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, str]:
    """Create a new site for device management."""
    try:
        db_service = await get_database_service()

        site_id = generate_site_id()
        # Keep trying until we land on an unused id (collision is astronomically
        # unlikely with 4+4 unambiguous chars, but stay safe).
        while await db_service.get_site_by_site_id(site_id):
            site_id = generate_site_id()

        # Create new site
        site = await db_service.create_site(
            site_id=site_id,
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
async def list_sites(
    include_archived: bool = Query(
        False, description="Include archived (hidden) sites"
    ),
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, List[Dict]]:
    """List all sites (scoped to user's accessible sites).

    By default only active sites are returned. Pass ``include_archived=true``
    to also include archived (is_active=false) sites for the restore view.
    """
    try:
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )

        db_service = await get_database_service()

        async with db_service.get_session() as session:
            query = select(Site)
            if not include_archived:
                query = query.where(Site.is_active.is_(True))

            # Non-admin users only see sites they can access
            if not db_user.is_admin:
                accessible_site_ids = get_accessible_site_ids(db_user, db)
                if accessible_site_ids:
                    query = query.where(Site.id.in_(accessible_site_ids))
                else:
                    return {"sites": []}

            result = await session.execute(query.order_by(Site.created_at.desc()))
            sites = result.scalars().all()

            # Batch fetch all devices for the retrieved sites to eliminate N+1 queries
            site_ids = [site.id for site in sites]
            devices_by_site: Dict[Any, Any] = {}
            if site_ids:
                devices_query = select(Device).where(Device.site_id.in_(site_ids))
                if not include_archived:
                    devices_query = devices_query.where(Device.is_active.is_(True))
                devices_result = await session.execute(devices_query)
                for device in devices_result.scalars().all():
                    devices_by_site.setdefault(device.site_id, []).append(device)

            site_list = []
            for site in sites:
                devices = devices_by_site.get(site.id, [])

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
                    # Priority 0: Check device_type for IoT
                    if device.device_type == "iot_sensor":
                        os_types.add("iot")

                    # Priority 1: Normalize OS info via os_family. This covers
                    # config['os'] and os_details for both simulated devices
                    # (short tokens like "linux") and emulators (versioned
                    # strings like "Windows 11", "Android 14", "iOS 17").
                    os_family_key = os_family(
                        device.config.get("os")
                        if device.config and isinstance(device.config, dict)
                        else None
                    ) or os_family(device.os_details)
                    if os_family_key:
                        os_types.add(os_family_key)
                    # Priority 2: Infer from device name/description
                    else:
                        normalized_name = (device.name or "").lower()
                        if "windows" in normalized_name or "win" in normalized_name:
                            os_types.add("windows")
                        elif (
                            "linux" in normalized_name
                            or "ubuntu" in normalized_name
                            or "debian" in normalized_name
                        ):
                            os_types.add("linux")
                        elif (
                            "mac" in normalized_name
                            or "apple" in normalized_name
                            or "ios" in normalized_name
                        ):
                            os_types.add("macos")
                        elif "android" in normalized_name:
                            os_types.add("android")
                        elif "web" in normalized_name:
                            os_types.add("web")
                        else:
                            # Default to IoT for unknown devices
                            os_types.add("iot")

                site_list.append(
                    {
                        "site_id": site.site_id,
                        "tenant_id": site.tenant_id,
                        "name": site.name,
                        "description": site.description,
                        "location": site.location,
                        "is_monitored": site.is_monitored,
                        "is_active": site.is_active,
                        "lifecycle_state": site.lifecycle_state,
                        "status": status,
                        "os_types": list(os_types),
                        "devices_count": len(devices),
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
async def get_site(
    site_id: str,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Get a specific site by site_id."""
    try:
        # Verify access
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        verify_site_access_for_user(db_user, site_id, db)

        db_service = await get_database_service()

        # Look up site by site_id
        site = await db_service.get_site_by_site_id(site_id)

        if not site:
            raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")

        return {
            "site_id": site.site_id,
            "tenant_id": site.tenant_id,
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
async def delete_site(
    site_id: str,
    mode: str = Query("archive", pattern="^(archive|purge)$"),
    confirm: bool = Query(False, description="Required for purge"),
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, str]:
    """Archive or purge a site.

    - ``archive`` (default): hide the site and its devices from the Dashboard,
      retaining all historical data. Safe and reversible (set ``is_active``
      back to true to restore).
    - ``purge``: delete the site and ALL associated data (metrics, logs,
      history, devices). Destructive and irreversible; requires
      ``confirm=true``. Applies regardless of whether devices are simulated,
      emulated, or real.

    Requires operator-level access on the site.
    """
    if mode == "purge" and not confirm:
        raise HTTPException(
            status_code=400,
            detail="Purge requires confirm=true (it permanently deletes the site and all associated data).",
        )

    try:
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        verify_site_access_for_user(db_user, site_id, db, minimum_role="operator")

        db_service = await get_database_service()
        from sqlalchemy import delete, select, update

        # Import analytics models for comprehensive cleanup
        from homepot.app.models.AnalyticsModel import (
            APIRequestLog,
            ConfigurationHistory,
            DeviceMetrics,
            DeviceStateHistory,
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

            if mode == "archive":
                # --- ARCHIVE: hide the site and its devices, keep all data ---
                site.is_active = False  # type: ignore[assignment]
                site.lifecycle_state = SiteLifecycleState.ARCHIVED.value  # type: ignore[assignment]
                # Suspend the site's devices so they read as clearly inactive
                # (offline) on the Dashboard, while preserving their data.
                # They remain recoverable: restore re-activates devices whose
                # lifecycle_state is active/pending/suspended, so suspended
                # devices are revived when the site is restored.
                await session.execute(
                    update(Device)
                    .where(
                        Device.site_id == site.id,
                        Device.lifecycle_state.in_(
                            [
                                LifecycleState.ACTIVE.value,
                                LifecycleState.PENDING.value,
                                LifecycleState.SUSPENDED.value,
                            ]
                        ),
                    )
                    .values(
                        is_active=False,
                        lifecycle_state=LifecycleState.SUSPENDED.value,
                        status=DeviceStatus.OFFLINE.value,
                    )
                )
                # Also hide any independently unpaired/retired devices under the
                # site so nothing under an archived site remains visible.
                await session.execute(
                    update(Device)
                    .where(Device.site_id == site.id)
                    .values(is_active=False)
                )
                await session.commit()

                audit_logger = get_audit_logger()
                await audit_logger.log_event(
                    AuditEventType.SITE_DELETED,
                    f"Site '{site_name}' archived (hidden from Dashboard, data retained)",
                    site_id=None,
                    old_values={
                        "site_id": site_str_id,
                        "name": site_name,
                        "db_id": site_pk,
                        "cleanup_policy": "archive",
                        "lifecycle_state": "archived",
                        "devices": "suspended",
                    },
                )
                return {
                    "message": (
                        f"Site {site_id} archived (data retained; "
                        "set lifecycle_state='active' to restore)"
                    )
                }

            # --- PURGE: delete the site and ALL associated data ---

            # Get all devices for this site to clean up their related data
            # We need both Integer IDs (for FKs) and String IDs (for Analytics)
            devices_result = await session.execute(
                select(Device).where(Device.site_id == site.id)
            )
            devices = devices_result.scalars().all()
            device_pk_ids = [d.id for d in devices]
            device_str_ids = [d.device_id for d in devices]

            # --- PHASE 1: Clean up Device-Specific Analytics & History ---
            if device_pk_ids:
                # Device Metrics
                await session.execute(
                    delete(DeviceMetrics).where(
                        DeviceMetrics.device_id.in_(device_pk_ids)
                    )
                )
                # Device State History
                await session.execute(
                    delete(DeviceStateHistory).where(
                        DeviceStateHistory.device_id.in_(device_pk_ids)
                    )
                )

            if device_str_ids:
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
                # Error Logs: no device/site FK exists on error_logs, and the
                # device id only lives inside the context JSON (unreliable to
                # query across backends), so error_logs are intentionally
                # retained -- they are operational error records, not
                # site-scoped data.

            # --- PHASE 2: Clean up Site-Specific Analytics & History ---
            # Site Operating Schedules
            await session.execute(
                delete(SiteOperatingSchedule).where(
                    SiteOperatingSchedule.site_id == site_pk
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

            # Get associated Jobs to delete their AuditLogs and Push logs
            jobs_result = await session.execute(
                select(Job.id, Job.job_id).where(Job.site_id == site.id)
            )
            job_rows = jobs_result.all()
            job_pk_ids = [r[0] for r in job_rows]
            job_str_ids = [r[1] for r in job_rows]

            if job_pk_ids:
                # Delete AuditLogs for jobs
                await session.execute(
                    delete(AuditLog).where(AuditLog.job_id.in_(job_pk_ids))
                )
            if job_str_ids:
                # Delete Push Notification Logs linked to this site's jobs
                await session.execute(
                    delete(PushNotificationLog).where(
                        PushNotificationLog.job_id.in_(job_str_ids)
                    )
                )

            # Delete associated Jobs
            await session.execute(delete(Job).where(Job.site_id == site.id))

            # Delete associated Devices
            await session.execute(delete(Device).where(Device.site_id == site.id))

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
                    "cleanup_policy": "purge",
                },
            )

            return {
                "message": f"Site {site_id} and all associated data purged successfully"
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


@router.post("/{site_id}/restore", tags=["Sites"])
async def restore_site(
    site_id: str,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, str]:
    """Restore an archived site (reverses ``mode=archive``).

    Sets the site back to ``active`` and re-activates its devices so they
    reappear on the Dashboard, retaining all historical data. Permanently
    purged sites cannot be restored (the row no longer exists).
    """
    try:
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        verify_site_access_for_user(db_user, site_id, db, minimum_role="operator")

        db_service = await get_database_service()

        async with db_service.get_session() as session:
            result = await session.execute(select(Site).where(Site.site_id == site_id))
            site = result.scalars().first()

            if not site:
                raise HTTPException(
                    status_code=404, detail=f"Site '{site_id}' not found"
                )

            if (
                site.is_active
                and site.lifecycle_state == SiteLifecycleState.ACTIVE.value
            ):
                return {
                    "message": f"Site {site_id} is already active (nothing to restore)"
                }

            site.is_active = True  # type: ignore[assignment]
            site.lifecycle_state = SiteLifecycleState.ACTIVE.value  # type: ignore[assignment]
            # Model B: restoring a site only un-hides the site itself. Devices
            # that were suspended by the site archive stay suspended (is_active
            # remains false) until they are individually restored, so a
            # technician can review them on the Site page and restore per device.
            await session.commit()

            audit_logger = get_audit_logger()
            await audit_logger.log_event(
                AuditEventType.SITE_UPDATED,
                f"Site '{site.name}' restored (archived -> active)",
                site_id=int(site.id),
                old_values={
                    "site_id": site.site_id,
                    "cleanup_policy": "restore",
                    "lifecycle_state": "active",
                },
            )
            return {"message": f"Site {site_id} restored (lifecycle_state='active')"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restore site {site_id}: {e}", exc_info=True)
        await log_error(
            category="api",
            severity="error",
            error_message=f"Failed to restore site {site_id}",
            exception=e,
            endpoint=f"/api/v1/sites/{site_id}/restore",
            context={"site_id": site_id, "action": "restore_site"},
        )
        raise HTTPException(status_code=500, detail="Failed to restore site")


@router.put("/{site_id}/monitor", tags=["Sites"])
async def toggle_site_monitor(
    site_id: str,
    monitor: bool,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Toggle the monitoring status of a site."""
    try:
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        verify_site_access_for_user(db_user, site_id, db, minimum_role="operator")

        db_service = await get_database_service()

        from sqlalchemy import select

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


@router.get("/{site_id}/stats", tags=["Sites"])
async def get_site_stats(
    site_id: str,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Get device breakdown and statistics for a specific site."""
    try:
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        verify_site_access_for_user(db_user, site_id, db)

        db_service = await get_database_service()

        # Verify site exists
        site = await db_service.get_site_by_site_id(site_id)
        if not site:
            raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")

        # Get devices for this site
        devices = await db_service.get_devices_by_site_id(site_id)

        # Calculate stats
        total_devices = len(devices)
        pre_provisioned = sum(
            1
            for d in devices
            if getattr(d, "enrollment_method", None) == "pre-provisioned"
        )
        self_enrolled = sum(
            1
            for d in devices
            if getattr(d, "enrollment_method", None) == "self-enrolled"
        )

        return {
            "site_id": site_id,
            "total_devices": total_devices,
            "breakdown": {
                "pre_provisioned": pre_provisioned,
                "self_enrolled": self_enrolled,
                "other": total_devices - (pre_provisioned + self_enrolled),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get site stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get site stats.")
