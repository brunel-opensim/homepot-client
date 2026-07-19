"""API endpoint for device provisioning."""

import logging
from typing import Any, Dict, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from homepot.app.auth_utils import (
    UserDict,
    require_user,
    verify_site_access_for_user,
)
from homepot.app.schemas.provision import (
    DeviceProvisionRequest,
    DeviceProvisionResponse,
)
from homepot.app.services.agent_service import AgentService
from homepot.database import get_db
from homepot.models import User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/provision",
    tags=["Devices"],
    response_model=Dict[str, Any],
)
def provision_device(
    payload: DeviceProvisionRequest,
    db: Session = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Provision a new device and return one-time credentials.

    Uses the authenticated user's identity (from JWT) as the provisioning
    authority rather than trusting the caller-provided ``user_identity``.
    Requires operator-level access on the target site.
    """
    logger.info(
        "Device provision request received for site_id=%s by user=%s",
        payload.site_id,
        current_user["email"],
    )
    try:
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        verify_site_access_for_user(
            db_user, payload.site_id, db, minimum_role="operator"
        )

        service = AgentService(db)
        user_email: str = current_user["email"] or ""  # type: ignore[assignment]
        result = service.provision_device(payload, provisioned_by=user_email)
        response_data = DeviceProvisionResponse(**result)
        return {
            "status": "success",
            "message": "Device provisioned successfully",
            "data": response_data.model_dump(),
        }
    except (LookupError, ValueError) as e:
        logger.error("Provision validation failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected provision error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
