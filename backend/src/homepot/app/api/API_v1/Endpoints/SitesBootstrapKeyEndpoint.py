"""API endpoint for managing site bootstrap keys.

Bootstrap keys are stored as a bcrypt hash (for enrolment verification) plus
an encrypted-at-rest plaintext copy (``Site.bootstrap_key_enc``) so operators
can re-display the key from the UI and reuse it to enrol more devices.
"""

import logging
import secrets
from typing import Any, Dict, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from homepot.app.auth_utils import (
    UserDict,
    require_user,
    verify_site_access_for_user,
)
from homepot.app.schemas.bootstrap import BootstrapKeyResponse
from homepot.app.services.bootstrap_key_service import (
    clear_bootstrap_key,
    reveal_bootstrap_key,
    store_bootstrap_key,
)
from homepot.database import get_db
from homepot.models import Site, User

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_site_for_operator(site_id: str, db: Session, current_user: UserDict) -> Site:
    """Load the site after checking the caller has operator access."""
    db_user = cast(
        User, db.query(User).filter(User.email == current_user["email"]).first()
    )
    verify_site_access_for_user(db_user, site_id, db, minimum_role="operator")
    site = cast(Site, db.query(Site).filter(Site.site_id == site_id).first())
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.post(
    "/sites/{site_id}/bootstrap-key",
    tags=["Sites"],
    response_model=Dict[str, Any],
)
def generate_bootstrap_key(
    site_id: str,
    db: Session = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Generate (or regenerate) a bootstrap key for a site.

    Requires operator-level access on the target site.
    The plaintext key is returned in this response and stored encrypted at
    rest so it can be re-displayed via ``GET /sites/{site_id}/bootstrap-key``.
    """
    try:
        site = _get_site_for_operator(site_id, db, current_user)

        bootstrap_key = secrets.token_urlsafe(32)
        store_bootstrap_key(site, bootstrap_key)
        db.commit()

        logger.info(
            "Bootstrap key generated for site_id=%s by user=%s",
            site_id,
            current_user["email"],
        )

        return {
            "status": "success",
            "message": "Bootstrap key generated",
            "data": BootstrapKeyResponse(
                bootstrap_key=bootstrap_key,
                message="Key stored securely and available for reuse",
            ).model_dump(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate bootstrap key: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate bootstrap key")


@router.get(
    "/sites/{site_id}/bootstrap-key",
    tags=["Sites"],
    response_model=Dict[str, Any],
)
def get_bootstrap_key(
    site_id: str,
    db: Session = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Reveal the stored bootstrap key for reuse across devices.

    Requires operator-level access on the target site. Returns the original
    plaintext stored when the key was generated; 404 when the site has no
    key configured (or the stored value cannot be decrypted).
    """
    try:
        site = _get_site_for_operator(site_id, db, current_user)

        bootstrap_key = reveal_bootstrap_key(site)
        if not bootstrap_key:
            raise HTTPException(
                status_code=404,
                detail="No bootstrap key configured for this site",
            )

        logger.info(
            "Bootstrap key revealed for site_id=%s by user=%s",
            site_id,
            current_user["email"],
        )

        return {
            "status": "success",
            "message": "Bootstrap key retrieved",
            "data": BootstrapKeyResponse(
                bootstrap_key=bootstrap_key,
                message="Key stored securely and available for reuse",
            ).model_dump(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get bootstrap key: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get bootstrap key")


@router.delete(
    "/sites/{site_id}/bootstrap-key",
    tags=["Sites"],
    response_model=Dict[str, Any],
)
def revoke_bootstrap_key(
    site_id: str,
    db: Session = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Revoke a site's bootstrap key, disabling bootstrap provisioning.

    Requires operator-level access on the target site.
    """
    try:
        site = _get_site_for_operator(site_id, db, current_user)

        clear_bootstrap_key(site)
        db.commit()

        logger.info(
            "Bootstrap key revoked for site_id=%s by user=%s",
            site_id,
            current_user["email"],
        )

        return {
            "status": "success",
            "message": "Bootstrap key revoked",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to revoke bootstrap key: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to revoke bootstrap key")
