"""API endpoint for device permission management.

Devices can write their own permissions via device-credential auth.
Operators can read and override permissions via JWT auth.
"""

import copy
import logging
from typing import Any, Dict, Optional, cast

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
import jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from homepot.app.auth_utils import (
    ALGORITHM,
    SECRET_KEY,
    UserDict,
    api_key_header,
    authenticate_device_credentials,
    device_id_header,
    get_current_device,
    require_user,
    security,
    verify_device_belongs_to_user,
)
from homepot.app.schemas.permissions import (
    ALL_PERMISSION_KEYS,
    DeviceCapabilities,
    DevicePermissions,
    DevicePermissionsResponse,
    DevicePermissionsUpdate,
    derive_capabilities,
)
from homepot.database import get_db
from homepot.models import AuditLog, Device, LifecycleState, User

logger = logging.getLogger(__name__)
router = APIRouter()


DEFAULT_PERMISSIONS: Dict[str, bool] = {k: False for k in ALL_PERMISSION_KEYS}


def _normalise_permissions(raw: Any) -> Dict[str, bool]:
    """Return a safe permissions dict, filling in any missing keys."""
    if not raw or not isinstance(raw, dict):
        return dict(DEFAULT_PERMISSIONS)
    result = dict(DEFAULT_PERMISSIONS)
    result.update({k: bool(v) for k, v in raw.items() if k in DEFAULT_PERMISSIONS})
    return result


def _get_capabilities_dict(device: Device) -> Dict[str, bool]:
    """Return device capabilities or all-``False`` when unset."""
    caps = device.capabilities
    derived = derive_capabilities(cast(Optional[str], device.os_details))
    if not caps or not isinstance(caps, dict):
        return derived
    return {k: bool(caps.get(k, derived.get(k, False))) for k in ALL_PERMISSION_KEYS}


def _audit_permission_change(
    db: Session,
    device: Device,
    old_permissions: Dict[str, bool],
    new_permissions: Dict[str, bool],
    user_id: int | None = None,
) -> None:
    db.add(
        AuditLog(
            event_type="permission_change",
            description=f"Permissions changed for device '{device.device_id}'",
            user_id=user_id,
            device_id=device.id,
            site_id=device.site_id,
            old_values=old_permissions,
            new_values=new_permissions,
        )
    )


def _validate_against_capabilities(
    permissions: Dict[str, bool], capabilities: Dict[str, bool]
) -> None:
    """Raise ``422`` if any requested permission exceeds device capabilities."""
    for key, requested in permissions.items():
        if requested and not capabilities.get(key, False):
            raise HTTPException(
                status_code=422,
                detail=f"Permission '{key}' is not supported by this device's OS",
            )


