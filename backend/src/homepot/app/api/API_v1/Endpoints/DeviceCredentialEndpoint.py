"""API endpoints for device credential management (rotation, revocation)."""

import logging
import secrets
from typing import Any, Dict
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from homepot.app.auth_utils import (
    UserDict,
    hash_password,
    require_user,
    verify_site_access_for_user,
)
from homepot.database import get_db
from homepot.models import Device, DeviceCredential, LifecycleState, User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/device/{device_id}/rotate-key",
    tags=["Devices"],
    response_model=Dict[str, Any],
)
def rotate_device_key(
    device_id: str,
    db: Session = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Rotate a device's API key.

    Revokes the current active credential and issues a new one.
    The new plaintext key is returned **only once**.
    Requires operator-level access on the device's site.
    Verified device must be in ``active`` lifecycle state.
    """
    try:
        db_user = db.query(User).filter(User.email == current_user["email"]).first()
        if not db_user:
            raise HTTPException(status_code=403, detail="User not found")

        result = db.execute(select(Device).where(Device.device_id == device_id))
        device = result.scalars().first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        verify_site_access_for_user(
            db_user,
            device.site.site_id if device.site else "",
            db,
            minimum_role="operator",
        )

        # Reject rotation for inactive lifecycle states
        if device.lifecycle_state != LifecycleState.ACTIVE.value:
            raise HTTPException(
                status_code=400,
                detail=f"Device lifecycle state is '{device.lifecycle_state}'; "
                "only 'active' devices may rotate keys",
            )

        # Revoke current active credential(s)
        cred_result = db.execute(
            select(DeviceCredential).where(
                DeviceCredential.device_id == device.id,
                DeviceCredential.is_active,
            )
        )
        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        for cred in cred_result.scalars().all():
            cred.is_active = False  # type: ignore[assignment]
            cred.revoked_at = now  # type: ignore[assignment]

        # Generate new key and hash
        new_api_key = secrets.token_urlsafe(32)
        new_key_hash = hash_password(new_api_key)

        # Create new credential record
        new_credential = DeviceCredential(
            credential_id=str(uuid.uuid4()),
            device_id=device.id,
            key_hash=new_key_hash,
            is_active=True,
        )
        db.add(new_credential)

        # Update device-level hash (backward compat)
        device.api_key_hash = new_key_hash  # type: ignore[assignment]

        db.commit()

        logger.info(
            "API key rotated for device=%s by user=%s",
            device_id,
            current_user["email"],
        )

        return {
            "status": "success",
            "message": "Device API key rotated successfully",
            "device_id": device_id,
            "api_key": new_api_key,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to rotate device key: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
