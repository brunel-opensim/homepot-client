"""Versioned UK demonstrator KPI export endpoint.

Exposes the Phase 2 reproducible KPI calculation (roadmap §Phase 2): a
time-bounded, site/device/type/provenance-filtered export with a
machine-readable KPI summary plus raw evidence, calculation version, Git
commit, units, timezone, and generation timestamp.
"""

from datetime import datetime
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from homepot.app.auth_utils import UserDict, require_user
from homepot.database import get_database_service
from homepot.kpi.export import compute_kpi_bundle, render_csv_summary
from homepot.kpi.models import PROVENANCE_CLASSES, ExportFilters

logger = logging.getLogger(__name__)
router = APIRouter()

EXPORT_FORMATS = ("json", "csv")


@router.get("/export", tags=["KPI"])
async def export_kpis(
    start: datetime,
    end: datetime,
    site_id: Optional[str] = None,
    device_id: Optional[str] = None,
    device_type: Optional[str] = None,
    provenance: Optional[str] = None,
    format: str = Query("json", description="json | csv"),
    current_user: UserDict = Depends(require_user()),
) -> Any:
    """Export a versioned, filtered KPI calculation bundle.

    ``json`` returns the machine-readable bundle (manifest + KPI summary +
    raw evidence). ``csv`` returns the KPI summary table as CSV with the
    manifest embedded as comment rows.
    """
    if format not in EXPORT_FORMATS:
        raise HTTPException(
            status_code=422,
            detail=f"format must be one of: {', '.join(EXPORT_FORMATS)}",
        )
    if provenance is not None and provenance not in PROVENANCE_CLASSES:
        raise HTTPException(
            status_code=422,
            detail=(f"provenance must be one of: {', '.join(PROVENANCE_CLASSES)}"),
        )
    if start > end:
        raise HTTPException(status_code=400, detail="start must not be after end")

    filters = ExportFilters(
        start=start,
        end=end,
        site_id=site_id,
        device_id=device_id,
        device_type=device_type,
        provenance=provenance,
    )

    try:
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            bundle = await compute_kpi_bundle(session, filters)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to compute KPI export: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to compute KPI export")

    if format == "csv":
        return Response(
            content=render_csv_summary(bundle),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="kpi-summary.csv"'},
        )
    return bundle.model_dump(mode="json")
