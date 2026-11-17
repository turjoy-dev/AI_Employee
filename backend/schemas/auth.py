"""Pydantic v2 schemas for Authentication and User registration."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserRegisterRequest(BaseModel):
    """Payload for registering an initial business admin account."""

    email: str = Field(..., min_length=3, max_length=255, description="Admin email address")
    password: str = Field(..., min_length=6, max_length=128, description="Plaintext password to hash")
    role: str = Field(default="admin", min_length=1, max_length=50, description="User role")


class UserResponse(BaseModel):
    """Public representation of a User account (never exposes hashed_password)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """OAuth2 JWT Bearer token response."""

    access_token: str
    token_type: str = "bearer"
