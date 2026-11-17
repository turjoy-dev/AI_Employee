"""Pydantic v2 schemas for Message domain."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MessageBase(BaseModel):
    """Shared message properties."""

    conversation_id: UUID = Field(..., description="Associated conversation UUID")
    role: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Sender role (e.g., 'user', 'assistant', 'system')",
    )
    content: str = Field(..., min_length=1, description="Message text content")
    metadata_json: Optional[dict[str, Any] | str] = Field(
        default=None,
        description="Optional structured metadata for the message turn",
    )
    timestamp: Optional[datetime] = Field(default=None, description="Message timestamp")


class MessageCreate(MessageBase):
    """Schema for creating a new message in a conversation."""

    pass


class MessageUpdate(BaseModel):
    """Schema for updating an existing message."""

    role: Optional[str] = Field(default=None, min_length=1, max_length=50)
    content: Optional[str] = Field(default=None, min_length=1)
    metadata_json: Optional[dict[str, Any] | str] = Field(default=None)


class MessageResponse(BaseModel):
    """Schema for returning a message record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    role: str
    content: str
    metadata_json: Optional[dict[str, Any] | str] = None
    timestamp: datetime
    created_at: datetime
    updated_at: datetime
