"""API endpoints for tenant and site membership management."""

import logging
from typing import Any, Dict, Generator, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from homepot.app.auth_utils import (
    TokenData,
    get_current_user,
    require_role,
)
from homepot.app.schemas.schemas import (
    SiteMembershipCreate,
    SiteMembershipOut,
    TenantCreate,
    TenantMembershipCreate,
    TenantMembershipOut,
    TenantOut,
    TenantUpdate,
    UserOutWithTenant,
)
from homepot.audit import AuditEventType, get_audit_logger
from homepot.database import SessionLocal
from homepot.models import Site, SiteMembership, Tenant, TenantMembership, User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


def get_db() -> Generator[Session, None, None]:
    """Get a sync database session for tenant operations."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---- Tenant CRUD ----


@router.post("/", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
async def create_tenant(  # type: ignore[no-untyped-def]
    tenant_data: TenantCreate,
    admin: Dict = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    """Create a new tenant/organisation."""
    existing = db.query(Tenant).filter(Tenant.slug == tenant_data.slug).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Tenant with slug '{tenant_data.slug}' already exists",
        )

    tenant = Tenant(
        name=tenant_data.name,
        slug=tenant_data.slug,
        settings=tenant_data.settings,
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    audit_logger = get_audit_logger()
    await audit_logger.log_event(
        AuditEventType.SITE_CREATED,
        f"Tenant '{tenant.name}' created",
        new_values={"name": tenant.name, "slug": tenant.slug},
    )

    logger.info(f"Created tenant {tenant.slug}")
    return tenant


@router.get("/", response_model=List[TenantOut])
async def list_tenants(  # type: ignore[no-untyped-def]
    admin: Dict = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    """List all active tenants."""
    tenants = (
        db.query(Tenant).filter(Tenant.is_active.is_(True)).order_by(Tenant.name).all()
    )
    return tenants


@router.get("/{tenant_id}", response_model=TenantOut)
async def get_tenant(  # type: ignore[no-untyped-def]
    tenant_id: int,
    admin: Dict = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    """Get a specific tenant by ID."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.put("/{tenant_id}", response_model=TenantOut)
