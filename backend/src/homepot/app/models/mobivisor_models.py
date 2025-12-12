"""Pydantic models for interacting with the external Mobivisor API.

These are plain Pydantic classes (no SQLAlchemy) and are intentionally
separated from the application's DB models to avoid mapper / table
conflicts and to make it explicit that these are DTOs for the
third-party Mobivisor service.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr


class MobivisorUserModel(BaseModel):
    """Pydantic model describing a Mobivisor user payload.

    Fields mirror the expected Mobivisor `/users` `user` object and are used
    to perform automatic request validation and parsing. This model is
    intentionally not a SQLAlchemy model and does not interact with the
    application's database.
    """

    email: EmailStr
    displayName: str
    username: str
    phone: str
    password: str
    notes: Optional[str] = None
    role: Optional[Dict[str, Any]] = None
    _id: Optional[str] = None


class CreateUserPayload(BaseModel):
    """Top-level payload model for creating a Mobivisor user.

    Contains the required `user` object and optional `groupInfoOfTheUser`.
    """

    user: MobivisorUserModel
    groupInfoOfTheUser: Optional[List[Dict[str, Any]]] = None


class MobivisorUserUpdateModel(BaseModel):
    """Pydantic model for partial updates to a Mobivisor user.

    All fields are optional to allow partial updates (clients may update one
    or more fields without resending the entire user object).
    """

    email: Optional[EmailStr] = None
    displayName: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = None
    notes: Optional[str] = None
    role: Optional[Dict[str, Any]] = None
    _id: Optional[str] = None


class UpdateUserPayload(BaseModel):
    """Top-level payload model for updating a Mobivisor user.

    Contains the optional `user` object (partial fields allowed) and an
    optional `groupInfoOfTheUser` list.
    """

    user: MobivisorUserUpdateModel
    groupInfoOfTheUser: Optional[List[Dict[str, Any]]] = None


class CreateGroupPayload(BaseModel):
    """Payload for creating a Mobivisor group.

    Fields:
    - name: required name of the group
    - description: optional description
    - metadata: optional arbitrary key/value metadata
    """

    name: str
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class UpdateGroupPayload(BaseModel):
    """Payload for updating a Mobivisor group.

    All fields are optional to allow partial updates. Use
    `model_dump(exclude_none=True)` before forwarding to the upstream API.
    """

    name: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
