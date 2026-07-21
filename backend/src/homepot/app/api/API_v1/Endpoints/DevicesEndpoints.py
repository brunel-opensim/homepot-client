"""API endpoints for managing Device in the HomePot system."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, cast
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session as SASession
from sqlalchemy.orm import joinedload

from homepot.app.auth_utils import (
    UserDict,
    require_user,
    verify_device_belongs_to_user,
    verify_site_access_for_user,
)
from homepot.app.models import AnalyticsModel as analytics_models
from homepot.audit import AuditEventType, get_audit_logger
from homepot.client import HomepotClient
from homepot.database import get_database_service, get_db
from homepot.models import (
    AuditLog,
    CommandStatus,
    ConnectivityState,
    Device,
    DeviceAssignment,
    DeviceCommand,
    DeviceCredential,
    DeviceLifecycleEvent,
    HealthState,
    Job,
    LifecycleEpoch,
    LifecycleState,
    Site,
    User,
)

client_instance: Optional[HomepotClient] = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_HEARTBEAT_ONLINE_SECONDS = 120


def _compute_connectivity(device: Device) -> str:
    """Return online/offline/unknown based on heartbeat recency."""
    if not device.last_heartbeat_at:
        return ConnectivityState.UNKNOWN.value
    heartbeat = device.last_heartbeat_at
    if heartbeat.tzinfo is None:
        heartbeat = heartbeat.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - heartbeat
    return (
        ConnectivityState.ONLINE.value
        if delta.total_seconds() <= _HEARTBEAT_ONLINE_SECONDS
        else ConnectivityState.OFFLINE.value
    )


router = APIRouter()


class CreateDeviceRequest(BaseModel):
    """Request model for creating a new device."""

    site_id: str
    device_id: str
    name: str
    device_type: str
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    os_details: Optional[str] = None
    firmware_version: Optional[str] = None
    enrollment_method: Optional[str] = "pre-provisioned"
    enrollment_token: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "site_id": "site-123",
                "device_id": "pos-001",
                "name": "Main POS Terminal",
                "device_type": "pos_terminal",
                "ip_address": "192.168.1.100",
                "mac_address": "00:11:22:33:44:55",
                "firmware_version": "1.0.0",
                "enrollment_method": "pre-provisioned",
                "enrollment_token": "secr3t-token",
            }
        }
    )


class UpdateDeviceRequest(BaseModel):
    """Request model for updating an existing device."""

    name: Optional[str] = None
    device_type: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    firmware_version: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Updated POS Terminal",
                "device_type": "pos_terminal",
                "ip_address": "192.168.1.101",
                "mac_address": "00:11:22:33:44:55",
                "firmware_version": "1.0.1",
            }
        }
    )


@router.post("/device", tags=["Devices"])
async def create_device(
    device_request: CreateDeviceRequest,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Create a new device."""
    try:
        # Verify user has access to the target site
        verify_site_access_for_user(
            cast(
                User, db.query(User).filter(User.email == current_user["email"]).first()
            ),
            device_request.site_id,
            db,
            minimum_role="operator",
        )

        db_service = await get_database_service()

        # Check if device already exists
        existing_device = await db_service.get_device_by_device_id(
            device_request.device_id
        )
        if existing_device:
            raise HTTPException(
                status_code=409,
                detail=f"Device {device_request.device_id} already exists",
            )

        # Verify site exists
        site = await db_service.get_site_by_site_id(device_request.site_id)
        if not site:
            raise HTTPException(
                status_code=404, detail=f"Site {device_request.site_id} not found"
            )

        # Create device
        device = await db_service.create_device(
            device_id=device_request.device_id,
            name=device_request.name,
            device_type=device_request.device_type,
            site_id=int(site.id),
            ip_address=device_request.ip_address,
            config={
                "mac_address": device_request.mac_address,
                "os_details": device_request.os_details,
                "firmware_version": device_request.firmware_version,
            },
        )

        # Log audit event
        audit_logger = get_audit_logger()
        await audit_logger.log_event(
            AuditEventType.DEVICE_CREATED,
            f"Device '{device.name}' registered with ID {device.device_id}",
            site_id=int(site.id),
            device_id=int(device.id),
            new_values={
                "device_id": str(device.device_id),
                "name": str(device.name),
                "site_id": str(device.site_id),
                "type": str(device.device_type),
            },
        )

        return {
            "message": "Device created successfully",
            "device_id": device.device_id,
            "name": device.name,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create device: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to create device. Please check server logs."
        )


