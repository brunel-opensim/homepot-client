"""Authentication and authorization utilities for the HomePot system."""

from datetime import datetime, timedelta, timezone
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, cast

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
import jwt
from jwt.exceptions import PyJWTError
from passlib.context import CryptContext
from pydantic import BaseModel
import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from homepot.app.schemas.schemas import UserDict
from homepot.database import get_db
from homepot.models import (
    Device,
    LifecycleState,
    Site,
    SiteMembership,
    Tenant,
    TenantMembership,
    User,
)

# Ensure environment variables are loaded
# load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[3]
env_path = BASE_DIR / ".env.example"

load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_SECRET_KEY = os.getenv("SECRET_KEY")
if not _SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is not set!")
SECRET_KEY: str = _SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 1
REFRESH_TOKEN_EXPIRE_DAYS = 7

COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"
API_KEY_HEADER_NAME = "X-API-Key"
DEVICE_ID_HEADER_NAME = "X-Device-ID"

# Google SSO Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # nosec # noqa: S105

# Cookie and Frontend Settings
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")  # "lax", "strict", or "none"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


def validate_google_config() -> bool:
    """Validate that Google SSO configuration is present and log status."""
    missing = []
    if not GOOGLE_CLIENT_ID:
        missing.append("GOOGLE_CLIENT_ID")
    if not GOOGLE_CLIENT_SECRET:
        missing.append("GOOGLE_CLIENT_SECRET")
    if not GOOGLE_REDIRECT_URI:
        missing.append("GOOGLE_REDIRECT_URI")

    if missing:
        logger.warning(
            "CRITICAL: Google SSO functionality will be disabled. "
            f"Missing environment variables: {', '.join(missing)}"
        )
        return False

    logger.info("Google SSO configuration validated successfully.")
    return True


# Validate on module load
validate_google_config()

# Use HTTPBearer instead of OAuth2PasswordBearer
security = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)
device_id_header = APIKeyHeader(name=DEVICE_ID_HEADER_NAME, auto_error=False)


