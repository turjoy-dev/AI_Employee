"""Pydantic v2 schemas for Appointment domain."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AppointmentBase(BaseModel):
    """Shared appointment properties."""

    customer_id: UUID = Field(..., description="Associated customer UUID")
    conversation_id: Optional[UUID] = Field(
        default=None,
        description="Optional originating conversation UUID",
    )
    title: str = Field(..., min_length=1, max_length=255, description="Appointment title or purpose")
    scheduled_at: datetime = Field(..., description="Scheduled start timestamp (UTC)")
    duration_minutes: int = Field(
        default=30,
        ge=5,
        le=480,
        description="Duration in minutes",
    )
    status: str = Field(
        default="scheduled",
        min_length=1,
        max_length=50,
        description="Appointment status ('scheduled', 'confirmed', 'completed', 'cancelled')",
    )
    notes: Optional[str] = Field(default=None, description="Additional booking notes")


class AppointmentCreate(AppointmentBase):
    """Schema for booking a new appointment."""

    pass


class AppointmentUpdate(BaseModel):
    """Schema for updating or rescheduling an appointment."""

    conversation_id: Optional[UUID] = Field(default=None)
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    scheduled_at: Optional[datetime] = Field(default=None)
    duration_minutes: Optional[int] = Field(default=None, ge=5, le=480)
    status: Optional[str] = Field(default=None, min_length=1, max_length=50)
    notes: Optional[str] = Field(default=None)


class AppointmentResponse(AppointmentBase):
    """Schema for returning an appointment record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
