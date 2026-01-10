"""API endpoints for managing user in the HomePot system."""

import logging
import os
from datetime import datetime, timezone
from typing import Dict, Generator, Literal, Optional, cast
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Response, status
from google.auth.transport import requests as google_requests

# SSO Imports
from google.oauth2 import id_token
from sqlalchemy.orm import Session

from homepot.app.auth_utils import (
    ACCESS_TOKEN_EXPIRE_HOURS,
    COOKIE_NAME,
    TokenData,
    create_access_token,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)
from homepot.app.models import UserRegisterModel as models
from homepot.app.schemas import schemas
from homepot.database import SessionLocal

# Load the .env file
load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")


# Cookie settings
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")  # "lax" or "strict" or "none"


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


def get_db() -> Generator[Session, None, None]:
    """Database Dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def response(success: bool, message: str, data: Optional[dict] = None) -> dict:
    """Unified Response Formatter."""
    return {"success": success, "message": message, "data": data or {}}


@router.post("/signup", response_model=dict, status_code=status.HTTP_201_CREATED)
def signup(user: schemas.UserCreate, db: Session = Depends(get_db)) -> dict:
    """User Registration and Authentication Endpoints."""
    try:
        db_user = db.query(models.User).filter(models.User.email == user.email).first()
        if db_user:
            logger.warning(f"Signup failed: Email {user.email} already registered")
            raise HTTPException(status_code=400, detail="Email already registered")
            # return {"status_code": 400, "detail": "Email already registered"}

        # Handle username (generate from email if missing)
        final_username = user.username
        if not final_username:
            final_username = user.email.split("@")[0]

        db_username = (
            db.query(models.User).filter(models.User.username == final_username).first()
        )
        if db_username:
            logger.warning(f"Signup failed: Username {final_username} already taken")
            raise HTTPException(status_code=400, detail="Username already taken")
            # return {"status_code": 400, "detail": "Username already taken"}
        # Determine if admin based on role
        user_role = user.role if user.role else "Client"
        is_admin_user = user_role.lower() == "admin"

        new_user = models.User(
            email=user.email,
            username=final_username,
            full_name=user.full_name,
            hashed_password=hash_password(user.password),
            role=user_role,
            is_admin=is_admin_user,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            # last_login=datetime.now(timezone.utc),
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        logger.info(f"New user created: {new_user.email}")

        return response(
            success=True,
            message="User registered successfully",
            data={"access_token": create_access_token({"sub": new_user.email})},
        )
    except HTTPException as e:
        # re-raise without modifying it
        raise e

    except Exception as e:
        logger.error(f"Signup error for {user.email}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/login", response_model=dict, status_code=status.HTTP_200_OK)
def login(
    user: schemas.UserLogin,
    api_response: Response,
    db: Session = Depends(get_db),
) -> dict:
    """User Login Endpoint."""
    try:
        db_user = db.query(models.User).filter(models.User.email == user.email).first()
        if not db_user:
            logger.warning(f"Login failed: User {user.email} not found")
            raise HTTPException(status_code=401, detail="Invalid email")
        hashed_pw: str = db_user.hashed_password  # type: ignore
        if not verify_password(user.password, hashed_pw):
            logger.warning(f"Login failed for {user.email}")
            raise HTTPException(status_code=401, detail="Invalid credentials")

        db_user.last_login = datetime.now(timezone.utc)  # type: ignore
        db.commit()

        logger.info(f"User logged in: {db_user.email}")

        # Create JWT token
        access_token = create_access_token(
            {"sub": db_user.email, "is_admin": db_user.is_admin}
        )

        logger.info(
            f"Setting cookie: secure={COOKIE_SECURE}, samesite={COOKIE_SAMESITE}"
        )

        # Set httpOnly cookie (not accessible via JavaScript - XSS protection)
        api_response.set_cookie(
            key=COOKIE_NAME,
            value=access_token,
            httponly=True,  # Prevents JavaScript access (XSS protection)
            secure=COOKIE_SECURE,  # Only send over HTTPS in production
            # CSRF protection
            samesite=cast(Literal["lax", "strict", "none"], COOKIE_SAMESITE),
            max_age=ACCESS_TOKEN_EXPIRE_HOURS * 60 * 60,  # Cookie expiry in seconds
            path="/",  # Cookie available for all paths
        )

        return response(
            success=True,
            message="Login successful",
            data={
                "access_token": access_token,
                "username": db_user.username,
                "is_admin": db_user.is_admin,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error for {user.email}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.put("/users/{email}/role", response_model=dict, status_code=status.HTTP_200_OK)
def assign_role(
    email: str,
    new_role: str,
    db: Session = Depends(get_db),
    admin: Dict = Depends(require_role("Admin")),
) -> dict:
    """Assign Role - Admin Only."""
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if new_role.lower() == "admin":
            user.is_admin = True  # type: ignore
        elif new_role.lower() == "user":
            user.is_admin = False  # type: ignore
        else:
            raise HTTPException(
                status_code=400, detail="Invalid role. Allowed roles: Admin, User"
            )

        user.updated_at = datetime.now(timezone.utc)  # type: ignore
        db.commit()

        logger.info(f"Role updated for user {email}: {new_role}")

        return response(
            success=True,
            message=f"User role updated to {new_role}",
            data={"email": email, "is_admin": user.is_admin},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Role assignment error for {email}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.delete("/users/{email}", response_model=dict)
def delete_user(
    email: str,
    db: Session = Depends(get_db),
    admin: Dict = Depends(require_role("Admin")),
) -> dict:
    """Delete a user by email."""
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        # Case 1: User does NOT exist
        if not user:
            logger.warning(f"Delete failed - user not found: {email}")
            raise HTTPException(status_code=401, detail="Invalid email")
        # Delete the user
        db.delete(user)
        db.commit()

        logger.info(f"User deleted successfully: {email}")

        return response(
            success=True, message="User deleted successfully.", data={"email": email}
        )
    except HTTPException:
        # Re-raise original intended errors (401, 404, etc.)
        raise

    except Exception as e:
        logger.error(f"Internal server error while deleting user {email}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/logout", response_model=dict, status_code=status.HTTP_200_OK)
def logout(logout_response: Response) -> dict:
    """Logout user by clearing the httpOnly cookie."""
    logout_response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        secure=COOKIE_SECURE,
        samesite=cast(Literal["lax", "strict", "none"], COOKIE_SAMESITE),
    )
    return response(
        success=True,
        message="Logged out successfully",
    )


@router.get("/me", response_model=dict, status_code=status.HTTP_200_OK)
def get_me(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Get current user info from httpOnly cookie."""
    try:
        db_user = (
            db.query(models.User)
            .filter(models.User.email == current_user.email)
            .first()
        )
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        return response(
            success=True,
            message="User info retrieved",
            data={
                "username": db_user.username,
                "email": db_user.email,
                "is_admin": db_user.is_admin,
                "full_name": db_user.full_name,
                "role": db_user.role,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/" + "token"  # nosec


@router.get("/login")
def google_login() -> dict:
    """Return the URL for Google sign-in."""
    params = {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI"),
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    return {"auth_url": f"{GOOGLE_AUTH_URL}?{urlencode(params)}"}


@router.get("/callback")
def google_callback(code: str, db: Session = Depends(get_db)) -> dict:
    """Backend-only callback: exchanges code and returns JSON user data."""
    # 1. Exchange code for Google tokens
    token_data = {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI"),
    }
    token_response = requests.post(GOOGLE_TOKEN_URL, data=token_data, timeout=10)
    if token_response.status_code != 200:
        logger.error(f"Google Token Exchange Failed: {token_response.text}")
        raise HTTPException(status_code=400, detail="Token exchange failed")
    tokens = token_response.json()
    id_token_str = tokens.get("id_token")
    # 2. Verify Google User
    try:
        idinfo = id_token.verify_oauth2_token(
            id_token_str, google_requests.Request(), os.getenv("GOOGLE_CLIENT_ID")
        )
    except Exception as e:
        logger.error(f"Google Verification Failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid Google token")
    # 3. Find/Create User in DB
    user_email = idinfo["email"]
    db_user = db.query(models.User).filter(models.User.email == user_email).first()

    if not db_user:
        db_user = models.User(
            email=user_email,
            username=idinfo.get("name", user_email.split("@")[0]),
            full_name=idinfo.get("name"),
            hashed_password=hash_password(os.urandom(24).hex()),
            is_admin=False,
            role="Client",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    # 4. Generate App JWT
    access_token = create_access_token(
        {"sub": db_user.email, "is_admin": db_user.is_admin}
    )
    # 5. Return JSON (Pure Backend Response)
    return response(
        success=True,
        message="SSO Login successful",
        data={
            "access_token": access_token,
            "user": {
                "email": db_user.email,
                "username": db_user.username,
                "role": db_user.role,
                "is_admin": db_user.is_admin,
            },
        },
    )
