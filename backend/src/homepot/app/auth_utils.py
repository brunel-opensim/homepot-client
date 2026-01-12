"""Authentication and authorization utilities for the HomePot system."""

from datetime import datetime, timedelta, timezone
import logging
import os
from typing import Any, Optional, cast

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt.exceptions import PyJWTError
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from homepot.app.schemas.schemas import UserDict
from homepot.database import get_db
from homepot.models import Device

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY", "supersecret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
COOKIE_NAME = "access_token"
API_KEY_HEADER_NAME = "X-API-Key"
DEVICE_ID_HEADER_NAME = "X-Device-ID"

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
    to_encode.update({"exp": expire})
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
            f"Auth Debug: No token in cookie '{COOKIE_NAME}'. Cookies present: {list(request.cookies.keys())}"
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

    if not device.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device is inactive",
        )

    return device