@router.post("/sites/{site_id}/devices", tags=["Devices"])
async def register_device_to_site(
    site_id: str,
    device_request: CreateDeviceRequest,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Register a device to a specific site with enrollment logic."""
    try:
        # Verify user has operator-level access to the site
        verify_site_access_for_user(
            cast(
                User, db.query(User).filter(User.email == current_user["email"]).first()
            ),
            site_id,
            db,
            minimum_role="operator",
        )

        db_service = await get_database_service()

        if site_id != device_request.site_id:
            raise HTTPException(
                status_code=400, detail="Site ID in URL must match payload"
            )

        # Verify site exists
        site = await db_service.get_site_by_site_id(site_id)
        if not site:
            raise HTTPException(status_code=404, detail=f"Site {site_id} not found")

        # Handle claiming pre-provisioned devices
        if device_request.enrollment_method == "pre-provisioned":
            existing_device = await db_service.get_device_by_device_id(
                device_request.device_id
            )
            if existing_device:
                # Update status and enrollment info
                existing_device.status = "online"  # type: ignore
                existing_device.enrollment_method = "pre-provisioned"  # type: ignore
                if device_request.ip_address:
                    existing_device.ip_address = device_request.ip_address  # type: ignore
                async with db_service.get_session() as session:
                    session.add(existing_device)
                    await session.commit()
                return {
                    "message": "Device claimed successfully",
                    "device_id": device_request.device_id,
                }

        # Otherwise verify device doesn't exist to create it
        existing_device = await db_service.get_device_by_device_id(
            device_request.device_id
        )
        if existing_device:
            raise HTTPException(
                status_code=409,
                detail=f"Device {device_request.device_id} already exists",
            )

        # Create new device using db_service
        device = await db_service.create_device(
            device_id=device_request.device_id,
            name=device_request.name,
            device_type=device_request.device_type,
            site_id=int(site.id),  # type: ignore
            ip_address=device_request.ip_address,
        )

        # Add the additional enrollment properties that create_device doesn't map directly
        device.mac_address = device_request.mac_address  # type: ignore
        device.os_details = device_request.os_details  # type: ignore
        device.firmware_version = device_request.firmware_version  # type: ignore
        device.enrollment_method = device_request.enrollment_method  # type: ignore
        device.enrollment_token = device_request.enrollment_token  # type: ignore
        device.status = "online"  # type: ignore

        async with db_service.get_session() as session:
            session.add(device)
            await session.commit()

        return {
            "message": "Device registered successfully",
            "device_id": device.device_id,
            "site_id": site.site_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering device to site {site_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to register device: {str(e)}"
        )


@router.get("/device", tags=["Devices"])
async def list_device(
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, List[Dict]]:
    """List all devices (scoped to user's accessible sites)."""
    try:
        current_db_user = (
            db.query(User).filter(User.email == current_user["email"]).first()
        )
        if not current_db_user:
            raise HTTPException(status_code=403, detail="User not found")
        db_user: User = current_db_user  # type: ignore[assignment]

        db_service = await get_database_service()

        async with db_service.get_session() as session:
            query = (
                select(Device)
                .options(joinedload(Device.site))
                .where(Device.is_active.is_(True))
            )

            # Non-admin users only see devices in their accessible sites
            if not db_user.is_admin:
                site_ids = [row[0] for row in db.query(Site.id).all()]
                accessible_site_ids = set()
                for sid in site_ids:
                    site_obj = db.query(Site).filter(Site.id == sid).first()
                    if not site_obj:
                        continue
                    try:
                        verify_site_access_for_user(
                            db_user,
                            cast(str, site_obj.site_id),
                            db,
                        )
                        accessible_site_ids.add(sid)
                    except HTTPException:
                        pass
                if accessible_site_ids:
                    query = query.where(Device.site_id.in_(accessible_site_ids))
                else:
                    return {"devices": []}

            query = query.order_by(Device.created_at.desc())
            result = await session.execute(query)
            devices = result.scalars().all()

            device_list = []
            for device in devices:
                device_list.append(
                    {
                        "site_id": device.site.site_id,
                        "device_id": device.device_id,
                        "name": device.name,
                        "device_type": device.device_type,
                        "os_details": device.os_details,
                        "lifecycle_state": device.lifecycle_state,
                        "connectivity_state": _compute_connectivity(device),
                        "health_state": device.health_state
                        or HealthState.UNKNOWN.value,
                        "status": device.status,
                        "ip_address": device.ip_address,
                        "last_heartbeat_at": (
                            device.last_heartbeat_at.isoformat()
                            if device.last_heartbeat_at
                            else None
                        ),
                        "credential_status": (
                            "active"
                            if any(c.is_active for c in (device.credentials or []))
                            else "inactive"
                        ),
                        "is_monitored": device.is_monitored,
                        "created_at": (
                            device.created_at.isoformat() if device.created_at else None
                        ),
                    }
                )

            return {"devices": device_list}

    except Exception as e:
        logger.error(f"Failed to list device: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to list device. Please check server logs."
        )


@router.get("/device/{device_id}", tags=["Devices"])
async def get_device(
    device_id: str,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Get a specific Device by device_id."""
    try:
        db_service = await get_database_service()

        # Look up site by device_id
        device = await db_service.get_device_by_device_id(device_id)

        if not device:
            raise HTTPException(
                status_code=404, detail=f"Device '{device_id}' not found"
            )

        # Verify user can access this device's site
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        verify_device_belongs_to_user(db_user, device, db)

        return {
            "site_id": device.site.site_id,
            "site_name": device.site.name if device.site else "Unknown Site",
            "device_id": device.device_id,
            "name": device.name,
            "device_type": device.device_type,
            "lifecycle_state": device.lifecycle_state,
            "connectivity_state": _compute_connectivity(device),
            "health_state": device.health_state or HealthState.UNKNOWN.value,
            "status": device.status,
            "ip_address": device.ip_address or "N/A",
            "os_details": device.os_details
            or (device.config.get("os_details") if device.config else "N/A"),
            "mac_address": device.mac_address
            or (device.config.get("mac_address") if device.config else "N/A"),
            "firmware_version": device.firmware_version
            or (device.config.get("firmware_version") if device.config else "N/A"),
            "last_seen": device.last_seen.isoformat() if device.last_seen else None,
            "last_heartbeat_at": (
                device.last_heartbeat_at.isoformat()
                if device.last_heartbeat_at
                else None
            ),
            "credential_status": (
                "active"
                if any(c.is_active for c in (device.credentials or []))
                else "inactive"
            ),
            "is_monitored": device.is_monitored,
            "created_at": device.created_at.isoformat() if device.created_at else None,
            "updated_at": device.updated_at.isoformat() if device.updated_at else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get Device {device_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to get Device. Please check server logs."
        )


@router.get("/device/{device_id}/credentials", tags=["Devices"])
async def get_device_credentials(
    device_id: str,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Return credential history for a device (without secrets)."""
    try:
        db_service = await get_database_service()
        device = await db_service.get_device_by_device_id(device_id)
        if not device:
            raise HTTPException(
                status_code=404, detail=f"Device '{device_id}' not found"
            )
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        verify_device_belongs_to_user(db_user, device, db)

        return {
            "device_id": device.device_id,
            "credentials": [
                {
                    "credential_id": c.credential_id,
                    "is_active": c.is_active,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "rotated_at": c.rotated_at.isoformat() if c.rotated_at else None,
                    "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
                }
                for c in (device.credentials or [])
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get credentials for Device {device_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to get device credentials. Please check server logs.",
        )


@router.put("/device/{device_id}", tags=["Devices"])
async def update_device(
    device_id: str,
    device_request: UpdateDeviceRequest,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Update an existing device."""
    try:
        current_db_user = (
            db.query(User).filter(User.email == current_user["email"]).first()
        )
        if not current_db_user:
            raise HTTPException(status_code=403, detail="User not found")
        db_user: User = current_db_user  # type: ignore[assignment]
        db_service = await get_database_service()

        # Verify access to the device before updating
        existing = await db_service.get_device_by_device_id(device_id)
        if not existing:
            raise HTTPException(
                status_code=404, detail=f"Device '{device_id}' not found"
            )
        verify_device_belongs_to_user(db_user, existing, db, minimum_role="operator")

        # Prepare config update
        config_update = {}
        if device_request.mac_address:
            config_update["mac_address"] = device_request.mac_address
        if device_request.firmware_version:
            config_update["firmware_version"] = device_request.firmware_version

        # Update device
        updated_device = await db_service.update_device(
            device_id=device_id,
            name=device_request.name,
            device_type=device_request.device_type,
            ip_address=device_request.ip_address,
            config=config_update if config_update else None,
        )
        if not updated_device:
            raise HTTPException(status_code=500, detail="Failed to update device")

        # Get site for audit logging (need integer ID)
        site_pk = int(updated_device.site_id)

        # Log audit event
        audit_logger = get_audit_logger()
        await audit_logger.log_event(
            AuditEventType.DEVICE_UPDATED,
            f"Device '{updated_device.name}' updated",
            device_id=int(updated_device.id),
            site_id=site_pk,
            new_values={
                "name": str(updated_device.name),
                "type": str(updated_device.device_type),
                "ip": str(updated_device.ip_address),
            },
        )

        return {
            "message": "Device updated successfully",
            "device_id": updated_device.device_id,
            "name": updated_device.name,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update device {device_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to update device. Please check server logs."
        )


@router.delete("/device/{device_id}", tags=["Devices"])
async def delete_device(
    device_id: str,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Unpair a device and archive its associated data.

    Requires operator-level access on the device's site.
    """
    try:
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        db_service = await get_database_service()

        # Verify access before unpairing — operator role required
        device = await db_service.get_device_by_device_id(device_id)
        if not device:
            raise HTTPException(
                status_code=404, detail=f"Device '{device_id}' not found"
            )
        verify_device_belongs_to_user(db_user, device, db, minimum_role="operator")

        success = await db_service.delete_device(device_id)

        if not success:
            raise HTTPException(
                status_code=404, detail=f"Device '{device_id}' not found"
            )

        return {"message": f"Device '{device_id}' unpaired and archived successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete device {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


class UnpairDeviceRequest(BaseModel):
    """Request model for explicitly unpairing a device."""

    reason: Optional[str] = None
    idempotency_key: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reason": "Hardware refresh at store #42",
                "idempotency_key": "unpair-abc123-20260720",
            }
        }
    )


@router.post("/device/{device_id}/unpair", tags=["Devices"])
async def unpair_device(
    device_id: str,
    payload: UnpairDeviceRequest,
    request: Request,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Explicitly unpair a device.

    Authenticates the caller, verifies site ownership (operator+ role),
    validates the current lifecycle state, supports idempotency,
    revokes credentials and commands, transitions the device to
    ``unpaired`` state, and produces a complete audit event.

    Idempotency
    -----------
    Pass an ``idempotency_key`` in the request body.  If an unpair
    audit log already exists for this device with the same key, the
    endpoint returns the previously-completed result without re-applying
    side-effects.
    """
    try:
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        if not db_user:
            raise HTTPException(status_code=403, detail="User not found")
        db_service = await get_database_service()

        # Look up the device
        device = await db_service.get_device_by_device_id(device_id)
        if not device:
            raise HTTPException(
                status_code=404, detail=f"Device '{device_id}' not found"
            )

        # Verify site ownership (operator+)
        verify_device_belongs_to_user(db_user, device, db, minimum_role="operator")

        # ----- Idempotency check -----
        if payload.idempotency_key:
            async with db_service.get_session() as session:
                existing = await session.execute(
                    select(AuditLog).where(
                        AuditLog.device_id == device.id,
                        AuditLog.event_type == "device_unpaired",
                        AuditLog.event_metadata["idempotency_key"].as_string()
                        == payload.idempotency_key,
                    )
                )
                if existing.scalars().first():
                    logger.info(
                        "Idempotent unpair request for device=%s key=%s",
                        device_id,
                        payload.idempotency_key,
                    )
                    return {
                        "status": "success",
                        "message": f"Device '{device_id}' already unpaired",
                        "device_id": device_id,
                    }

        # ----- Lifecycle validation -----
        current_lifecycle = device.lifecycle_state
        allowed = (
            LifecycleState.ACTIVE.value,
            LifecycleState.SUSPENDED.value,
            # Allow re-unpair if somehow stuck in a transitional state
        )
        if current_lifecycle not in allowed:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Device lifecycle state is '{current_lifecycle}'; "
                    "only 'active' or 'suspended' devices may be unpaired"
                ),
            )

        if current_lifecycle == LifecycleState.UNPAIRED.value:
            return {
                "status": "success",
                "message": f"Device '{device_id}' is already unpaired",
                "device_id": device_id,
            }

        now = datetime.now(timezone.utc)

        # ----- Revoke credentials -----
        async with db_service.get_session() as session:
            cred_result = await session.execute(
                select(DeviceCredential).where(
                    DeviceCredential.device_id == device.id,
                    DeviceCredential.is_active,
                )
            )
            for cred in cred_result.scalars().all():
                cred.is_active = False  # type: ignore[assignment]
                cred.revoked_at = now  # type: ignore[assignment]

        # ----- Expire outstanding commands -----
        async with db_service.get_session() as session:
            cmd_result = await session.execute(
                select(DeviceCommand).where(
                    DeviceCommand.device_id == device.id,
                    DeviceCommand.status.in_(
                        [CommandStatus.PENDING.value, CommandStatus.SENT.value]
                    ),
                )
            )
            for cmd in cmd_result.scalars().all():
                cmd.status = CommandStatus.EXPIRED.value  # type: ignore[assignment]

        # ----- Revoke push-provider registrations -----
        # No persistent push-subscription table exists in this codebase.
        # PushNotificationLog entries are historical records kept for audit.
        # Placeholder for future push-provider revocation when a registry is added.

        # ----- Expire sessions -----
        # No device session table exists.  Sessions are implicitly tied to
        # the validity of the DeviceCredential / api_key_hash; revoking
        # those above is sufficient.

        # ----- Update device -----
        device.lifecycle_state = LifecycleState.UNPAIRED.value  # type: ignore[assignment]
        device.is_active = False  # type: ignore[assignment]
        device.api_key_hash = None  # type: ignore[assignment]

        # ----- Audit event -----
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        audit_logger = get_audit_logger()
        await audit_logger.log_event(
            AuditEventType.DEVICE_UNPAIRED,
            f"Device '{device.name}' ({device.device_id}) unpaired by "
            f"{current_user['email']}"
            + (f" — {payload.reason}" if payload.reason else ""),
            device_id=int(device.id),
            site_id=int(device.site_id) if device.site_id else None,
            user_id=int(db_user.id),
            ip_address=ip_address,
            user_agent=user_agent,
            old_values={
                "lifecycle_state": current_lifecycle,
                "is_active": True,
            },
            new_values={
                "lifecycle_state": LifecycleState.UNPAIRED.value,
                "is_active": False,
                "reason": payload.reason,
            },
            event_metadata={
                "idempotency_key": payload.idempotency_key,
                "unpair_endpoint": "POST /device/{device_id}/unpair",
            },
        )

        logger.info(
            "Device unpaired: %s by %s (reason=%s)",
            device_id,
            current_user["email"],
            payload.reason,
        )

        return {
            "status": "success",
            "message": f"Device '{device_id}' unpaired successfully",
            "device_id": device_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unpair device {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


# ---------------------------------------------------------------------------
# Shared helpers for lifecycle transitions
# ---------------------------------------------------------------------------


async def _record_lifecycle_event(
    db_service: Any,
    device: Device,
    from_state: Optional[str],
    to_state: str,
    triggered_by_user_id: Optional[int] = None,
    reason: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    epoch_id: Optional[int] = None,
) -> None:
    """Persist a DeviceLifecycleEvent row."""
    async with db_service.get_session() as session:
        event = DeviceLifecycleEvent(
            event_id=str(uuid.uuid4()),
            device_id=device.id,
            epoch_id=epoch_id,
            from_state=from_state,
            to_state=to_state,
            triggered_by_user_id=triggered_by_user_id,
            reason=reason,
            idempotency_key=idempotency_key,
        )
        session.add(event)
        await session.commit()


class LifecycleTransitionRequest(BaseModel):
    """Request body for lifecycle-state transitions."""

    reason: Optional[str] = None
    idempotency_key: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reason": "Scheduled maintenance window",
                "idempotency_key": "lifecycle-abc123",
            }
        }
    )


class TransferDeviceRequest(BaseModel):
    """Request body for transferring a device between sites."""

    target_site_id: str
    reason: Optional[str] = None
    idempotency_key: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "target_site_id": "site-456",
                "reason": "Reallocation to store #456",
                "idempotency_key": "transfer-abc123",
            }
        }
    )


class ReEnrolDeviceRequest(BaseModel):
    """Request body for re-enrolling an unpaired device."""

    site_id: str
    device_name: Optional[str] = None
    reason: Optional[str] = None
    idempotency_key: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "site_id": "site-123",
                "device_name": "Front POS (re-enrolled)",
                "reason": "Hardware refresh complete",
                "idempotency_key": "reenrol-abc123",
            }
        }
    )


# ---------------------------------------------------------------------------
# Suspend
# ---------------------------------------------------------------------------


@router.post("/device/{device_id}/suspend", tags=["Devices"])
async def suspend_device(
    device_id: str,
    payload: LifecycleTransitionRequest,
    request: Request,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Suspend a device: ``active → suspended``.

    Requires operator-level access on the device's site.
    """
    try:
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        if not db_user:
            raise HTTPException(status_code=403, detail="User not found")
        db_service = await get_database_service()

        device = await db_service.get_device_by_device_id(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        verify_device_belongs_to_user(db_user, device, db, minimum_role="operator")

        current_lifecycle = device.lifecycle_state
        if current_lifecycle != LifecycleState.ACTIVE.value:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Device lifecycle state is '{current_lifecycle}'; "
                    "only 'active' devices may be suspended"
                ),
            )

        device.lifecycle_state = LifecycleState.SUSPENDED.value  # type: ignore[assignment]

        await _record_lifecycle_event(
            db_service,
            device,
            from_state=str(current_lifecycle),
            to_state=LifecycleState.SUSPENDED.value,
            triggered_by_user_id=int(db_user.id),
            reason=payload.reason,
            idempotency_key=payload.idempotency_key,
        )

        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        audit_logger = get_audit_logger()
        await audit_logger.log_event(
            AuditEventType.DEVICE_SUSPENDED,
            f"Device '{device.name}' ({device.device_id}) suspended by "
            f"{current_user['email']}"
            + (f" — {payload.reason}" if payload.reason else ""),
            device_id=int(device.id),
            site_id=int(device.site_id) if device.site_id else None,
            user_id=int(db_user.id),
            ip_address=ip_address,
            user_agent=user_agent,
            old_values={"lifecycle_state": current_lifecycle},
            new_values={
                "lifecycle_state": LifecycleState.SUSPENDED.value,
                "reason": payload.reason,
            },
            event_metadata={"idempotency_key": payload.idempotency_key},
        )

        logger.info("Device suspended: %s by %s", device_id, current_user["email"])

        return {
            "status": "success",
            "message": f"Device '{device_id}' suspended",
            "device_id": device_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to suspend device {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


# ---------------------------------------------------------------------------
# Resume
# ---------------------------------------------------------------------------


@router.post("/device/{device_id}/resume", tags=["Devices"])
async def resume_device(
    device_id: str,
    payload: LifecycleTransitionRequest,
    request: Request,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Resume a suspended device: ``suspended → active``.

    Requires operator-level access on the device's site.
    """
    try:
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        if not db_user:
            raise HTTPException(status_code=403, detail="User not found")
        db_service = await get_database_service()

        device = await db_service.get_device_by_device_id(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        verify_device_belongs_to_user(db_user, device, db, minimum_role="operator")

        current_lifecycle = device.lifecycle_state
        if current_lifecycle != LifecycleState.SUSPENDED.value:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Device lifecycle state is '{current_lifecycle}'; "
                    "only 'suspended' devices may be resumed"
                ),
            )

        device.lifecycle_state = LifecycleState.ACTIVE.value  # type: ignore[assignment]

        await _record_lifecycle_event(
            db_service,
            device,
            from_state=str(current_lifecycle),
            to_state=LifecycleState.ACTIVE.value,
            triggered_by_user_id=int(db_user.id),
            reason=payload.reason,
            idempotency_key=payload.idempotency_key,
        )

        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        audit_logger = get_audit_logger()
        await audit_logger.log_event(
            AuditEventType.DEVICE_RESUMED,
            f"Device '{device.name}' ({device.device_id}) resumed by "
            f"{current_user['email']}"
            + (f" — {payload.reason}" if payload.reason else ""),
            device_id=int(device.id),
            site_id=int(device.site_id) if device.site_id else None,
            user_id=int(db_user.id),
            ip_address=ip_address,
            user_agent=user_agent,
            old_values={"lifecycle_state": current_lifecycle},
            new_values={
                "lifecycle_state": LifecycleState.ACTIVE.value,
                "reason": payload.reason,
            },
            event_metadata={"idempotency_key": payload.idempotency_key},
        )

        logger.info("Device resumed: %s by %s", device_id, current_user["email"])

        return {
            "status": "success",
            "message": f"Device '{device_id}' resumed",
            "device_id": device_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume device {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


# ---------------------------------------------------------------------------
# Retire
# ---------------------------------------------------------------------------


@router.post("/device/{device_id}/retire", tags=["Devices"])
async def retire_device(
    device_id: str,
    payload: LifecycleTransitionRequest,
    request: Request,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Retire a device from eligible lifecycle states.

    Eligible states: ``active``, ``suspended``, ``unpaired``.

    Retired is a terminal state — the device cannot be re-enrolled
    or transferred.  Requires operator-level access on the site.
    """
    try:
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        if not db_user:
            raise HTTPException(status_code=403, detail="User not found")
        db_service = await get_database_service()

        device = await db_service.get_device_by_device_id(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        verify_device_belongs_to_user(db_user, device, db, minimum_role="operator")

        current_lifecycle = device.lifecycle_state
        eligible = (
            LifecycleState.ACTIVE.value,
            LifecycleState.SUSPENDED.value,
            LifecycleState.UNPAIRED.value,
        )
        if current_lifecycle not in eligible:
            raise HTTPException(
                status_code=400,
                detail=f"Device lifecycle state is '{current_lifecycle}'; "
                "only 'active', 'suspended', or 'unpaired' devices may be retired",
            )

        now = datetime.now(timezone.utc)
        device.lifecycle_state = LifecycleState.RETIRED.value  # type: ignore[assignment]
        device.is_active = False  # type: ignore[assignment]
        device.api_key_hash = None  # type: ignore[assignment]

        # Revoke active credentials
        async with db_service.get_session() as session:
            cred_result = await session.execute(
                select(DeviceCredential).where(
                    DeviceCredential.device_id == device.id,
                    DeviceCredential.is_active,
                )
            )
            for cred in cred_result.scalars().all():
                cred.is_active = False  # type: ignore[assignment]
                cred.revoked_at = now  # type: ignore[assignment]

        # Expire pending commands
        async with db_service.get_session() as session:
            cmd_result = await session.execute(
                select(DeviceCommand).where(
                    DeviceCommand.device_id == device.id,
                    DeviceCommand.status.in_(
                        [CommandStatus.PENDING.value, CommandStatus.SENT.value]
                    ),
                )
            )
            for cmd in cmd_result.scalars().all():
                cmd.status = CommandStatus.EXPIRED.value  # type: ignore[assignment]

        # Close current epoch if open
        if device.lifecycle_epoch_id:
            async with db_service.get_session() as session:
                epoch_result = await session.execute(
                    select(LifecycleEpoch).where(
                        LifecycleEpoch.id == device.lifecycle_epoch_id
                    )
                )
                epoch = epoch_result.scalars().first()
                if epoch and not epoch.ended_at:
                    epoch.ended_at = now  # type: ignore[assignment]

        await _record_lifecycle_event(
            db_service,
            device,
            from_state=str(current_lifecycle),
            to_state=LifecycleState.RETIRED.value,
            triggered_by_user_id=int(db_user.id),
            reason=payload.reason,
            idempotency_key=payload.idempotency_key,
        )

        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        audit_logger = get_audit_logger()
        await audit_logger.log_event(
            AuditEventType.DEVICE_RETIRED,
            f"Device '{device.name}' ({device.device_id}) retired by "
            f"{current_user['email']}"
            + (f" — {payload.reason}" if payload.reason else ""),
            device_id=int(device.id),
            site_id=int(device.site_id) if device.site_id else None,
            user_id=int(db_user.id),
            ip_address=ip_address,
            user_agent=user_agent,
            old_values={"lifecycle_state": current_lifecycle, "is_active": True},
            new_values={
                "lifecycle_state": LifecycleState.RETIRED.value,
                "is_active": False,
                "reason": payload.reason,
            },
            event_metadata={"idempotency_key": payload.idempotency_key},
        )

        logger.info("Device retired: %s by %s", device_id, current_user["email"])

        return {
            "status": "success",
            "message": f"Device '{device_id}' retired",
            "device_id": device_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retire device {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


# ---------------------------------------------------------------------------
# Re-enrol
# ---------------------------------------------------------------------------


@router.post("/device/{device_id}/reenrol", tags=["Devices"])
async def reenrol_device(
    device_id: str,
    payload: ReEnrolDeviceRequest,
    request: Request,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Re-enrol an unpaired device into a new lifecycle epoch.

    The device must be in ``unpaired`` state.  A new epoch and
    credentials are issued.  Requires operator-level access on
    the target site.
    """
    try:
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        if not db_user:
            raise HTTPException(status_code=403, detail="User not found")
        db_service = await get_database_service()

        device = await db_service.get_device_by_device_id(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        # Verify access to the target site
        verify_site_access_for_user(
            db_user, payload.site_id, db, minimum_role="operator"
        )

        current_lifecycle = device.lifecycle_state
        if current_lifecycle != LifecycleState.UNPAIRED.value:
            raise HTTPException(
                status_code=400,
                detail=f"Device lifecycle state is '{current_lifecycle}'; "
                "only 'unpaired' devices may be re-enrolled",
            )

        # Validate target site exists
        site = db.query(Site).filter(Site.site_id == payload.site_id).first()
        if not site:
            raise HTTPException(
                status_code=404, detail=f"Site '{payload.site_id}' not found"
            )

        now = datetime.now(timezone.utc)

        # If the device is being re-enrolled to a different site, close
        # the old assignment and create a new one
        if device.site_id != site.id:
            async with db_service.get_session() as session:
                old_assignment_result = await session.execute(
                    select(DeviceAssignment).where(
                        DeviceAssignment.device_id == device.id,
                        DeviceAssignment.is_current,
                    )
                )
                old_assignment = old_assignment_result.scalars().first()
                if old_assignment:
                    old_assignment.is_current = False  # type: ignore[assignment]
                    old_assignment.unassigned_at = now  # type: ignore[assignment]

                new_assignment = DeviceAssignment(
                    assignment_id=str(uuid.uuid4()),
                    device_id=device.id,
                    site_id=int(site.id),
                    assignment_reason=payload.reason or "re-enrolment",
                    assigned_at=now,
                    is_current=True,
                )
                session.add(new_assignment)

        # Update device
        device.site_id = int(site.id)  # type: ignore[assignment]
        if payload.device_name:
            device.name = payload.device_name  # type: ignore[assignment]
        device.lifecycle_state = LifecycleState.ACTIVE.value  # type: ignore[assignment]
        device.is_active = True  # type: ignore[assignment]

        # Create new lifecycle epoch
        async with db_service.get_session() as session:
            new_epoch = LifecycleEpoch(
                epoch_id=str(uuid.uuid4()),
                device_id=device.id,
                site_id=int(site.id),
                claimed_at=now,
                enrolment_method="re-enrolled",
            )
            session.add(new_epoch)
            await session.flush()
            device.lifecycle_epoch_id = new_epoch.id  # type: ignore[assignment]

        # Issue new credential
        import secrets

        from homepot.app.auth_utils import hash_password

        new_api_key = secrets.token_urlsafe(32)
        new_key_hash = hash_password(new_api_key)

        async with db_service.get_session() as session:
            new_credential = DeviceCredential(
                credential_id=str(uuid.uuid4()),
                device_id=device.id,
                key_hash=new_key_hash,
                is_active=True,
            )
            session.add(new_credential)
        device.api_key_hash = new_key_hash  # type: ignore[assignment]

        await _record_lifecycle_event(
            db_service,
            device,
            from_state=str(current_lifecycle),
            to_state=LifecycleState.ACTIVE.value,
            triggered_by_user_id=int(db_user.id),
            reason=payload.reason or "re-enrolment",
            idempotency_key=payload.idempotency_key,
        )

        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        audit_logger = get_audit_logger()
        await audit_logger.log_event(
            AuditEventType.DEVICE_RE_ENROLLED,
            f"Device '{device.name}' ({device.device_id}) re-enrolled to site "
            f"'{payload.site_id}' by {current_user['email']}"
            + (f" — {payload.reason}" if payload.reason else ""),
            device_id=int(device.id),
            site_id=int(site.id),
            user_id=int(db_user.id),
            ip_address=ip_address,
            user_agent=user_agent,
            old_values={"lifecycle_state": current_lifecycle},
            new_values={
                "lifecycle_state": LifecycleState.ACTIVE.value,
                "site_id": payload.site_id,
                "reason": payload.reason,
            },
            event_metadata={"idempotency_key": payload.idempotency_key},
        )

        logger.info(
            "Device re-enrolled: %s -> site %s by %s",
            device_id,
            payload.site_id,
            current_user["email"],
        )

        return {
            "status": "success",
            "message": f"Device '{device_id}' re-enrolled to site '{payload.site_id}'",
            "device_id": device_id,
            "api_key": new_api_key,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to re-enrol device {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


# ---------------------------------------------------------------------------
# Transfer
# ---------------------------------------------------------------------------


@router.post("/device/{device_id}/transfer", tags=["Devices"])
async def transfer_device(
    device_id: str,
    payload: TransferDeviceRequest,
    request: Request,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Transfer a device between sites.

    The caller must have operator+ access on **both** the source and
    target sites.  The current lifecycle epoch is closed, a new epoch
    and assignment are created, credentials are rotated, and a full
    audit trail is produced.
    """
    try:
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        if not db_user:
            raise HTTPException(status_code=403, detail="User not found")
        db_service = await get_database_service()

        device = await db_service.get_device_by_device_id(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        current_lifecycle = device.lifecycle_state
        eligible = (
            LifecycleState.ACTIVE.value,
            LifecycleState.SUSPENDED.value,
        )
        if current_lifecycle not in eligible:
            raise HTTPException(
                status_code=400,
                detail=f"Device lifecycle state is '{current_lifecycle}'; "
                "only 'active' or 'suspended' devices may be transferred",
            )

        # Verify access on source site
        verify_device_belongs_to_user(db_user, device, db, minimum_role="operator")

        # Verify access on target site
        verify_site_access_for_user(
            db_user, payload.target_site_id, db, minimum_role="operator"
        )

        # Validate target site exists
        target_site = (
            db.query(Site).filter(Site.site_id == payload.target_site_id).first()
        )
        if not target_site:
            raise HTTPException(
                status_code=404,
                detail=f"Target site '{payload.target_site_id}' not found",
            )

        if device.site_id == target_site.id:
            raise HTTPException(
                status_code=400,
                detail="Device is already assigned to the target site",
            )

        now = datetime.now(timezone.utc)

        # Close current assignment
        async with db_service.get_session() as session:
            current_assignment_result = await session.execute(
                select(DeviceAssignment).where(
                    DeviceAssignment.device_id == device.id,
                    DeviceAssignment.is_current,
                )
            )
            current_assignment = current_assignment_result.scalars().first()
            if current_assignment:
                current_assignment.is_current = False  # type: ignore[assignment]
                current_assignment.unassigned_at = now  # type: ignore[assignment]

            # Create new assignment
            new_assignment = DeviceAssignment(
                assignment_id=str(uuid.uuid4()),
                device_id=device.id,
                site_id=int(target_site.id),
                assignment_reason=payload.reason or "transfer",
                assigned_at=now,
                is_current=True,
            )
            session.add(new_assignment)

        # Close current epoch
        if device.lifecycle_epoch_id:
            async with db_service.get_session() as session:
                epoch_result = await session.execute(
                    select(LifecycleEpoch).where(
                        LifecycleEpoch.id == device.lifecycle_epoch_id
                    )
                )
                current_epoch = epoch_result.scalars().first()
                if current_epoch and not current_epoch.ended_at:
                    current_epoch.ended_at = now  # type: ignore[assignment]

        # Update device
        device.site_id = int(target_site.id)  # type: ignore[assignment]
        device.lifecycle_state = LifecycleState.ACTIVE.value  # type: ignore[assignment]
        device.is_active = True  # type: ignore[assignment]

        # Create new epoch
        async with db_service.get_session() as session:
            new_epoch = LifecycleEpoch(
                epoch_id=str(uuid.uuid4()),
                device_id=device.id,
                site_id=int(target_site.id),
                claimed_at=now,
                enrolment_method="transferred",
            )
            session.add(new_epoch)
            await session.flush()
            device.lifecycle_epoch_id = new_epoch.id  # type: ignore[assignment]

        # Revoke old credentials
        async with db_service.get_session() as session:
            cred_result = await session.execute(
                select(DeviceCredential).where(
                    DeviceCredential.device_id == device.id,
                    DeviceCredential.is_active,
                )
            )
            for cred in cred_result.scalars().all():
                cred.is_active = False  # type: ignore[assignment]
                cred.revoked_at = now  # type: ignore[assignment]

        # Issue new credential
        import secrets

        from homepot.app.auth_utils import hash_password

        new_api_key = secrets.token_urlsafe(32)
        new_key_hash = hash_password(new_api_key)

        async with db_service.get_session() as session:
            new_credential = DeviceCredential(
                credential_id=str(uuid.uuid4()),
                device_id=device.id,
                key_hash=new_key_hash,
                is_active=True,
            )
            session.add(new_credential)
        device.api_key_hash = new_key_hash  # type: ignore[assignment]

        await _record_lifecycle_event(
            db_service,
            device,
            from_state=str(current_lifecycle),
            to_state=LifecycleState.ACTIVE.value,
            triggered_by_user_id=int(db_user.id),
            reason=payload.reason or "transfer",
            idempotency_key=payload.idempotency_key,
        )

        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        audit_logger = get_audit_logger()
        await audit_logger.log_event(
            AuditEventType.DEVICE_TRANSFERRED,
            f"Device '{device.name}' ({device.device_id}) transferred from site "
            f"'{device.site_id if hasattr(device, 'site_id') else 'unknown'}' "
            f"to '{payload.target_site_id}' by {current_user['email']}"
            + (f" — {payload.reason}" if payload.reason else ""),
            device_id=int(device.id),
            site_id=int(target_site.id),
            user_id=int(db_user.id),
            ip_address=ip_address,
            user_agent=user_agent,
            old_values={
                "lifecycle_state": current_lifecycle,
                "site_id": str(device.site_id),
            },
            new_values={
                "lifecycle_state": LifecycleState.ACTIVE.value,
                "site_id": payload.target_site_id,
                "reason": payload.reason,
            },
            event_metadata={"idempotency_key": payload.idempotency_key},
        )

        logger.info(
            "Device transferred: %s -> site %s by %s",
            device_id,
            payload.target_site_id,
            current_user["email"],
        )

        return {
            "status": "success",
            "message": f"Device '{device_id}' transferred to site '{payload.target_site_id}'",
            "device_id": device_id,
            "target_site_id": payload.target_site_id,
            "api_key": new_api_key,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to transfer device {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.put("/device/{device_id}/monitor", tags=["Devices"])
async def toggle_device_monitor(
    device_id: str,
    monitor: bool,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Toggle the monitoring status of a device."""
    try:
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        db_service = await get_database_service()

        async with db_service.get_session() as session:
            result = await session.execute(
                select(Device).where(Device.device_id == device_id)
            )
            device = result.scalars().first()

            if not device:
                raise HTTPException(
                    status_code=404, detail=f"Device '{device_id}' not found"
                )

            # Verify access before modifying
            verify_device_belongs_to_user(db_user, device, db, minimum_role="operator")

            device.is_monitored = monitor  # type: ignore
            await session.commit()

            return {
                "message": f"Device monitoring {'enabled' if monitor else 'disabled'}",
                "device_id": device.device_id,
                "is_monitored": device.is_monitored,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update device monitor status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/sites/{site_id}/devices", tags=["Devices"])
async def get_devices_by_site(
    site_id: str,
    include_unpaired: bool = False,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> List[Dict[str, Any]]:
    """Get all devices for a specific site.

    Args:
        site_id: The site's business ID (e.g., 'site-123')
        include_unpaired: Whether to include devices that were unbound/soft-deleted

    Returns:
        List of devices belonging to the site

    Raises:
        HTTPException: 404 if site not found, 403 if no access
    """
    try:
        # Verify user can access this site
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
        devices = await db_service.get_devices_by_site_id(
            site_id, include_unpaired=include_unpaired
        )

        # Basic alert counting (can be optimized with a single query if needed)
        alert_map = {}
        if devices:
            device_ids = [d.device_id for d in devices]
            async with db_service.get_session() as session:
                alerts_query = (
                    select(
                        analytics_models.Alert.device_id,
                        func.count(analytics_models.Alert.id),
                    )
                    .where(
                        analytics_models.Alert.device_id.in_(device_ids),
                        analytics_models.Alert.status == "active",
                    )
                    .group_by(analytics_models.Alert.device_id)
                )
                result = await session.execute(alerts_query)
                for row in result:
                    # row is (device_id, count)
                    alert_map[row[0]] = row[1]

        return [
            {
                "site_id": site.site_id,
                "device_id": d.device_id,
                "name": d.name,
                "device_type": d.device_type,
                "os_details": d.os_details,
                "lifecycle_state": d.lifecycle_state,
                "connectivity_state": _compute_connectivity(d),
                "health_state": d.health_state or HealthState.UNKNOWN.value,
                "pairing_status": (
                    "unpaired"
                    if d.lifecycle_state
                    in (LifecycleState.UNPAIRED.value, LifecycleState.RETIRED.value)
                    else "paired"
                ),
                "status": d.status,
                "ip_address": d.ip_address,
                "is_monitored": d.is_monitored,
                "active_alerts": alert_map.get(d.device_id, 0),
                "enrollment_method": getattr(d, "enrollment_method", "pre-provisioned"),
                "last_seen": d.last_seen.isoformat() if d.last_seen else None,
                "last_heartbeat_at": (
                    d.last_heartbeat_at.isoformat() if d.last_heartbeat_at else None
                ),
                "credential_status": (
                    "active"
                    if any(c.is_active for c in (d.credentials or []))
                    else "inactive"
                ),
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            }
            for d in devices
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get devices for site {site_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to get devices. Please check server logs."
        )


@router.get("/device/{device_id}/metrics", tags=["Devices"])
async def get_device_metrics(
    device_id: str,
    limit: int = 100,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> List[Dict[str, Any]]:
    """Get performance metrics for a specific device."""
    try:
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            # First find the device PK
            result = await session.execute(
                select(Device).where(Device.device_id == device_id)
            )
            device = result.scalars().first()
            if not device:
                raise HTTPException(status_code=404, detail="Device not found")
            verify_device_belongs_to_user(db_user, device, db)

            # Fetch metrics
            metrics_result = await session.execute(
                select(analytics_models.DeviceMetrics)
                .where(analytics_models.DeviceMetrics.device_id == device.id)
                .order_by(desc(analytics_models.DeviceMetrics.timestamp))
                .limit(limit)
            )
            metrics = metrics_result.scalars().all()

            return [
                {
                    "timestamp": m.timestamp.isoformat(),
                    "cpu_percent": m.cpu_percent,
                    "memory_percent": m.memory_percent,
                    "disk_percent": m.disk_percent,
                    "network_latency_ms": m.network_latency_ms,
                    "transaction_count": m.transaction_count,
                    "error_rate": m.error_rate,
                    "extra_metrics": m.extra_metrics,
                }
                for m in metrics
            ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get metrics for {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/device/{device_id}/audit-logs", tags=["Devices"])
async def get_device_audit_logs(
    device_id: str,
    limit: int = 50,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> List[Dict[str, Any]]:
    """Get audit logs for a specific device."""
    try:
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            # Find device PK
            result = await session.execute(
                select(Device).where(Device.device_id == device_id)
            )
            device = result.scalars().first()
            if not device:
                raise HTTPException(status_code=404, detail="Device not found")
            verify_device_belongs_to_user(db_user, device, db)

            # Fetch logs
            logs_result = await session.execute(
                select(AuditLog)
                .where(AuditLog.device_id == device.id)
                .order_by(desc(AuditLog.created_at))
                .limit(limit)
            )
            logs = logs_result.scalars().all()

            return [
                {
                    "id": log.id,
                    "event_type": log.event_type,
                    "description": log.description,
                    "created_at": log.created_at.isoformat(),
                    "user_id": log.user_id,
                    "ip_address": log.ip_address,
                }
                for log in logs
            ]
    except HTTPException:
        raise


@router.get("/device/{device_id}/jobs", tags=["Devices"])
async def get_device_jobs(
    device_id: str,
    limit: int = 50,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> List[Dict[str, Any]]:
    """Get job history for a specific device."""
    try:
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            result = await session.execute(
                select(Device).where(Device.device_id == device_id)
            )
            device = result.scalars().first()
            if not device:
                raise HTTPException(status_code=404, detail="Device not found")
            verify_device_belongs_to_user(db_user, device, db)

            jobs_result = await session.execute(
                select(Job)
                .where(Job.device_id == device.id)
                .order_by(desc(Job.created_at))
                .limit(limit)
            )
            jobs = jobs_result.scalars().all()

            return [
                {
                    "job_id": j.job_id,
                    "action": j.action,
                    "status": j.status,
                    "priority": j.priority,
                    "created_at": j.created_at.isoformat(),
                    "completed_at": (
                        j.completed_at.isoformat() if j.completed_at else None
                    ),
                    "result": j.result,
                }
                for j in jobs
            ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get jobs for {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/device/{device_id}/error-logs", tags=["Devices"])
async def get_device_error_logs(
    device_id: str,
    limit: int = 50,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> List[Dict[str, Any]]:
    """Get error logs for a specific device."""
    try:
        from sqlalchemy import String as SA_String
        from sqlalchemy import cast as sa_cast

        db_user_opt = cast(
            "User", db.query(User).filter(User.email == current_user["email"]).first()
        )
        if not db_user_opt:
            raise HTTPException(status_code=403, detail="User not found")
        db_user: User = db_user_opt  # type: ignore[assignment]
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            dev_result = await session.execute(
                select(Device).where(Device.device_id == device_id)
            )
            dev = dev_result.scalars().first()
            if dev:
                verify_device_belongs_to_user(db_user, dev, db)

            # Query using the context JSON column since device_id column was removed
            errors_result = await session.execute(
                select(analytics_models.ErrorLog)
                .where(
                    sa_cast(
                        analytics_models.ErrorLog.context["original_device_id"],
                        SA_String,
                    )
                    == f'"{device_id}"'
                )
                .order_by(desc(analytics_models.ErrorLog.timestamp))
                .limit(limit)
            )
            # Fallback: check unquoted match if the cast result doesn't include quotes
            errors = errors_result.scalars().all()
            if not errors:
                errors_result = await session.execute(
                    select(analytics_models.ErrorLog)
                    .where(
                        sa_cast(
                            analytics_models.ErrorLog.context["original_device_id"],
                            SA_String,
                        )
                        == device_id
                    )
                    .order_by(desc(analytics_models.ErrorLog.timestamp))
                    .limit(limit)
                )
                errors = errors_result.scalars().all()

            return [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "category": e.category,
                    "severity": e.severity,
                    "error_code": e.error_code,
                    "error_message": e.error_message,
                    "resolved": e.resolved,
                    "context": e.context,
                }
                for e in errors
            ]
    except Exception as e:
        logger.error(f"Failed to get error logs for {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/device/{device_id}/push-logs", tags=["Devices"])
async def get_device_push_logs(device_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get push notification logs for a specific device."""
    try:
        # device_id column removed from schema due to mismatch.
        # Returning empty list until schema migration catches up.
        return []

        # db_service = await get_database_service()
        # async with db_service.get_session() as session:
        #     # Note: PushNotificationLog uses string device_id
        #     logs_result = await session.execute(
        #         select(analytics_models.PushNotificationLog)
        #         .where(analytics_models.PushNotificationLog.device_id == device_id)
        #         .order_by(desc(analytics_models.PushNotificationLog.sent_at))
        #         .limit(limit)
        #     )
        #     logs = logs_result.scalars().all()
        #
        #     return [
        #         {
        #             "message_id": log.message_id,
        #             "provider": log.provider,
        #             "status": log.status,
        #             "sent_at": log.sent_at.isoformat(),
        #             "received_at": (
        #                 log.received_at.isoformat() if log.received_at else None
        #             ),
        #             "error_message": log.error_message,
        #         }
        #         for log in logs
        #     ]
    except Exception as e:
        logger.error(f"Failed to get push logs for {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/device/{device_id}/alerts", tags=["Devices"])
async def get_device_alerts(
    device_id: str,
    limit: int = 5,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> List[Dict[str, Any]]:
    """Get active and recent alerts for a specific device."""
    try:
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            dev_result = await session.execute(
                select(Device).where(Device.device_id == device_id)
            )
            dev = dev_result.scalars().first()
            if not dev:
                raise HTTPException(status_code=404, detail="Device not found")
            verify_device_belongs_to_user(db_user, dev, db)

            alerts_result = await session.execute(
                select(analytics_models.Alert)
                .where(analytics_models.Alert.device_id == device_id)
                .order_by(
                    desc(analytics_models.Alert.status == "active"),
                    desc(analytics_models.Alert.timestamp),
                )
                .limit(limit)
            )
            alerts = alerts_result.scalars().all()

            return [
                {
                    "id": a.id,
                    "title": a.title,
                    "description": a.description,
                    "severity": a.severity,
                    "category": a.category,
                    "status": a.status,
                    "ai_confidence": a.ai_confidence,
                    "ai_recommendation": a.ai_recommendation,
                    "timestamp": a.timestamp.isoformat() if a.timestamp else None,
                    "resolved_at": (
                        a.resolved_at.isoformat() if a.resolved_at else None
                    ),
                    "resolved_by": a.resolved_by,
                }
                for a in alerts
            ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get alerts for {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
