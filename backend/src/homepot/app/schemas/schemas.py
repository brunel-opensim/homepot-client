"""Pydantic schemas for user registration and authentication in the HomePot system."""

from typing import Optional, TypedDict

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    """Schema for creating a new user."""

    email: EmailStr
    password: str
    username: Optional[str] = None
    # role: Optional[str] = "User"  # Default role


class UserLogin(BaseModel):
    """Schema for user login."""

    email: EmailStr
    password: str


class UserOut(BaseModel):
    """Schema for user output (response)."""

    id: int
    email: EmailStr
    name: Optional[str] = None
    role: str

    class Config:
        """Enable ORM mode for compatibility with SQLAlchemy models."""

        orm_mode = True


class Token(BaseModel):
    """Schema for JWT token response."""

    access_token: str
    token_type: str


class UserDict(TypedDict):
    """TypedDict for user information extracted from JWT token."""

    email: Optional[str]
    role: Optional[str]
