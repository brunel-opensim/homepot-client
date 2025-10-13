"""API endpoints for managing user in the HomePot system."""


import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from homepot_client.app.auth_utils import (
    create_access_token,
    hash_password,
    require_role,
    verify_password,
)
from homepot_client.app.db.database import SessionLocal
from homepot_client.app.models import UserRegisterModel as models
from homepot_client.app.schemas import schemas

# Setup Logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter()


# Database Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Unified Response Format
def response(success: bool, message: str, data: dict = None):
    return {"success": success, "message": message, "data": data or {}}


@router.post("/signup", response_model=dict, status_code=status.HTTP_201_CREATED)
def signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    try:
        db_user = db.query(models.User).filter(models.User.email == user.email).first()
        if db_user:
            logger.warning(f"Signup failed: Email {user.email} already registered")
            raise HTTPException(status_code=400, detail="Email already registered")

        new_user = models.User(
            email=user.email,
            name=user.name,
            hashed_password=hash_password(user.password),
            role=user.role if user.role else "User",
            created_date=datetime.utcnow(),
            updated_date=datetime.utcnow(),
            last_login=datetime.utcnow(),
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
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    try:
        db_user = db.query(models.User).filter(models.User.email == user.email).first()
        if not db_user or not verify_password(user.password, db_user.hashed_password):
            logger.warning(f"Login failed for {user.email}")
            raise HTTPException(status_code=401, detail="Invalid credentials")

        db_user.last_login = datetime.utcnow()
        db.commit()

        logger.info(f"User logged in: {db_user.email}")

        return response(
            success=True,
            message="Login successful",
            data={
                "access_token": create_access_token(
                    {"sub": db_user.email, "role": db_user.role}
                ),
                "username": db_user.name,
                "role": db_user.role,
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
    admin=Depends(require_role("Admin")),
):
    try:
        db_user = db.query(models.User).filter(models.User.id == user_id).first()
        if not db_user:
            logger.warning(f"Role assignment failed: User {user_id} not found")
            raise HTTPException(status_code=404, detail="User not found")

        db_user.role = new_role
        db.commit()
        db.refresh(db_user)

        logger.info(f"Role updated: {db_user.email} -> {new_role}")

        return response(
            success=True,
            message=f"Role updated to {new_role} for {db_user.email}",
            data={"user_id": db_user.id, "email": db_user.email, "role": db_user.role},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Role assignment error for user_id {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
