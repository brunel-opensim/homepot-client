"""Authentication and authorization utilities for the HomePot system."""

from datetime import datetime, timedelta, timezone
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional, cast

import jwt
import requests
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from jwt.exceptions import PyJWTError
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from homepot.app.schemas.schemas import UserDict
from homepot.database import get_db
from homepot.models import Device, User

# Ensure environment variables are loaded
load_dotenv()

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY", "supersecret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
COOKIE_NAME = "access_token"
API_KEY_HEADER_NAME = "X-API-Key"
DEVICE_ID_HEADER_NAME = "X-Device-ID"

# Google SSO Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Cookie and Frontend Settings
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")  # "lax", "strict", or "none"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

def validate_google_config():
    """Validate that Google SSO configuration is present and log status."""
    missing = []
    if not GOOGLE_CLIENT_ID: missing.append("GOOGLE_CLIENT_ID")
    if not GOOGLE_CLIENT_SECRET: missing.append("GOOGLE_CLIENT_SECRET")
    if not GOOGLE_REDIRECT_URI: missing.append("GOOGLE_REDIRECT_URI")
    
    if missing:
        logger.warning(
            f"CRITICAL: Google SSO functionality will be disabled. "
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


def exchange_google_code(code: str) -> dict:
    """Exchange authorization code for tokens."""
    if not validate_google_config():
        raise HTTPException(status_code=500, detail="Google SSO not configured")

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
        raise HTTPException(status_code=500, detail="Google Client ID not configured")
        
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
        # Create new user
        user = User(
            email=user_email,
            username=idinfo.get("name", user_email.split("@")[0]),
            full_name=idinfo.get("name"),
            hashed_password=hash_password(os.urandom(24).hex()),
            is_admin=False,
            role="Client",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"New user created via Google SSO: {user_email}")
    
    return cast(User, user)
