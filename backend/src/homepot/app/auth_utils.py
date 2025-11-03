"""Authentication and authorization utilities for the HomePot system."""

import os
from typing import Any, Optional, cast

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from homepot.app.schemas.schemas import UserDict

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY", "supersecret")
ALGORITHM = "HS256"

# Use HTTPBearer instead of OAuth2PasswordBearer
security = HTTPBearer()


def hash_password(password: str) -> str:
    """Hash a plaintext password."""
    return cast(str, pwd_context.hash(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a hashed password."""
    return cast(bool, pwd_context.verify(plain_password, hashed_password))


def create_access_token(data: dict[str, Any]) -> str:
    """Create a JWT access token."""
    return cast(str, jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM))


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
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenData:
    """Get the current user from the JWT token."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")  # type: ignore
        role: str = payload.get("role")  # type: ignore
        return TokenData(email=email, role=role)
        # return {"email": payload.get("sub"), "role": payload.get("role")}
    except JWTError:
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
