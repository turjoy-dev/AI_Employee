"""Thin REST API routes for Conversation management."""

from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
)
from backend.services import conversation_service, customer_service

router = APIRouter(prefix="/conversations", tags=["Conversations"])

DBSession = Annotated[Session, Depends(get_db)]


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation",
)
def create_conversation(conversation_in: ConversationCreate, db: DBSession):
    """Start or record a new conversation for an existing customer."""
    if not customer_service.get_customer(db, conversation_in.customer_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )
    return conversation_service.create_conversation(db, conversation_in)


@router.get(
    "",
    response_model=List[ConversationResponse],
    summary="List conversations",
)
def list_conversations(
    db: DBSession,
    customer_id: Optional[UUID] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    """Retrieve a list of conversations, optionally filtered by customer."""
    return conversation_service.list_conversations(
        db,
        customer_id=customer_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get conversation by ID",
)
def get_conversation(conversation_id: UUID, db: DBSession):
    """Retrieve a single conversation by UUID."""
    conversation = conversation_service.get_conversation(db, conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return conversation


@router.patch(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Update a conversation",
)
def update_conversation(
    conversation_id: UUID,
    conversation_in: ConversationUpdate,
    db: DBSession,
):
    """Partially update an existing conversation."""
    conversation = conversation_service.update_conversation(
        db,
        conversation_id,
        conversation_in,
    )
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return conversation


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation",
)
def delete_conversation(conversation_id: UUID, db: DBSession) -> Response:
    """Delete a conversation and cascade delete its messages."""
    deleted = conversation_service.delete_conversation(db, conversation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