def hash_password(password: str) -> str:
    """Hash a plaintext password."""
    return cast(str, pwd_context.hash(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a hashed password."""
    return cast(bool, pwd_context.verify(plain_password, hashed_password))


def create_access_token(
    data: dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token with expiration."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire, "type": "access"})
    return cast(str, jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM))


def create_refresh_token(data: dict[str, Any]) -> str:
    """Create a JWT refresh token with long expiration."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return cast(str, jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM))


class TokenData(BaseModel):
    """Data contained in the JWT token."""

    email: Optional[str] = None
    role: Optional[str] = None


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenData:
    """Verify a JWT token and extract the token data."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        role: Optional[str] = payload.get("role")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token: no email")
        return TokenData(email=email, role=role)
    except PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> TokenData:
    """Get the current user from httpOnly cookie or Authorization header."""
    token: Optional[str] = None

    # First, try to get token from httpOnly cookie
    token = request.cookies.get(COOKIE_NAME)

    # Debug logging for cookie issues
    if not token:
        logger.warning(
            f"Auth Debug: No token in cookie '{COOKIE_NAME}'. "
            f"Cookies present: {list(request.cookies.keys())}"
        )
    else:
        logger.info(f"Auth Debug: Token found in cookie '{COOKIE_NAME}'")

    # Fall back to Authorization header if no cookie
    if not token and credentials:
        token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")  # type: ignore
        is_admin: bool = payload.get("is_admin", False)  # type: ignore
        return TokenData(email=email, role="Admin" if is_admin else "User")
    except PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )


def require_role(required_role: str) -> Any:
    """Dependency to require a specific user role."""

    def role_checker(user: TokenData = Depends(get_current_user)) -> UserDict:
        if user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {required_role} role",
            )
        return {"email": user.email, "role": user.role}

    return role_checker


def authenticate_device_credentials(
    db: Session, device_id: str, api_key: str
) -> Device:
    """Authenticate a device using its device ID and plaintext API key.

    Rejects credentials if the device is not in an active lifecycle state
    (``PENDING``, ``SUSPENDED``, ``UNPAIRED``, ``RETIRED`` are rejected).
    """
    if not device_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Device-ID header",
        )

    result = db.execute(select(Device).where(Device.device_id == device_id))
    device = result.scalars().first()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Device ID",
        )

    # Reject inactive lifecycle states
    if device.lifecycle_state not in (LifecycleState.ACTIVE.value,):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Device lifecycle state is '{device.lifecycle_state}'; "
            "only 'active' devices may authenticate",
        )

    if not device.api_key_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Device not configured for API Key authentication",
        )

    if not verify_password(api_key, device.api_key_hash):  # type: ignore[arg-type]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )

    return device


async def get_current_device(
    api_key: str = Depends(api_key_header),
    device_id: str = Depends(device_id_header),
    db: Session = Depends(get_db),
) -> Device:
    """Authenticate device using API Key and Device ID."""
    if not api_key or not device_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key or X-Device-ID header",
        )

    # Fetch device by ID
    result = db.execute(select(Device).where(Device.device_id == device_id))
    device = result.scalars().first()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Device ID",
        )

    # Reject inactive lifecycle states
    if device.lifecycle_state not in (LifecycleState.ACTIVE.value,):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Device lifecycle state is '{device.lifecycle_state}'; "
            "only 'active' devices may authenticate",
        )

    if not device.api_key_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Device not configured for API Key authentication",
        )

    # Verify API Key
    if not verify_password(api_key, device.api_key_hash):  # type: ignore
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )

    return device


def exchange_google_code(code: str) -> dict:
    """Exchange authorization code for tokens."""
    if not validate_google_config():
        raise HTTPException(status_code=503, detail="Google SSO not configured")

    token_data = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": GOOGLE_REDIRECT_URI,
    }

    try:
        token_response = requests.post(GOOGLE_TOKEN_URL, data=token_data, timeout=10)
        if token_response.status_code != 200:
            logger.error(f"Google Token Exchange Failed: {token_response.text}")
            raise HTTPException(status_code=400, detail="Token exchange failed")
        return cast(dict, token_response.json())
    except requests.RequestException as e:
        logger.error(f"Request to Google failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service unavailable (Google)")


def verify_google_token(id_token_str: str) -> dict:
    """Verify Google ID token and return user info."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google Client ID not configured")

    try:
        idinfo = id_token.verify_oauth2_token(
            id_token_str, google_requests.Request(), GOOGLE_CLIENT_ID
        )
        return cast(dict, idinfo)
    except Exception as e:
        logger.error(f"Google Verification Failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid Google token")


def get_or_create_google_user(db: Session, idinfo: dict) -> User:
    """Find or create a user based on Google idinfo."""
    user_email = idinfo["email"]
    user = db.query(User).filter(User.email == user_email).first()

    if not user:
        # Assign to default tenant
        default_tenant = db.query(Tenant).filter(Tenant.slug == "default").first()

        # Create new user
        user = User(
            email=user_email,
            username=idinfo.get("name", user_email.split("@")[0]),
            full_name=idinfo.get("name"),
            hashed_password=hash_password(os.urandom(24).hex()),
            is_admin=False,
            role="Client",
            tenant_id=default_tenant.id if default_tenant else None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"New user created via Google SSO: {user_email}")

    return cast(User, user)


# ---- Tenant & Site Authorization Guards ----


def require_tenant_role(required_role: str) -> Any:
    """Dependency to require a specific role within a user's primary tenant."""

    def role_checker(
        user_token: TokenData = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> Dict[str, Any]:
        db_user = cast(
            User, db.query(User).filter(User.email == user_token.email).first()
        )
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not found",
            )

        if db_user.is_admin:
            return {
                "email": cast(str, db_user.email),
                "role": "Admin",
                "user_id": cast(int, db_user.id),
            }

        if not db_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not associated with any tenant",
            )

        membership = cast(
            TenantMembership,
            db.query(TenantMembership)
            .filter(
                TenantMembership.user_id == db_user.id,
                TenantMembership.tenant_id == db_user.tenant_id,
                TenantMembership.role == required_role,
            )
            .first(),
        )
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {required_role} role in tenant",
            )

        return {
            "email": cast(str, db_user.email),
            "role": cast(str, membership.role),
            "user_id": cast(int, db_user.id),
        }

    return role_checker


def require_site_access(site_id: int, minimum_role: str = "viewer") -> Any:
    """Dependency to verify a user has at least the minimum role on a site.

    Admins bypass this check. Role hierarchy: admin > operator > installer > viewer.
    """
    _ROLE_HIERARCHY: dict[str, int] = {
        "admin": 4,
        "operator": 3,
        "installer": 2,
        "viewer": 1,
    }

    def access_checker(
        user_token: TokenData = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> Dict[str, Any]:
        db_user = cast(
            User, db.query(User).filter(User.email == user_token.email).first()
        )
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not found",
            )

        if db_user.is_admin:
            return {
                "email": cast(str, db_user.email),
                "role": "Admin",
                "user_id": cast(int, db_user.id),
            }

        site = cast(Site, db.query(Site).filter(Site.id == site_id).first())
        if not site:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Site not found",
            )

        min_level = _ROLE_HIERARCHY.get(minimum_role, 1)

        if db_user.tenant_id and site.tenant_id == db_user.tenant_id:
            tenant_membership = cast(
                TenantMembership,
                db.query(TenantMembership)
                .filter(
                    TenantMembership.user_id == db_user.id,
                    TenantMembership.tenant_id == db_user.tenant_id,
                )
                .first(),
            )
            if tenant_membership:
                tenant_level = _ROLE_HIERARCHY.get(cast(str, tenant_membership.role), 0)
                if tenant_level >= min_level:
                    return {
                        "email": cast(str, db_user.email),
                        "role": cast(str, tenant_membership.role),
                        "user_id": cast(int, db_user.id),
                    }

        membership = cast(
            SiteMembership,
            db.query(SiteMembership)
            .filter(
                SiteMembership.user_id == db_user.id,
                SiteMembership.site_id == site_id,
            )
            .first(),
        )
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have access to this site",
            )

        user_level = _ROLE_HIERARCHY.get(cast(str, membership.role), 0)
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires at least '{minimum_role}' role on this site",
            )

        return {
            "email": cast(str, db_user.email),
            "role": cast(str, membership.role),
            "user_id": cast(int, db_user.id),
        }

    return access_checker


