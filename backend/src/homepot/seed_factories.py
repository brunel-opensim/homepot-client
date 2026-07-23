"""Reusable factory functions for creating seed data entities.

Each factory provides sensible defaults for every field and accepts
``**kwargs`` overrides.  They are the single source of truth for what
fields every entity receives, shared between the CLI seed script and
test fixtures.

Every entity provides three variants:
* ``create_*`` -- async, for use with ``AsyncSession`` (e.g. ``seed_data.py``).
* ``create_*_sync`` -- sync, for use with sync ``Session`` (e.g. test fixtures).
* ``build_*`` -- pure builder that returns an unsaved instance; sync tests
  that need to customise the object before adding it to a session can use
  these.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from homepot.models import (
    AuditLog,
    Device,
    DeviceCredential,
    DeviceLifecycleEvent,
    DeviceType,
    EnrolmentIntent,
    HealthCheck,
    HealthState,
    Job,
    JobPriority,
    JobStatus,
    LifecycleEpoch,
    LifecycleState,
    Site,
    SiteMembership,
    Tenant,
    TenantMembership,
    User,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash_password(password: str) -> str:
    return CryptContext(schemes=["bcrypt"], deprecated="auto").hash(password)


# ---------------------------------------------------------------------------
# Tenant
# ---------------------------------------------------------------------------


def build_tenant(
    *, name: str = "Default Tenant", slug: str | None = None, **kwargs: Any
) -> Tenant:
    """Build an unsaved Tenant instance."""
    if slug is None:
        slug = name.lower().replace(" ", "-")
    return Tenant(name=name, slug=slug, **kwargs)


async def create_tenant(session: AsyncSession, **kwargs: Any) -> Tenant:
    """Create and persist a Tenant using an async session."""
    tenant = build_tenant(**kwargs)
    session.add(tenant)
    await session.flush()
    return tenant


def create_tenant_sync(session: Session, **kwargs: Any) -> Tenant:
    """Create and persist a Tenant using a sync session."""
    tenant = build_tenant(**kwargs)
    session.add(tenant)
    session.flush()
    return tenant


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


def build_user(
    *,
    username: str = "test-user",
    email: str = "test@example.com",
    password: str = "password",
    **kwargs: Any,
) -> User:
    """Build an unsaved User instance."""
    kwargs.setdefault("hashed_password", _hash_password(password))
    return User(username=username, email=email, **kwargs)


async def create_user(session: AsyncSession, **kwargs: Any) -> User:
    """Create and persist a User using an async session."""
    user = build_user(**kwargs)
    session.add(user)
    await session.flush()
    return user


def create_user_sync(session: Session, **kwargs: Any) -> User:
    """Create and persist a User using a sync session."""
    user = build_user(**kwargs)
    session.add(user)
    session.flush()
    return user


# ---------------------------------------------------------------------------
# TenantMembership
# ---------------------------------------------------------------------------


def build_tenant_membership(
    *, user_id: int, tenant_id: int, role: str = "member", **kwargs: Any
) -> TenantMembership:
    """Build an unsaved TenantMembership instance."""
    return TenantMembership(user_id=user_id, tenant_id=tenant_id, role=role, **kwargs)


async def create_tenant_membership(
    session: AsyncSession, **kwargs: Any
) -> TenantMembership:
    """Create and persist a TenantMembership using an async session."""
    tm = build_tenant_membership(**kwargs)
    session.add(tm)
    await session.flush()
    return tm


def create_tenant_membership_sync(session: Session, **kwargs: Any) -> TenantMembership:
    """Create and persist a TenantMembership using a sync session."""
    tm = build_tenant_membership(**kwargs)
    session.add(tm)
    session.flush()
    return tm


# ---------------------------------------------------------------------------
# Site
# ---------------------------------------------------------------------------


def build_site(
    *, site_id: str | None = None, name: str = "Default Site", **kwargs: Any
) -> Site:
    """Build an unsaved Site instance."""
    if site_id is None:
        site_id = f"site-{uuid4().hex[:8]}"
    return Site(site_id=site_id, name=name, **kwargs)


async def create_site(session: AsyncSession, **kwargs: Any) -> Site:
    """Create and persist a Site using an async session."""
    site = build_site(**kwargs)
    session.add(site)
    await session.flush()
    return site


def create_site_sync(session: Session, **kwargs: Any) -> Site:
    """Create and persist a Site using a sync session."""
    site = build_site(**kwargs)
    session.add(site)
    session.flush()
    return site


# ---------------------------------------------------------------------------
# SiteMembership
# ---------------------------------------------------------------------------


def build_site_membership(
    *, user_id: int, site_id: int, role: str = "viewer", **kwargs: Any
) -> SiteMembership:
    """Build an unsaved SiteMembership instance."""
    return SiteMembership(user_id=user_id, site_id=site_id, role=role, **kwargs)


async def create_site_membership(
    session: AsyncSession, **kwargs: Any
) -> SiteMembership:
    """Create and persist a SiteMembership using an async session."""
    sm = build_site_membership(**kwargs)
    session.add(sm)
    await session.flush()
    return sm


def create_site_membership_sync(session: Session, **kwargs: Any) -> SiteMembership:
    """Create and persist a SiteMembership using a sync session."""
    sm = build_site_membership(**kwargs)
    session.add(sm)
    session.flush()
    return sm


# ---------------------------------------------------------------------------
# Device
# ---------------------------------------------------------------------------


def build_device(
    *,
    device_id: str | None = None,
    name: str = "Default Device",
    device_type: str = DeviceType.UNKNOWN,
    site_id: int,
    **kwargs: Any,
) -> Device:
    """Build an unsaved Device instance."""
    if device_id is None:
        device_id = f"dev-{uuid4().hex[:8]}"
    kwargs.setdefault("lifecycle_state", LifecycleState.PENDING.value)
    kwargs.setdefault("health_state", HealthState.UNKNOWN.value)
    return Device(
        device_id=device_id,
        name=name,
        device_type=device_type,
        site_id=site_id,
        **kwargs,
    )


async def create_device(session: AsyncSession, **kwargs: Any) -> Device:
    """Create and persist a Device using an async session."""
    device = build_device(**kwargs)
    session.add(device)
    await session.flush()
    return device


def create_device_sync(session: Session, **kwargs: Any) -> Device:
    """Create and persist a Device using a sync session."""
    device = build_device(**kwargs)
    session.add(device)
    session.flush()
    return device


# ---------------------------------------------------------------------------
# LifecycleEpoch
# ---------------------------------------------------------------------------


def build_lifecycle_epoch(
    *, device_id: int, site_id: int, **kwargs: Any
) -> LifecycleEpoch:
    """Build an unsaved LifecycleEpoch instance."""
    kwargs.setdefault("epoch_id", str(uuid4()))
    kwargs.setdefault("claimed_at", _utc_now())
    kwargs.setdefault("enrolment_method", "pre-provisioned")
    return LifecycleEpoch(device_id=device_id, site_id=site_id, **kwargs)


async def create_lifecycle_epoch(
    session: AsyncSession, **kwargs: Any
) -> LifecycleEpoch:
    """Create and persist a LifecycleEpoch using an async session."""
    epoch = build_lifecycle_epoch(**kwargs)
    session.add(epoch)
    await session.flush()
    return epoch


def create_lifecycle_epoch_sync(session: Session, **kwargs: Any) -> LifecycleEpoch:
    """Create and persist a LifecycleEpoch using a sync session."""
    epoch = build_lifecycle_epoch(**kwargs)
    session.add(epoch)
    session.flush()
    return epoch


# ---------------------------------------------------------------------------
# DeviceLifecycleEvent
# ---------------------------------------------------------------------------


def build_device_lifecycle_event(
    *, device_id: int, to_state: str = LifecycleState.PENDING, **kwargs: Any
) -> DeviceLifecycleEvent:
    """Build an unsaved DeviceLifecycleEvent instance."""
    kwargs.setdefault("event_id", str(uuid4()))
    return DeviceLifecycleEvent(device_id=device_id, to_state=to_state, **kwargs)


async def create_device_lifecycle_event(
    session: AsyncSession, **kwargs: Any
) -> DeviceLifecycleEvent:
    """Create and persist a DeviceLifecycleEvent using an async session."""
    event = build_device_lifecycle_event(**kwargs)
    session.add(event)
    await session.flush()
    return event


def create_device_lifecycle_event_sync(
    session: Session, **kwargs: Any
) -> DeviceLifecycleEvent:
    """Create and persist a DeviceLifecycleEvent using a sync session."""
    event = build_device_lifecycle_event(**kwargs)
    session.add(event)
    session.flush()
    return event


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------


def build_job(
    *,
    job_id: str | None = None,
    action: str = "test-action",
    site_id: int,
    created_by: int,
    **kwargs: Any,
) -> Job:
    """Build an unsaved Job instance."""
    if job_id is None:
        job_id = f"job-{uuid4().hex[:12]}"
    kwargs.setdefault("priority", JobPriority.NORMAL)
    kwargs.setdefault("status", JobStatus.PENDING)
    return Job(
        job_id=job_id, action=action, site_id=site_id, created_by=created_by, **kwargs
    )


async def create_job(session: AsyncSession, **kwargs: Any) -> Job:
    """Create and persist a Job using an async session."""
    job = build_job(**kwargs)
    session.add(job)
    await session.flush()
    return job


def create_job_sync(session: Session, **kwargs: Any) -> Job:
    """Create and persist a Job using a sync session."""
    job = build_job(**kwargs)
    session.add(job)
    session.flush()
    return job


# ---------------------------------------------------------------------------
# HealthCheck
# ---------------------------------------------------------------------------


def build_health_check(
    *, device_id: int, is_healthy: bool = True, **kwargs: Any
) -> HealthCheck:
    """Build an unsaved HealthCheck instance."""
    return HealthCheck(device_id=device_id, is_healthy=is_healthy, **kwargs)


async def create_health_check(session: AsyncSession, **kwargs: Any) -> HealthCheck:
    """Create and persist a HealthCheck using an async session."""
    hc = build_health_check(**kwargs)
    session.add(hc)
    await session.flush()
    return hc


def create_health_check_sync(session: Session, **kwargs: Any) -> HealthCheck:
    """Create and persist a HealthCheck using a sync session."""
    hc = build_health_check(**kwargs)
    session.add(hc)
    session.flush()
    return hc


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------


def build_audit_log(
    *,
    event_type: str = "system_event",
    description: str = "Audit log entry",
    **kwargs: Any,
) -> AuditLog:
    """Build an unsaved AuditLog instance."""
    return AuditLog(event_type=event_type, description=description, **kwargs)


async def create_audit_log(session: AsyncSession, **kwargs: Any) -> AuditLog:
    """Create and persist an AuditLog using an async session."""
    log = build_audit_log(**kwargs)
    session.add(log)
    await session.flush()
    return log


def create_audit_log_sync(session: Session, **kwargs: Any) -> AuditLog:
    """Create and persist an AuditLog using a sync session."""
    log = build_audit_log(**kwargs)
    session.add(log)
    session.flush()
    return log


# ---------------------------------------------------------------------------
# EnrolmentIntent
# ---------------------------------------------------------------------------


def build_enrolment_intent(
    *,
    intent_id: str | None = None,
    site_id: int,
    enrolment_method: str = "pre-provisioned",
    expires_at: datetime | None = None,
    creator_id: int,
    **kwargs: Any,
) -> EnrolmentIntent:
    """Build an unsaved EnrolmentIntent instance."""
    if intent_id is None:
        intent_id = str(uuid4())
    if expires_at is None:
        expires_at = _utc_now()
    return EnrolmentIntent(
        intent_id=intent_id,
        site_id=site_id,
        enrolment_method=enrolment_method,
        expires_at=expires_at,
        creator_id=creator_id,
        **kwargs,
    )


async def create_enrolment_intent(
    session: AsyncSession, **kwargs: Any
) -> EnrolmentIntent:
    """Create and persist an EnrolmentIntent using an async session."""
    intent = build_enrolment_intent(**kwargs)
    session.add(intent)
    await session.flush()
    return intent


def create_enrolment_intent_sync(session: Session, **kwargs: Any) -> EnrolmentIntent:
    """Create and persist an EnrolmentIntent using a sync session."""
    intent = build_enrolment_intent(**kwargs)
    session.add(intent)
    session.flush()
    return intent


# ---------------------------------------------------------------------------
# DeviceCredential
# ---------------------------------------------------------------------------


def build_device_credential(
    *, credential_id: str | None = None, device_id: int, key_hash: str, **kwargs: Any
) -> DeviceCredential:
    """Build an unsaved DeviceCredential instance."""
    if credential_id is None:
        credential_id = str(uuid4())
    return DeviceCredential(
        credential_id=credential_id, device_id=device_id, key_hash=key_hash, **kwargs
    )


async def create_device_credential(
    session: AsyncSession, **kwargs: Any
) -> DeviceCredential:
    """Create and persist a DeviceCredential using an async session."""
    cred = build_device_credential(**kwargs)
    session.add(cred)
    await session.flush()
    return cred


def create_device_credential_sync(session: Session, **kwargs: Any) -> DeviceCredential:
    """Create and persist a DeviceCredential using a sync session."""
    cred = build_device_credential(**kwargs)
    session.add(cred)
    session.flush()
    return cred
