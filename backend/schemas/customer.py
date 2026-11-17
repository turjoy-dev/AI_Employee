"""Pydantic v2 schemas for Customer domain."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CustomerBase(BaseModel):
    """Shared customer properties."""

    full_name: str = Field(..., min_length=1, max_length=255, description="Customer full name")
    phone_number: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Contact phone number",
    )
    email: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Contact email address",
    )
    preferred_language: str = Field(
        default="en",
        min_length=2,
        max_length=20,
        description="Preferred language code (e.g., 'en', 'bn')",
    )
    notes: Optional[str] = Field(default=None, description="Additional customer notes")


class CustomerCreate(CustomerBase):
    """Schema for creating a new customer."""

    pass


class CustomerUpdate(BaseModel):
    """Schema for partially updating an existing customer."""

    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    phone_number: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)
    preferred_language: Optional[str] = Field(default=None, min_length=2, max_length=20)
    notes: Optional[str] = Field(default=None)


class CustomerResponse(CustomerBase):
    """Schema for returning a customer record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
