"""Pydantic v2 schemas for Conversation domain."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConversationBase(BaseModel):
    """Shared conversation properties."""

    customer_id: UUID = Field(..., description="Associated customer UUID")
    channel: str = Field(
        default="web",
        min_length=1,
        max_length=50,
        description="Communication channel (e.g., 'web', 'voice', 'phone')",
    )
    status: str = Field(
        default="active",
        min_length=1,
        max_length=50,
        description="Conversation lifecycle status (e.g., 'active', 'completed', 'escalated')",
    )
    summary: Optional[str] = Field(default=None, description="Summary of the conversation")
    started_at: Optional[datetime] = Field(default=None, description="Conversation start timestamp")
    ended_at: Optional[datetime] = Field(default=None, description="Conversation end timestamp")


class ConversationCreate(ConversationBase):
    """Schema for starting or recording a new conversation."""

    pass


class ConversationUpdate(BaseModel):
    """Schema for updating an existing conversation."""

    channel: Optional[str] = Field(default=None, min_length=1, max_length=50)
    status: Optional[str] = Field(default=None, min_length=1, max_length=50)
    summary: Optional[str] = Field(default=None)
    ended_at: Optional[datetime] = Field(default=None)


class ConversationResponse(BaseModel):
    """Schema for returning a conversation record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    channel: str
    status: str
    summary: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
