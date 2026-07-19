"""API endpoints for managing enrolment intents."""

from datetime import datetime, timedelta, timezone
import logging
import secrets
from typing import Any, Dict, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from homepot.app.auth_utils import (
    UserDict,
    require_user,
    verify_site_access_for_user,
)
from homepot.app.schemas.enrolment import (
    EnrolmentIntentApprove,
    EnrolmentIntentClaim,
    EnrolmentIntentCreate,
)
from homepot.database import get_database_service, get_db
from homepot.models import (
    EnrolmentIntent,
    EnrolmentIntentStatus,
    Site,
    User,
)

logger = logging.getLogger(__name__)
router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _get_site_by_site_id(db: Session, site_str_id: str) -> Site:
    """Look up a Site by its string site_id, raising 404 if not found."""
    site = db.query(Site).filter(Site.site_id == site_str_id).first()
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{site_str_id}' not found")
    return site


def _get_intent_by_id_sync(db: Session, intent_id: str) -> Optional[EnrolmentIntent]:
    """Look up an EnrolmentIntent by its public intent_id (sync)."""
    return (
        db.query(EnrolmentIntent).filter(EnrolmentIntent.intent_id == intent_id).first()
    )


@router.post(
    "/sites/{site_id}/enrolment-intents",
    tags=["Enrolment Intents"],
    response_model=Dict[str, Any],
)
def create_enrolment_intent(
    site_id: str,
    payload: EnrolmentIntentCreate,
    db: Session = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Create a new enrolment intent for a site.

    Requires operator-level access on the target site.
    """
    try:
        current_db_user = (
            db.query(User).filter(User.email == current_user["email"]).first()
        )
        if not current_db_user:
            raise HTTPException(status_code=403, detail="User not found")
        db_user: User = current_db_user  # type: ignore[assignment]
        site = _get_site_by_site_id(db, site_id)
        verify_site_access_for_user(db_user, site_id, db, minimum_role="operator")

        # Check idempotency
        if payload.idempotency_key:
            existing = (
                db.query(EnrolmentIntent)
                .filter(EnrolmentIntent.idempotency_key == payload.idempotency_key)
                .first()
            )
            if existing:
                return {
                    "status": "success",
                    "message": "Enrolment intent already exists",
                    "intent_id": existing.intent_id,
                }

        intent_id = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=payload.expires_in_hours
        )

        # Generate a one-time claim token
        claim_token = secrets.token_urlsafe(32)
        claim_token_hash = pwd_context.hash(claim_token)

        import asyncio

        async def _create() -> EnrolmentIntent:
            svc = await get_database_service()
            intent = await svc.create_enrolment_intent(
                intent_id=intent_id,
                site_id=site.id,  # type: ignore[arg-type]
                tenant_id=site.tenant_id,  # type: ignore[arg-type]
                enrolment_method=payload.enrolment_method,
                claim_token_hash=claim_token_hash,
                expires_at=expires_at,
                creator_id=db_user.id,  # type: ignore[arg-type]
                idempotency_key=payload.idempotency_key,
                expected_device_identity=payload.expected_device_identity,
            )
            return intent

        intent = asyncio.run(_create())
        return {
            "status": "success",
            "message": "Enrolment intent created",
            "intent_id": intent.intent_id,
            "claim_token": claim_token,
            "expires_at": expires_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create enrolment intent: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/sites/{site_id}/enrolment-intents",
    tags=["Enrolment Intents"],
    response_model=Dict[str, Any],
)
def list_enrolment_intents(
    site_id: str,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """List enrolment intents for a site."""
    try:
        current_db_user = (
            db.query(User).filter(User.email == current_user["email"]).first()
        )
        if not current_db_user:
            raise HTTPException(status_code=403, detail="User not found")
        db_user: User = current_db_user  # type: ignore[assignment]
        site = _get_site_by_site_id(db, site_id)
        verify_site_access_for_user(db_user, site_id, db, minimum_role="viewer")

        import asyncio

        async def _list() -> tuple:
            svc = await get_database_service()
            intents = await svc.get_enrolment_intents_by_site(
                site.id, status=status, limit=limit, offset=offset  # type: ignore[arg-type]
            )
            total = await svc.count_enrolment_intents_by_site(
                site.id, status=status  # type: ignore[arg-type]
            )
            return intents, total

        intents, total = asyncio.run(_list())
        return {
            "intents": [
                {
                    "id": i.id,
                    "intent_id": i.intent_id,
                    "enrolment_method": i.enrolment_method,
                    "expected_device_identity": i.expected_device_identity,
                    "expires_at": i.expires_at.isoformat() if i.expires_at else None,
                    "consumed_at": i.consumed_at.isoformat() if i.consumed_at else None,
                    "creator_id": i.creator_id,
                    "status": i.status,
                    "idempotency_key": i.idempotency_key,
                    "created_at": i.created_at.isoformat(),
                    "updated_at": i.updated_at.isoformat(),
                }
                for i in intents
            ],
            "total": total,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list enrolment intents: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/sites/{site_id}/enrolment-intents/{intent_id}",
    tags=["Enrolment Intents"],
    response_model=Dict[str, Any],
)
def get_enrolment_intent(
    site_id: str,
    intent_id: str,
    db: Session = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Get details of a specific enrolment intent."""
    try:
        current_db_user = (
            db.query(User).filter(User.email == current_user["email"]).first()
        )
        if not current_db_user:
            raise HTTPException(status_code=403, detail="User not found")
        db_user: User = current_db_user  # type: ignore[assignment]
        _get_site_by_site_id(db, site_id)
        verify_site_access_for_user(db_user, site_id, db, minimum_role="viewer")

        intent = _get_intent_by_id_sync(db, intent_id)
        if not intent:
            raise HTTPException(status_code=404, detail="Enrolment intent not found")

        return {
            "id": intent.id,
            "intent_id": intent.intent_id,
            "site_id": intent.site_id,
            "tenant_id": intent.tenant_id,
            "enrolment_method": intent.enrolment_method,
            "expected_device_identity": intent.expected_device_identity,
            "expires_at": intent.expires_at.isoformat() if intent.expires_at else None,
            "consumed_at": (
                intent.consumed_at.isoformat() if intent.consumed_at else None
            ),
            "creator_id": intent.creator_id,
            "status": intent.status,
            "idempotency_key": intent.idempotency_key,
            "created_at": intent.created_at.isoformat(),
            "updated_at": intent.updated_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get enrolment intent: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/sites/{site_id}/enrolment-intents/{intent_id}",
    tags=["Enrolment Intents"],
    response_model=Dict[str, Any],
)
def update_enrolment_intent_status(
    site_id: str,
    intent_id: str,
    payload: EnrolmentIntentApprove,
    db: Session = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Approve or reject a pending enrolment intent.

    Requires operator-level access on the target site.
    """
    try:
        current_db_user = (
            db.query(User).filter(User.email == current_user["email"]).first()
        )
        if not current_db_user:
            raise HTTPException(status_code=403, detail="User not found")
        db_user: User = current_db_user  # type: ignore[assignment]
        _get_site_by_site_id(db, site_id)
        verify_site_access_for_user(db_user, site_id, db, minimum_role="operator")

        intent = _get_intent_by_id_sync(db, intent_id)
        if not intent:
            raise HTTPException(status_code=404, detail="Enrolment intent not found")
        if intent.status != EnrolmentIntentStatus.PENDING:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot update intent in status '{intent.status}'",
            )

        new_status = EnrolmentIntentStatus(payload.status)

        import asyncio

        async def _update() -> Any:
            svc = await get_database_service()
            return await svc.update_enrolment_intent_status(
                intent_id=intent_id, status=new_status
            )

        updated = asyncio.run(_update())
        return {
            "status": "success",
            "message": f"Enrolment intent {new_status.value}",
            "intent_id": updated.intent_id,
            "new_status": updated.status,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update enrolment intent: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/enrolment-intents/{intent_id}/claim",
    tags=["Enrolment Intents"],
    response_model=Dict[str, Any],
)
def claim_enrolment_intent(
    intent_id: str,
    payload: EnrolmentIntentClaim,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Claim an enrolment intent using its one-time claim token.

    This endpoint is used by the device/app side (no user auth required).
    On success, a device is created in PENDING lifecycle state and
    device credentials are returned.
    """
    try:
        intent = _get_intent_by_id_sync(db, intent_id)
        if not intent:
            raise HTTPException(status_code=404, detail="Enrolment intent not found")

        # Validate intent is in a claimable state
        if intent.status != EnrolmentIntentStatus.APPROVED:
            raise HTTPException(
                status_code=400,
                detail=f"Intent must be approved before claiming (current: {intent.status})",
            )

        if intent.expires_at and intent.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Enrolment intent has expired")

        # Verify claim token
        if not intent.claim_token_hash or not pwd_context.verify(
            payload.claim_token, intent.claim_token_hash  # type: ignore[arg-type]
        ):
            raise HTTPException(status_code=401, detail="Invalid claim token")

        # Create the device
        new_device_id = f"{payload.device_type}-{secrets.token_hex(4)}"
        api_key = secrets.token_urlsafe(32)
        api_key_hash = pwd_context.hash(api_key)

        async def _create_device() -> Any:
            svc = await get_database_service()
            device = await svc.create_device(
                device_id=new_device_id,
                name=payload.device_name or new_device_id,
                device_type=payload.device_type,
                site_id=intent.site_id,  # type: ignore[arg-type]
                api_key_hash=api_key_hash,
                enrollment_method=intent.enrolment_method,  # type: ignore[arg-type]
            )
            return device

        # Mark intent as consumed
        async def _consume_intent() -> None:
            svc = await get_database_service()
            await svc.update_enrolment_intent_status(
                intent_id=intent_id,
                status=EnrolmentIntentStatus.CONSUMED,
                consumed_at=datetime.now(timezone.utc),
            )

        import asyncio

        asyncio.run(_create_device())
        asyncio.run(_consume_intent())

        return {
            "status": "success",
            "message": "Device claimed successfully",
            "device_id": new_device_id,
            "api_key": api_key,
            "site_id": intent.site_id,  # type: ignore[arg-type]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to claim enrolment intent: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
