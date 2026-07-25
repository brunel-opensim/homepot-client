"""API endpoint for managing site bootstrap keys."""

import logging
import secrets
from typing import Any, Dict, cast

from fastapi import APIRouter, Depends, HTTPException
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from homepot.app.auth_utils import (
    UserDict,
    require_user,
    verify_site_access_for_user,
)
from homepot.app.schemas.bootstrap import BootstrapKeyResponse
from homepot.database import get_db
from homepot.models import Site, User

logger = logging.getLogger(__name__)
router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
    The plaintext key is returned **only** in this response.
    """
    try:
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        verify_site_access_for_user(db_user, site_id, db, minimum_role="operator")

        site = cast(Site, db.query(Site).filter(Site.site_id == site_id).first())
        if not site:
            raise HTTPException(status_code=404, detail="Site not found")

        bootstrap_key = secrets.token_urlsafe(32)
        site.bootstrap_key_hash = cast(str, pwd_context.hash(bootstrap_key))  # type: ignore[assignment]
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
                message="Store this key securely — it will not be shown again",
            ).model_dump(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate bootstrap key: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate bootstrap key")


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
        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        verify_site_access_for_user(db_user, site_id, db, minimum_role="operator")

        site = cast(Site, db.query(Site).filter(Site.site_id == site_id).first())
        if not site:
            raise HTTPException(status_code=404, detail="Site not found")

        site.bootstrap_key_hash = None  # type: ignore[assignment]
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
