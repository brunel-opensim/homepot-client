"""API endpoint for device permission management.

Devices can write their own permissions via device-credential auth.
Operators can read permissions via the existing GET /devices/device/{id}.
"""

import copy
import logging
from typing import Any, Dict, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from homepot.app.auth_utils import (
    UserDict,
    get_current_device,
    require_user,
    verify_device_belongs_to_user,
)
from homepot.app.schemas.permissions import (
    DevicePermissions,
    DevicePermissionsResponse,
    DevicePermissionsUpdate,
)
from homepot.database import get_db
from homepot.models import Device, LifecycleState, User

logger = logging.getLogger(__name__)
router = APIRouter()


DEFAULT_PERMISSIONS: Dict[str, bool] = {
    "root_access": False,
    "process_monitoring": False,
    "filesystem_access": False,
    "network_monitoring": False,
}


def _normalise_permissions(raw: Any) -> Dict[str, bool]:
    """Return a safe permissions dict, filling in any missing keys."""
    if not raw or not isinstance(raw, dict):
        return dict(DEFAULT_PERMISSIONS)
    result = dict(DEFAULT_PERMISSIONS)
    result.update({k: bool(v) for k, v in raw.items() if k in DEFAULT_PERMISSIONS})
    return result


@router.patch(
    "/device/{device_id}/permissions",
    tags=["Devices"],
    response_model=Dict[str, Any],
)
def update_device_permissions(
    device_id: str,
    payload: DevicePermissionsUpdate,
    db: Session = Depends(get_db),
    current_device: Device = Depends(get_current_device),
) -> Dict[str, Any]:
    """Update permissions for a device.

    The device authenticates via ``X-Device-ID`` and ``X-API-Key`` headers
    (device-credential auth).  The device's lifecycle must be ``active``.
    Only the keys supplied in the request body are updated; unspecified
    keys retain their current value.
    """
    try:
        if current_device.device_id != device_id:
            raise HTTPException(
                status_code=403,
                detail="Device can only update its own permissions",
            )

        if current_device.lifecycle_state != LifecycleState.ACTIVE.value:
            raise HTTPException(
                status_code=403,
                detail=f"Device lifecycle state is '{current_device.lifecycle_state}'; "
                "only 'active' devices may set permissions",
            )

        current_perms = _normalise_permissions(current_device.device_permissions)
        incoming = payload.permissions.model_dump(exclude_unset=True)
        current_perms.update(incoming)

        current_device.device_permissions = copy.deepcopy(current_perms)  # type: ignore[arg-type]
        db.commit()

        logger.info(
            "Permissions updated for device_id=%s: %s",
            device_id,
            current_perms,
        )

        return {
            "status": "success",
            "message": "Device permissions updated",
            "data": DevicePermissionsResponse(
                device_id=device_id,
                permissions=DevicePermissions(**current_perms),
                message="Permissions updated",
            ).model_dump(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to update permissions for device %s: %s",
            device_id,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to update device permissions",
        )


@router.get(
    "/device/{device_id}/permissions",
    tags=["Devices"],
    response_model=Dict[str, Any],
)
def get_device_permissions(
    device_id: str,
    db: Session = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Get permissions for a device.

    Requires operator-level access on the device's site.
    """
    try:
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if not device:
            raise HTTPException(
                status_code=404, detail=f"Device '{device_id}' not found"
            )

        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        verify_device_belongs_to_user(db_user, device, db, minimum_role="operator")

        perms = _normalise_permissions(device.device_permissions)

        return {
            "status": "success",
            "data": DevicePermissionsResponse(
                device_id=device_id,
                permissions=DevicePermissions(**perms),
                message="Permissions retrieved",
            ).model_dump(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get permissions for device %s: %s",
            device_id,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to get device permissions",
        )
