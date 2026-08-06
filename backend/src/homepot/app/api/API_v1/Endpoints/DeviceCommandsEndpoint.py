"""API endpoints for managing device commands."""

from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session as SASession

from homepot.agent.utils.command_poller import (
    COMMAND_TYPES,
    required_permissions_for_command,
)
from homepot.app.auth_utils import (
    UserDict,
    get_current_device,
    require_user,
    verify_device_belongs_to_user,
)
from homepot.app.utils.limiter import limiter
from homepot.audit import AuditEventType, get_audit_logger
from homepot.database import get_database_service, get_db
from homepot.models import CommandStatus, Device, User

router = APIRouter()


class CreateCommandRequest(BaseModel):
    """Request model for creating a new command."""

    command_type: str
    payload: Optional[Dict[str, Any]] = None


class CommandHistoryResponse(BaseModel):
    """Response model for command history listing."""

    command_id: str
    command_type: str
    payload: Optional[Dict[str, Any]] = None
    status: CommandStatus
    result: Optional[Dict[str, Any]] = None
    created_at: str
    executed_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UpdateCommandStatusRequest(BaseModel):
    """Request model for updating command status."""

    status: CommandStatus
    result: Optional[Dict[str, Any]] = None


class CommandResponse(BaseModel):
    """Response model for command details."""

    command_id: str
    command_type: str
    payload: Optional[Dict[str, Any]] = None
    status: CommandStatus
    created_at: str

    model_config = ConfigDict(from_attributes=True)


# 1. Queue Command (Requires user with operator access to the device's site)
@router.post(
    "/{device_id}/commands",
    response_model=CommandResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("30/minute")
async def queue_command(
    device_id: str,
    command_request: CreateCommandRequest,
    request: Request,
    sync_db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> CommandResponse:
    """Queue a command for a specific device (by device_id string).

    Requires operator-level access on the device's site.
    """
    db_user = cast(
        User, sync_db.query(User).filter(User.email == current_user["email"]).first()
    )
    db = await get_database_service()
    device = await db.get_device_by_device_id(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    verify_device_belongs_to_user(db_user, device, sync_db, minimum_role="operator")

    command_type = command_request.command_type.strip().lower()
    if command_type not in COMMAND_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported command type: {command_request.command_type}",
        )

    permissions: Dict[str, bool] = (
        device.device_permissions if isinstance(device.device_permissions, dict) else {}
    )
    required_permissions = required_permissions_for_command(
        command_type, command_request.payload
    )
    missing_permissions = [
        key for key in required_permissions if not permissions.get(key, False)
    ]
    if missing_permissions:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Device owner has not granted the required permissions",
                "required_permissions": required_permissions,
                "missing_permissions": missing_permissions,
            },
        )

    command = await db.create_device_command(
        device_id=device.id,  # type: ignore
        command_type=command_type,
        payload=command_request.payload,
    )

    # Audit log
    audit_logger = get_audit_logger()
    await audit_logger.log_event(
        AuditEventType.COMMAND_QUEUED,
        f"User '{current_user['email']}' queued {command_type} "
        f"command for device '{device_id}'",
        user_id=db_user.id,  # type: ignore
        device_id=device.id,  # type: ignore
        site_id=device.site_id,  # type: ignore
        new_values={
            "command_id": str(command.command_id),
            "command_type": command_type,
            "payload": command_request.payload,
        },
    )

    return CommandResponse(
        command_id=command.command_id,  # type: ignore
        command_type=command.command_type,  # type: ignore
        payload=command.payload,  # type: ignore
        status=command.status,  # type: ignore
        created_at=command.created_at.isoformat(),  # type: ignore
    )


# 2. Get Pending Commands (Device only)
@router.get("/pending", response_model=List[CommandResponse])
async def get_pending_commands(
    current_device: Device = Depends(get_current_device),
) -> List[CommandResponse]:
    """Get all pending commands for the authenticated device."""
    db = await get_database_service()
    commands = await db.get_pending_commands_for_device(
        current_device.id  # type: ignore
    )
    return [
        CommandResponse(
            command_id=cmd.command_id,  # type: ignore
            command_type=cmd.command_type,  # type: ignore
            payload=cmd.payload,  # type: ignore
            status=cmd.status,  # type: ignore
            created_at=cmd.created_at.isoformat(),  # type: ignore
        )
        for cmd in commands
    ]


# 3. Ack Command (Device only)
@router.post(
    "/{device_id}/commands/{command_id}/ack",
    response_model=CommandResponse,
)
async def ack_command(
    device_id: str,
    command_id: str,
    current_device: Device = Depends(get_current_device),
) -> CommandResponse:
    """Acknowledge receipt of a command, transitioning it from PENDING to SENT.

    Called by the agent after it fetches a pending command to confirm delivery.
    """
    if current_device.device_id != device_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device ID mismatch",
        )

    db = await get_database_service()
    updated = await db.update_command_status(
        command_id=command_id,
        status=CommandStatus.SENT,
        device_id=cast(int, current_device.id),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Command not found")

    return CommandResponse(
        command_id=updated.command_id,  # type: ignore
        command_type=updated.command_type,  # type: ignore
        payload=updated.payload,  # type: ignore
        status=updated.status,  # type: ignore
        created_at=updated.created_at.isoformat(),  # type: ignore
    )


# 4. Update Command Status (Device only)
@router.put("/{command_id}/status", response_model=CommandResponse)
async def update_command_status(
    command_id: str,
    request: UpdateCommandStatusRequest,
    current_device: Device = Depends(get_current_device),
) -> CommandResponse:
    """Update the status of a command (e.g., COMPLETED, FAILED)."""
    db = await get_database_service()

    updated_command = await db.update_command_status(
        command_id=command_id,
        status=request.status,
        result=request.result,
        device_id=cast(int, current_device.id),
    )

    if not updated_command:
        raise HTTPException(status_code=404, detail="Command not found")

    return CommandResponse(
        command_id=updated_command.command_id,  # type: ignore
        command_type=updated_command.command_type,  # type: ignore
        payload=updated_command.payload,  # type: ignore
        status=updated_command.status,  # type: ignore
        created_at=updated_command.created_at.isoformat(),  # type: ignore
    )


# 5. Get Device Command History (User-facing)
@router.get(
    "/device/{device_id}/commands",
    response_model=List[CommandHistoryResponse],
)
async def get_device_command_history(
    device_id: str,
    sync_db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> List[CommandHistoryResponse]:
    """Get all commands for a device, sorted by created_at descending.

    Requires viewer-level access on the device's site.
    """
    db_user = cast(
        User, sync_db.query(User).filter(User.email == current_user["email"]).first()
    )
    db = await get_database_service()
    device = await db.get_device_by_device_id(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    verify_device_belongs_to_user(db_user, device, sync_db, minimum_role="viewer")

    commands = await db.get_commands_for_device(device.id)  # type: ignore
    return [
        CommandHistoryResponse(
            command_id=cmd.command_id,  # type: ignore
            command_type=cmd.command_type,  # type: ignore
            payload=cmd.payload,  # type: ignore
            status=cmd.status,  # type: ignore
            result=cmd.result,  # type: ignore
            created_at=cmd.created_at.isoformat(),  # type: ignore
            executed_at=cmd.executed_at.isoformat() if cmd.executed_at else None,  # type: ignore
        )
        for cmd in commands
    ]
