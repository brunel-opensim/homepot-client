from fastapi import APIRouter, Depends, HTTPException
from typing import Any, AsyncIterator, Dict, List, Optional
import logging
import asyncio
from homepot_client.client import HomepotClient
from pydantic import BaseModel
from homepot_client.database import close_database_service, get_database_service
from homepot_client.audit import AuditEventType, get_audit_logger


client_instance: Optional[HomepotClient] = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


router = APIRouter()


class SiteHealthResponse(BaseModel):
    """Response model for site health status."""

    site_id: str
    total_devices: int
    healthy_devices: int
    offline_devices: int
    error_devices: int
    health_percentage: float
    status_summary: str
    devices: List[Dict]
    last_updated: str


class CreateSiteRequest(BaseModel):
    """Request model for creating a new site."""

    site_id: str
    name: str
    description: Optional[str] = None
    location: Optional[str] = None

    class Config:
        """Pydantic model configuration with example data."""

        schema_extra = {
            "example": {
                "site_id": "site-123",
                "name": "Main Retail Store",
                "description": "Primary retail location with 5 POS terminals",
                "location": "London, UK",
            }
        }


def get_client() -> HomepotClient:
    """Dependency to get the client instance."""
    if client_instance is None:
        raise HTTPException(status_code=503, detail="Client not available")
    return client_instance


@router.post("/sites", tags=["Sites"], response_model=Dict[str, str])
async def create_site(site_request: CreateSiteRequest) -> Dict[str, str]:
    """Create a new site for device management."""
    try:
        db_service = await get_database_service()

        # Check if site already exists
        existing_site = await db_service.get_site_by_site_id(site_request.site_id)
        if existing_site:
            raise HTTPException(
                status_code=409, detail=f"Site {site_request.site_id} already exists"
            )

        # Create new site
        site = await db_service.create_site(
            site_id=site_request.site_id,
            name=site_request.name,
            description=site_request.description,
            location=site_request.location,
        )

        # Log audit event
        audit_logger = get_audit_logger()
        await audit_logger.log_event(
            AuditEventType.SITE_CREATED,
            f"Site '{site.name}' created with ID {site.site_id}",
            site_id=int(site.id),
            new_values={
                "site_id": str(site.site_id),
                "name": str(site.name),
                "description": str(site.description),
                "location": site.location,
            },
        )

        logger.info(f"Created site {site.site_id}")
        return {
            "message": f"Site {site.site_id} created successfully",
            "site_id": str(site.site_id),
            "name": str(site.name),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create site: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create site: {e}")


@router.get("/sites", tags=["Sites"])
async def list_sites() -> Dict[str, List[Dict]]:
    """List all sites."""
    try:
        db_service = await get_database_service()

        # For demo, we'll create a simple query (in real app, add pagination)
        from sqlalchemy import select

        from homepot_client.models import Site

        async with db_service.get_session() as session:
            result = await session.execute(
                select(Site)
                .where(Site.is_active.is_(True))
                .order_by(Site.created_at.desc())
            )
            sites = result.scalars().all()

            site_list = []
            for site in sites:
                site_list.append(
                    {
                        "site_id": site.site_id,
                        "name": site.name,
                        "description": site.description,
                        "location": site.location,
                        "created_at": (
                            site.created_at.isoformat() if site.created_at else None
                        ),
                    }
                )

            return {"sites": site_list}

    except Exception as e:
        logger.error(f"Failed to list sites: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list sites: {e}")


@router.get("/sites/{site_id}", tags=["Sites"])
async def get_site(site_id: str) -> Dict[str, Any]:
    """Get a specific site by site_id."""
    try:
        db_service = await get_database_service()

        # Look up site by site_id
        site = await db_service.get_site_by_site_id(site_id)

        if not site:
            raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")

        return {
            "site_id": site.site_id,
            "name": site.name,
            "description": site.description,
            "location": site.location,
            "is_active": site.is_active,
            "created_at": site.created_at.isoformat() if site.created_at else None,
            "updated_at": site.updated_at.isoformat() if site.updated_at else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get site {site_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get site: {e}")