def get_current_user_id(
    user_token: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> int:
    """Get the database user ID from the current authenticated user."""
    db_user = cast(User, db.query(User).filter(User.email == user_token.email).first())
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return cast(int, db_user.id)


# ---- Async-compatible Authorization Helpers ----

_ROLE_HIERARCHY: dict[str, int] = {
    "admin": 4,
    "operator": 3,
    "installer": 2,
    "viewer": 1,
}


def require_user() -> Any:
    """Dependency that returns the authenticated user dict.

    Like get_current_user but returns a UserDict with email, role, and user_id.
    """

    def user_checker(
        user_token: TokenData = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> UserDict:
        db_user = cast(
            User, db.query(User).filter(User.email == user_token.email).first()
        )
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not found",
            )
        return {
            "email": cast(str, db_user.email),
            "role": "Admin" if db_user.is_admin else cast(str, db_user.role),
            "user_id": cast(int, db_user.id),
        }

    return user_checker


def verify_site_access_for_user(
    db_user: User,
    site_str_id: str,
    db: Session,
    minimum_role: str = "viewer",
) -> dict:
    """Verify a user has at least the minimum role on a site (string ID).

    Admins bypass this check.  Raises HTTPException on failure.
    Returns the resolved Site object on success.
    """
    from homepot.models import Site, SiteMembership, TenantMembership

    if db_user.is_admin:
        return {"role": "Admin", "user_id": cast(int, db_user.id)}

    site = db.query(Site).filter(Site.site_id == site_str_id).first()
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found",
        )

    min_level = _ROLE_HIERARCHY.get(minimum_role, 1)

    if db_user.tenant_id and site.tenant_id == db_user.tenant_id:
        tm = cast(
            TenantMembership,
            db.query(TenantMembership)
            .filter(
                TenantMembership.user_id == db_user.id,
                TenantMembership.tenant_id == db_user.tenant_id,
            )
            .first(),
        )
        if tm:
            tm_level = _ROLE_HIERARCHY.get(cast(str, tm.role), 0)
            if tm_level >= min_level:
                return {
                    "role": cast(str, tm.role),
                    "user_id": cast(int, db_user.id),
                }

    sm = cast(
        SiteMembership,
        db.query(SiteMembership)
        .filter(
            SiteMembership.user_id == db_user.id,
            SiteMembership.site_id == site.id,
        )
        .first(),
    )
    if not sm:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have access to this site",
        )

    user_level = _ROLE_HIERARCHY.get(cast(str, sm.role), 0)
    if user_level < min_level:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires at least '{minimum_role}' role on this site",
        )

    return {"role": cast(str, sm.role), "user_id": cast(int, db_user.id)}


def get_accessible_site_ids(
    db_user: User,
    db: Session,
    minimum_role: str = "viewer",
) -> Optional[set[int]]:
    """Get the set of site database IDs (integer IDs) that the user has access to.

    If the user is an admin, returns None (all sites accessible).
    """
    if db_user.is_admin:
        return None

    from homepot.models import Site, SiteMembership, TenantMembership

    min_level = _ROLE_HIERARCHY.get(minimum_role, 1)
    allowed_roles = [role for role, val in _ROLE_HIERARCHY.items() if val >= min_level]

    accessible_site_ids: set[int] = set()

    # 1. Check tenant-level access
    if db_user.tenant_id:
        tm_role = (
            db.query(TenantMembership.role)
            .filter(
                TenantMembership.user_id == db_user.id,
                TenantMembership.tenant_id == db_user.tenant_id,
                TenantMembership.role.in_(allowed_roles),
            )
            .scalar()
        )
        if tm_role:
            tenant_site_ids = (
                db.query(Site.id).filter(Site.tenant_id == db_user.tenant_id).all()
            )
            accessible_site_ids.update(row[0] for row in tenant_site_ids)

    # 2. Check site-level access
    site_memberships = (
        db.query(SiteMembership.site_id)
        .filter(
            SiteMembership.user_id == db_user.id,
            SiteMembership.role.in_(allowed_roles),
        )
        .all()
    )
    accessible_site_ids.update(row[0] for row in site_memberships)

    return accessible_site_ids


def verify_device_belongs_to_user(
    db_user: User,
    device: Device,
    db: Session,
    minimum_role: str = "viewer",
) -> None:
    """Verify that a device's site is accessible by the user."""
    site = cast("Site", db.query(Site).filter(Site.id == device.site_id).first())
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device site not found",
        )
    verify_site_access_for_user(db_user, cast(str, site.site_id), db, minimum_role)