async def update_tenant(  # type: ignore[no-untyped-def]
    tenant_id: int,
    tenant_data: TenantUpdate,
    admin: Dict = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    """Update a tenant's name or settings."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if tenant_data.name is not None:
        tenant.name = tenant_data.name  # type: ignore[assignment]
    if tenant_data.settings is not None:
        tenant.settings = tenant_data.settings  # type: ignore[assignment]

    db.commit()
    db.refresh(tenant)

    audit_logger = get_audit_logger()
    await audit_logger.log_event(
        AuditEventType.SITE_UPDATED,
        f"Tenant '{tenant.name}' updated",
        new_values={"name": tenant_data.name},
    )

    return tenant


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(  # type: ignore[no-untyped-def]
    tenant_id: int,
    admin: Dict = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    """Deactivate a tenant (soft delete to preserve referential integrity)."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant.is_active = False  # type: ignore[assignment]
    db.commit()

    audit_logger = get_audit_logger()
    await audit_logger.log_event(
        AuditEventType.SITE_DELETED,
        f"Tenant '{tenant.name}' deactivated",
        old_values={"slug": tenant.slug},
    )


# ---- Tenant Membership Management ----


@router.get(
    "/{tenant_id}/members",
    response_model=List[TenantMembershipOut],
)
async def list_tenant_members(  # type: ignore[no-untyped-def]
    tenant_id: int,
    admin: Dict = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    """List all members of a tenant."""
    memberships = (
        db.query(TenantMembership).filter(TenantMembership.tenant_id == tenant_id).all()
    )
    return memberships


@router.post(
    "/{tenant_id}/members",
    response_model=TenantMembershipOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_tenant_member(  # type: ignore[no-untyped-def]
    tenant_id: int,
    membership: TenantMembershipCreate,
    admin: Dict = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    """Add a user to a tenant with a role."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    user = db.query(User).filter(User.id == membership.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = (
        db.query(TenantMembership)
        .filter(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == membership.user_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="User is already a member of this tenant",
        )

    member = TenantMembership(
        user_id=membership.user_id,
        tenant_id=tenant_id,
        role=membership.role,
    )
    db.add(member)
    db.commit()
    db.refresh(member)

    logger.info(
        f"User {membership.user_id} added to tenant {tenant_id} as {membership.role}"
    )
    return member


@router.put(
    "/{tenant_id}/members/{membership_id}",
    response_model=TenantMembershipOut,
)
async def update_tenant_member_role(  # type: ignore[no-untyped-def]
    tenant_id: int,
    membership_id: int,
    role_update: TenantMembershipCreate,
    admin: Dict = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    """Update a tenant member's role."""
    member = (
        db.query(TenantMembership)
        .filter(
            TenantMembership.id == membership_id,
            TenantMembership.tenant_id == tenant_id,
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Membership not found")

    member.role = role_update.role  # type: ignore[assignment]
    db.commit()
    db.refresh(member)
    return member


@router.delete(
    "/{tenant_id}/members/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_tenant_member(  # type: ignore[no-untyped-def]
    tenant_id: int,
    membership_id: int,
    admin: Dict = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    """Remove a user from a tenant."""
    member = (
        db.query(TenantMembership)
        .filter(
            TenantMembership.id == membership_id,
            TenantMembership.tenant_id == tenant_id,
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Membership not found")

    db.delete(member)
    db.commit()


# ---- Site Membership Management ----


@router.get(
    "/{tenant_id}/sites/{site_id}/members",
    response_model=List[SiteMembershipOut],
)
async def list_site_members(  # type: ignore[no-untyped-def]
    tenant_id: int,
    site_id: int,
    admin: Dict = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    """List all members of a site scoped to a tenant."""
    site = (
        db.query(Site).filter(Site.id == site_id, Site.tenant_id == tenant_id).first()
    )
    if not site:
        raise HTTPException(status_code=404, detail="Site not found in this tenant")

    memberships = (
        db.query(SiteMembership).filter(SiteMembership.site_id == site_id).all()
    )
    return memberships


@router.post(
    "/{tenant_id}/sites/{site_id}/members",
    response_model=SiteMembershipOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_site_member(  # type: ignore[no-untyped-def]
    tenant_id: int,
    site_id: int,
    membership: SiteMembershipCreate,
    db: Session = Depends(get_db),
    admin: Dict = Depends(require_role("Admin")),
):
    """Add a user to a site with a role."""
    site = (
        db.query(Site).filter(Site.id == site_id, Site.tenant_id == tenant_id).first()
    )
    if not site:
        raise HTTPException(status_code=404, detail="Site not found in this tenant")

    user = db.query(User).filter(User.id == membership.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = (
        db.query(SiteMembership)
        .filter(
            SiteMembership.site_id == site_id,
            SiteMembership.user_id == membership.user_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="User is already a member of this site",
        )

    member = SiteMembership(
        user_id=membership.user_id,
        site_id=site_id,
        role=membership.role,
    )
    db.add(member)
    db.commit()
    db.refresh(member)

    logger.info(
        f"User {membership.user_id} added to site {site_id} as {membership.role}"
    )
    return member


@router.put(
    "/{tenant_id}/sites/{site_id}/members/{membership_id}",
    response_model=SiteMembershipOut,
)
async def update_site_member_role(  # type: ignore[no-untyped-def]
    tenant_id: int,
    site_id: int,
    membership_id: int,
    role_update: SiteMembershipCreate,
    admin: Dict = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    """Update a site member's role."""
    member = (
        db.query(SiteMembership)
        .filter(
            SiteMembership.id == membership_id,
            SiteMembership.site_id == site_id,
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Site membership not found")

    member.role = role_update.role  # type: ignore[assignment]
    db.commit()
    db.refresh(member)
    return member


@router.delete(
    "/{tenant_id}/sites/{site_id}/members/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_site_member(  # type: ignore[no-untyped-def]
    tenant_id: int,
    site_id: int,
    membership_id: int,
    admin: Dict = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    """Remove a user from a site."""
    member = (
        db.query(SiteMembership)
        .filter(
            SiteMembership.id == membership_id,
            SiteMembership.site_id == site_id,
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Site membership not found")

    db.delete(member)
    db.commit()


# ---- Tenant-scoped User Info ----


@router.get("/{tenant_id}/users", response_model=List[UserOutWithTenant])
async def list_tenant_users(  # type: ignore[no-untyped-def]
    tenant_id: int,
    admin: Dict = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    """List all users belonging to a tenant."""
    users = (
        db.query(User)
        .filter(User.tenant_id == tenant_id, User.is_active.is_(True))
        .all()
    )
    return users


# ---- My Memberships (for the current user) ----


@router.get("/me/memberships", response_model=Dict[str, Any])
async def get_my_memberships(  # type: ignore[no-untyped-def]
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all tenant and site memberships for the current user."""
    user = db.query(User).filter(User.email == current_user.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    tenant_memberships = (
        db.query(TenantMembership).filter(TenantMembership.user_id == user.id).all()
    )
    site_memberships = (
        db.query(SiteMembership).filter(SiteMembership.user_id == user.id).all()
    )

    return {
        "tenant_memberships": [
            {
                "id": m.id,
                "tenant_id": m.tenant_id,
                "role": m.role,
            }
            for m in tenant_memberships
        ],
        "site_memberships": [
            {
                "id": m.id,
                "site_id": m.site_id,
                "role": m.role,
            }
            for m in site_memberships
        ],
    }
