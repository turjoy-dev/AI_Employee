"""Thin REST API routes for Message management."""

from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.schemas.message import MessageCreate, MessageResponse, MessageUpdate
from backend.services import conversation_service, message_service

router = APIRouter(prefix="/messages", tags=["Messages"])

DBSession = Annotated[Session, Depends(get_db)]


@router.post(
    "",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new message",
)
def create_message(message_in: MessageCreate, db: DBSession):
    """Append a new message to an existing conversation."""
    if not conversation_service.get_conversation(db, message_in.conversation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return message_service.create_message(db, message_in)


@router.get(
    "",
    response_model=List[MessageResponse],
    summary="List messages",
)
def list_messages(
    db: DBSession,
    conversation_id: Optional[UUID] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    """List messages chronologically, optionally filtered by conversation."""
    return message_service.list_messages(
        db,
        conversation_id=conversation_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{message_id}",
    response_model=MessageResponse,
    summary="Get message by ID",
)
def get_message(message_id: UUID, db: DBSession):
    """Retrieve a single message by UUID."""
    message = message_service.get_message(db, message_id)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found.",
        )
    return message


@router.patch(
    "/{message_id}",
    response_model=MessageResponse,
    summary="Update a message",
)
def update_message(message_id: UUID, message_in: MessageUpdate, db: DBSession):
    """Partially update an existing message."""
    message = message_service.update_message(db, message_id, message_in)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found.",
        )
    return message


@router.delete(
    "/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a message",
)
def delete_message(message_id: UUID, db: DBSession) -> Response:
    """Delete a message record."""
    deleted = message_service.delete_message(db, message_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