def _build_response(
    device_id: str, perms: Dict[str, bool], caps: Dict[str, bool], msg: str
) -> Dict[str, Any]:
    return {
        "status": "success",
        "data": DevicePermissionsResponse(
            device_id=device_id,
            permissions=DevicePermissions(**perms),
            capabilities=DeviceCapabilities(**caps),
            message=msg,
        ).model_dump(),
    }


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
    """Update permissions for a device (device-credential auth).

    The device authenticates via ``X-Device-ID`` and ``X-API-Key`` headers.
    The device's lifecycle must be ``active``.
    Only the keys supplied are updated; unspecified keys retain their value.
    Permissions that exceed the device capabilities are rejected.
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

        capabilities = _get_capabilities_dict(current_device)
        incoming = payload.permissions.model_dump(exclude_unset=True)
        _validate_against_capabilities(incoming, capabilities)

        current_perms = _normalise_permissions(current_device.device_permissions)
        old_perms = dict(current_perms)
        current_perms.update(incoming)

        current_device.device_permissions = copy.deepcopy(current_perms)  # type: ignore[arg-type]
        _audit_permission_change(db, current_device, old_perms, current_perms)
        db.commit()

        logger.info(
            "Permissions updated (device auth) for device_id=%s: %s",
            device_id,
            current_perms,
        )

        return _build_response(
            device_id, current_perms, capabilities, "Permissions updated"
        )
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


class AdminPermissionsUpdate(BaseModel):
    """Request schema for operator-level permission override."""

    permissions: DevicePermissions


@router.patch(
    "/device/{device_id}/permissions/admin-override",
    tags=["Devices"],
    response_model=Dict[str, Any],
)
def admin_override_device_permissions(
    device_id: str,
    payload: AdminPermissionsUpdate,
    db: Session = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Revoke a device's permissions (operator JWT auth).

    Requires operator-level access on the device's site.
    Operators may revoke access in an emergency, but only the device owner can
    grant access through the User App consent flow.
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

        capabilities = _get_capabilities_dict(device)
        incoming = payload.permissions.model_dump(exclude_unset=True)
        attempted_grants = [key for key, value in incoming.items() if value]
        if attempted_grants:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Only the device owner can grant permissions",
                    "permissions": attempted_grants,
                },
            )
        _validate_against_capabilities(incoming, capabilities)

        current_perms = _normalise_permissions(device.device_permissions)
        old_perms = dict(current_perms)
        current_perms.update(incoming)

        device.device_permissions = copy.deepcopy(current_perms)  # type: ignore[arg-type]
        _audit_permission_change(
            db, device, old_perms, current_perms, user_id=cast(int, db_user.id)
        )
        db.commit()

        logger.info(
            "Permissions overridden (operator auth) for device_id=%s by user=%s: %s",
            device_id,
            current_user["email"],
            current_perms,
        )

        return _build_response(
            device_id, current_perms, capabilities, "Permissions overridden by operator"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to override permissions for device %s: %s",
            device_id,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to override device permissions",
        )


@router.get(
    "/device/{device_id}/permissions",
    tags=["Devices"],
    response_model=Dict[str, Any],
)
def get_device_permissions(
    device_id: str,
    db: Session = Depends(get_db),
    api_key: Optional[str] = Depends(api_key_header),
    device_id_header_val: Optional[str] = Depends(device_id_header),
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Dict[str, Any]:
    """Get permissions and capabilities for a device.

    Two authentication modes:
    - **Device credentials**: pass ``X-Device-ID`` + ``X-API-Key`` headers.
      The device can only read its own permissions.
    - **Operator JWT**: pass ``Authorization: Bearer <token>``.
      Requires operator-level access on the device's site.

    When both are present, device-credential auth takes precedence.
    """
    try:
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if not device:
            raise HTTPException(
                status_code=404, detail=f"Device '{device_id}' not found"
            )

        if api_key and device_id_header_val:
            auth_device = authenticate_device_credentials(
                db, device_id_header_val, api_key
            )
            if auth_device.device_id != device_id:
                raise HTTPException(
                    status_code=403,
                    detail="Device can only read its own permissions",
                )
        elif bearer_creds:
            try:
                payload = jwt.decode(
                    bearer_creds.credentials, SECRET_KEY, algorithms=[ALGORITHM]
                )
                email = payload.get("sub")
                if not email:
                    raise HTTPException(
                        status_code=401, detail="Invalid token: no email"
                    )
            except jwt.PyJWTError:
                raise HTTPException(status_code=401, detail="Invalid or expired token")
            db_user = cast(User, db.query(User).filter(User.email == email).first())
            if not db_user:
                raise HTTPException(status_code=403, detail="User not found")
            verify_device_belongs_to_user(db_user, device, db, minimum_role="operator")
        else:
            raise HTTPException(
                status_code=401,
                detail="Authentication required — provide device credentials or operator JWT",
            )

        perms = _normalise_permissions(device.device_permissions)
        caps = _get_capabilities_dict(device)

        return _build_response(device_id, perms, caps, "Permissions retrieved")
    except HTTPException:
        raise
    except Exception as h:
        logger.error(
            "Failed to get permissions for device %s: %s",
            device_id,
            h,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to get device permissions",
        )
