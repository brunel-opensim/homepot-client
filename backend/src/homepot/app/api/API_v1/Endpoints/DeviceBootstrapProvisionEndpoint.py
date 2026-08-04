"""API endpoint for device bootstrap provisioning.

Uses a site-level bootstrap key instead of SSO JWT auth, enabling
devices to self-enrol without a user login session.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from homepot.app.auth_utils import verify_bootstrap_key
from homepot.app.schemas.bootstrap import (
    BootstrapProvisionRequest,
    BootstrapProvisionResponse,
    DeviceNameCheckRequest,
    DeviceNameCheckResponse,
)
from homepot.app.services.agent_service import AgentService
from homepot.database import get_db
from homepot.models import Site

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/bootstrap-provision",
    tags=["Devices"],
    response_model=Dict[str, Any],
)
def bootstrap_provision_device(
    payload: BootstrapProvisionRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Provision a new device using a site bootstrap key.

    No user authentication required — the bootstrap key acts as the
    enrolment credential.  The key is validated against the site's
    stored hash, then the device is created with an ACTIVE lifecycle
    state and one-time credentials are returned.
    """
    try:
        site = db.query(Site).filter(Site.site_id == payload.site_id).first()
        if not site:
            raise HTTPException(status_code=404, detail="Site not found")

        if not verify_bootstrap_key(
            payload.bootstrap_key,
            site,
            allow_dev_key=payload.provisioning_source == "emulator",
        ):
            if not site.bootstrap_key_hash:
                raise HTTPException(
                    status_code=401,
                    detail="Site does not have a bootstrap key configured",
                )
            raise HTTPException(status_code=401, detail="Invalid bootstrap key")

        service = AgentService(db)
        result = service.bootstrap_provision_device(payload)
        response_data = BootstrapProvisionResponse(**result)
        return {
            "status": "success",
            "message": "Device provisioned successfully",
            "data": response_data.model_dump(),
        }
    except HTTPException:
        raise
    except (LookupError, ValueError) as e:
        logger.error("Bootstrap provision validation failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected bootstrap provision error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/check-name",
    tags=["Devices"],
    response_model=Dict[str, Any],
)
def check_device_name(
    payload: DeviceNameCheckRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Check whether a device name is available in a site.

    Authenticated by the site bootstrap key, mirroring the provisioning
    endpoint so the User App can surface inline feedback before a device is
    actually enrolled.
    """
    site = db.query(Site).filter(Site.site_id == payload.site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    if not verify_bootstrap_key(payload.bootstrap_key, site, allow_dev_key=True):
        raise HTTPException(status_code=401, detail="Invalid bootstrap key")

    service = AgentService(db)
    available = service.device_name_available(payload.site_id, payload.device_name)
    response_data = DeviceNameCheckResponse(available=available)
    return {
        "status": "success",
        "data": response_data.model_dump(),
    }
