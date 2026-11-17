"""Pydantic v2 schemas for Lead domain."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LeadBase(BaseModel):
    """Shared lead properties."""

    customer_id: UUID = Field(..., description="Associated customer UUID")
    conversation_id: Optional[UUID] = Field(
        default=None,
        description="Optional originating conversation UUID",
    )
    source: str = Field(
        default="receptionist",
        min_length=1,
        max_length=100,
        description="Lead source (e.g., 'receptionist', 'website', 'phone')",
    )
    status: str = Field(
        default="new",
        min_length=1,
        max_length=50,
        description="Lead status (e.g., 'new', 'contacted', 'qualified', 'converted', 'lost')",
    )
    priority: str = Field(
        default="medium",
        min_length=1,
        max_length=50,
        description="Lead priority ('low', 'medium', 'high', 'urgent')",
    )
    score: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Lead qualification score (0-100)",
    )
    notes: Optional[str] = Field(default=None, description="Notes and analyst recommendations")


class LeadCreate(LeadBase):
    """Schema for creating a new business lead."""

    pass


class LeadUpdate(BaseModel):
    """Schema for updating an existing business lead."""

    conversation_id: Optional[UUID] = Field(default=None)
    source: Optional[str] = Field(default=None, min_length=1, max_length=100)
    status: Optional[str] = Field(default=None, min_length=1, max_length=50)
    priority: Optional[str] = Field(default=None, min_length=1, max_length=50)
    score: Optional[int] = Field(default=None, ge=0, le=100)
    notes: Optional[str] = Field(default=None)


class LeadResponse(LeadBase):
    """Schema for returning a business lead record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class LeadFollowUpDraftResponse(BaseModel):
    """Schema for returning an AI-drafted lead follow-up message."""

    draft: str = Field(..., description="Generated follow-up message draft")


class LeadFollowUpSendRequest(BaseModel):
    """Schema for sending/persisting a follow-up message to a lead."""

    message: str = Field(..., min_length=1, max_length=5000, description="Follow-up message content")

    @field_validator("message")
    @classmethod
    def validate_non_empty_message(cls, value: str) -> str:
        """Ensure follow-up message is not whitespace-only."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Follow-up message cannot be blank.")
        return cleaned


class LeadFollowUpSendResponse(BaseModel):
    """Schema confirming a follow-up message was persisted."""

    status: str = Field(default="success", description="Operation status")
