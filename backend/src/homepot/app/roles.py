"""Canonical operator roles and privilege derivation.

Single source of truth for the operator role vocabulary. Historically four
vocabularies coexisted (``User.role`` free text, the ``TokenData`` projection,
``TenantMembership.role`` and ``SiteMembership.role``), which meant a role
assignment could mean different things depending on where it was read. Signup,
role updates and token issuance now all resolve roles through this module.

The two operator roles are:

``Admin``
    Full access. A small number of trusted operators.
``Technician``
    Field engineers working on devices and sites.

Device permission tiers (``root_access`` / the monitoring keys) are a separate,
device-owned consent system and are deliberately NOT modelled here.
"""

import os

ADMIN = "Admin"
TECHNICIAN = "Technician"

CANONICAL_ROLES = (ADMIN, TECHNICIAN)

#: Legacy spellings mapped onto the canonical vocabulary. ``Client`` was the
#: original default, ``Engineer`` was introduced later, and ``User`` was what
#: the role-update endpoint accepted. All three meant "non-admin operator".
LEGACY_ROLE_ALIASES = {
    "admin": ADMIN,
    "administrator": ADMIN,
    "client": TECHNICIAN,
    "user": TECHNICIAN,
    "engineer": TECHNICIAN,
    "technician": TECHNICIAN,
    "operator": TECHNICIAN,
    "installer": TECHNICIAN,
    "viewer": TECHNICIAN,
    "member": TECHNICIAN,
}


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# REVERT WHEN PRODUCTION READY
# While we are still in development, every operator is granted admin-equivalent
# access so that role granularity does not block feature work. Set
# HOMEPOT_DEV_UNIFIED_ACCESS=false to restore per-role privilege, in which case
# only an Admin is privileged and a Technician is an ordinary operator.
DEV_UNIFIED_ACCESS = _env_flag("HOMEPOT_DEV_UNIFIED_ACCESS", default=True)


def normalize_role(value: object) -> str:
    """Map any known role spelling onto a canonical role.

    Unknown or missing values resolve to ``Technician`` - the least privileged
    role - so an unrecognised value can never grant extra access.
    """
    if not isinstance(value, str):
        return TECHNICIAN
    return LEGACY_ROLE_ALIASES.get(value.strip().lower(), TECHNICIAN)


def is_privileged(role: object, *, dev_unified_access: bool | None = None) -> bool:
    """Whether ``role`` carries admin-equivalent access.

    While ``HOMEPOT_DEV_UNIFIED_ACCESS`` is on (the development default) every
    canonical role is privileged, so Admin and Technician behave identically.
    """
    unified = DEV_UNIFIED_ACCESS if dev_unified_access is None else dev_unified_access
    if unified:
        return True
    return normalize_role(role) == ADMIN
