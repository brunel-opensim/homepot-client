"""API endpoints for managing user in the HomePot system."""

import logging
from datetime import datetime, timezone
from typing import Dict, Generator, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from homepot.app.auth_utils import (
    create_access_token,
    hash_password,
    require_role,
    verify_password,
)
from homepot.app.db.database import SessionLocal
from homepot.app.models import UserRegisterModel as models
from homepot.app.schemas import schemas

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
            # raise HTTPException(status_code=400, detail="Email already registered")
            return {"status_code": 400, "detail": "Email already registered"}

        new_user = models.User(
            email=user.email,
            username=user.username,
            hashed_password=hash_password(user.password),
            # role=user.role if user.role else "User",
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

    except Exception as e:
        logger.error(f"Signup error for {user.email}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/login", response_model=dict, status_code=status.HTTP_200_OK)
def login(user: schemas.UserLogin, db: Session = Depends(get_db)) -> dict:
    """User Login Endpoint."""
    try:
        db_user = db.query(models.User).filter(models.User.email == user.email).first()
        hashed_pw: str = db_user.hashed_password  # type: ignore
        if not db_user or not verify_password(user.password, hashed_pw):
            logger.warning(f"Login failed for {user.email}")
            raise HTTPException(status_code=401, detail="Invalid credentials")

        db_user.last_login = datetime.now(timezone.utc)  # type: ignore
        db.commit()

        logger.info(f"User logged in: {db_user.email}")

        return response(
            success=True,
            message="Login successful",
            data={
                "access_token": create_access_token(
                    {"sub": db_user.email, "is_admin": db_user.is_admin}
                ),
                "username": db_user.username,
                "is_admin": db_user.is_admin,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error for {user.email}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.put(
    "/users/{user_id}/role", response_model=dict, status_code=status.HTTP_200_OK
)
def assign_role(
    user_id: int,
    new_role: str,
    db: Session = Depends(get_db),
    admin: Dict = Depends(require_role("Admin")),
) -> dict:
    """Assign Role - Admin Only (DISABLED - not in schema)."""
    # TODO: Add role/permission system to schema
    raise HTTPException(
        status_code=501,
        detail=(
            "Role assignment not implemented in current schema. "
            "Use is_admin field instead."
        ),
    )
