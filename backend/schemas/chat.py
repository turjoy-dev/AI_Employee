"""Pydantic v2 schemas for AI Receptionist chat endpoint."""

from uuid import UUID
from pydantic import BaseModel, Field


class ReceptionistChatRequest(BaseModel):
    """Request payload for POST /api/v1/chat/receptionist."""

    customer_id: UUID = Field(..., description="UUID of the customer sending the message")
    conversation_id: UUID = Field(..., description="UUID of the active conversation")
    content: str = Field(..., min_length=1, description="User message text (English or Bangla)")


class ReceptionistChatResponse(BaseModel):
    """Response payload returned by POST /api/v1/chat/receptionist."""

    customer_id: UUID = Field(..., description="UUID of the customer")
    conversation_id: UUID = Field(..., description="UUID of the conversation")
    reply: str = Field(..., description="Generated AI Receptionist response text")
    content: str = Field(..., description="Generated AI Receptionist response text (alias)")
    user_message_id: UUID = Field(..., description="Persisted User Message UUID")
    assistant_message_id: UUID = Field(..., description="Persisted Assistant Message UUID")
