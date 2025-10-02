from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict, List, Optional
import logging
from pydantic import BaseModel, EmailStr
from homepot_client.client import HomepotClient
from homepot_client.database import get_database_service
from homepot_client.audit import AuditEventType, get_audit_logger

client_instance: Optional[HomepotClient] = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


class CreateUserRequest(BaseModel):
    """Request model for creating a new user."""

    user_id: str
    name: str
    email: EmailStr
    password_hash: str
    token: Optional[str] = None
    role: Optional[str] = "user"

    class Config:
        schema_extra = {
            "example": {
                "user_id": "user-123",
                "name": "John Doe",
                "email": "john.doe@example.com",
                "password_hash": "hashed_password_here",
                "token": "fcm_token_or_webpush_token",
                "role": "admin",
            }
        }


def get_client() -> HomepotClient:
    """Dependency to get the client instance."""
    if client_instance is None:
        raise HTTPException(status_code=503, detail="Client not available")
    return client_instance


@router.post("/users", tags=["Users"], response_model=Dict[str, str])
async def create_user(user_request: CreateUserRequest) -> Dict[str, str]:
    """Create a new user."""
    try:
        db_service = await get_database_service()
        print(user_request, "user_request")
        # Check if user already exists (by email or user_id)
        existing_user = await db_service.get_user_by_user_id(user_request.user_id)
        if existing_user:
            raise HTTPException(
                status_code=409, detail=f"User {user_request.user_id} already exists"
            )

        existing_email = await db_service.get_user_by_email(user_request.email)
        if existing_email:
            raise HTTPException(
                status_code=409, detail=f"Email {user_request.email} already registered"
            )

        # Create new user
        user = await db_service.create_user(
            user_id=user_request.user_id,
            name=user_request.name,
            email=user_request.email,
            password_hash=user_request.password_hash,
            token=user_request.token,
            role=user_request.role,
        )

        # Log audit event
        audit_logger = get_audit_logger()
        await audit_logger.log_event(
            AuditEventType.USER_CREATED,
            f"User '{user.name}' created with ID {user.user_id}",
            user_id=int(user.id),
            new_values={
                "user_id": str(user.user_id),
                "name": str(user.name),
                "email": str(user.email),
                "role": str(user.role),
                "token": user.token,
            },
        )

        logger.info(f"Created user {user.user_id}")
        return {
            "message": f"User {user.user_id} created successfully",
            "user_id": str(user.user_id),
            "name": str(user.name),
            "email": str(user.email),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create user: {e}")


@router.get("/users", tags=["Users"])
async def list_users() -> Dict[str, List[Dict]]:
    """List all users."""
    try:
        db_service = await get_database_service()

        from sqlalchemy import select
        from homepot_client.models import User

        async with db_service.get_session() as session:
            result = await session.execute(
                select(User).order_by(User.created_at.desc())
            )
            users = result.scalars().all()

            user_list = []
            for user in users:
                user_list.append(
                    {
                        "user_id": user.user_id,
                        "name": user.name,
                        "email": user.email,
                        "role": user.role,
                        "token": user.token,
                        "created_at": (
                            user.created_at.isoformat() if user.created_at else None
                        ),
                    }
                )

            return {"users": user_list}

    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list users: {e}")


@router.get("/users/{user_id}", tags=["Users"])
async def get_user(user_id: str) -> Dict[str, Any]:
    """Get a specific user by user_id."""
    try:
        db_service = await get_database_service()

        # Look up user by user_id
        user = await db_service.get_user_by_user_id(user_id)

        if not user:
            raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

        return {
            "user_id": user.user_id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "token": user.token,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get user: {e}")
