"""Dashboard aggregate endpoints for the HOMEPOT system."""

import logging
from typing import Any, Dict, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as SASession

from homepot.app.auth_utils import (
    UserDict,
    require_user,
    verify_site_access_for_user,
)
from homepot.database import get_database_service, get_db
from homepot.models import Site, User

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/dashboard/summary", tags=["Dashboard"])
async def get_dashboard_summary(
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Get global dashboard aggregate counts.

    Returns device counts grouped by lifecycle_state, connectivity_state,
    and health_state, plus pending enrolment intents and command counts.
    """
    try:
        db_service = await get_database_service()
        return await db_service.get_dashboard_summary()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get dashboard summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to get dashboard summary. Please check server logs.",
        )


@router.get("/sites/{site_id}/dashboard", tags=["Dashboard"])
async def get_site_dashboard(
    site_id: str,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Get dashboard aggregate counts scoped to a specific site.

    Same breakdown as the global summary but filtered to devices,
    enrolment intents and commands belonging to the given site.
    """
    try:
        db_service = await get_database_service()

        db_user = cast(
            User, db.query(User).filter(User.email == current_user["email"]).first()
        )
        verify_site_access_for_user(db_user, site_id, db)

        # Resolve the integer site.id from the string site_id
        site = db.query(Site).filter(Site.site_id == site_id).first()
        if not site:
            raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")

        return await db_service.get_dashboard_summary(site_id=cast(int, site.id))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get dashboard for site {site_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to get site dashboard. Please check server logs.",
        )
