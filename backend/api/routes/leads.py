"""Thin REST API routes for Lead management."""

from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from backend.agents.analyst import AIBusinessAnalyst
from backend.api.deps import get_current_user
from backend.database.connection import get_db
from backend.database.models import User
from backend.schemas.lead import (
    LeadCreate,
    LeadFollowUpDraftResponse,
    LeadFollowUpSendRequest,
    LeadFollowUpSendResponse,
    LeadResponse,
    LeadUpdate,
)
from backend.schemas.message import MessageCreate
from backend.services import (
    conversation_service,
    customer_service,
    lead_service,
    message_service,
)

router = APIRouter(prefix="/leads", tags=["Leads"])

DBSession = Annotated[Session, Depends(get_db)]
CurrentAdmin = Annotated[User, Depends(get_current_user)]


@router.post(
    "",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new lead",
)
def create_lead(lead_in: LeadCreate, db: DBSession):
    """Create a new business lead for an existing customer."""
    if not customer_service.get_customer(db, lead_in.customer_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )
    if lead_in.conversation_id and not conversation_service.get_conversation(
        db, lead_in.conversation_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return lead_service.create_lead(db, lead_in)


@router.get(
    "",
    response_model=List[LeadResponse],
    summary="List leads (Admin Auth Required)",
)
def list_leads(
    db: DBSession,
    _current_user: CurrentAdmin,
    customer_id: Optional[UUID] = None,
    status_filter: Annotated[Optional[str], Query(alias="status")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    """List leads with optional customer and status filters."""
    return lead_service.list_leads(
        db,
        customer_id=customer_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{lead_id}",
    response_model=LeadResponse,
    summary="Get lead by ID",
)
def get_lead(lead_id: UUID, db: DBSession):
    """Retrieve a single lead by UUID."""
    lead = lead_service.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found.",
        )
    return lead


@router.patch(
    "/{lead_id}",
    response_model=LeadResponse,
    summary="Update a lead",
)
def update_lead(lead_id: UUID, lead_in: LeadUpdate, db: DBSession):
    """Partially update an existing lead."""
    if lead_in.conversation_id and not conversation_service.get_conversation(
        db, lead_in.conversation_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    lead = lead_service.update_lead(db, lead_id, lead_in)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found.",
        )
    return lead


@router.delete(
    "/{lead_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a lead",
)
def delete_lead(lead_id: UUID, db: DBSession) -> Response:
    """Delete a lead record."""
    deleted = lead_service.delete_lead(db, lead_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{lead_id}/draft-follow-up",
    response_model=LeadFollowUpDraftResponse,
    summary="Generate an AI follow-up draft for a lead (Admin Auth Required)",
)
def draft_lead_follow_up(
    lead_id: UUID,
    db: DBSession,
    _current_user: CurrentAdmin,
) -> LeadFollowUpDraftResponse:
    """Draft a context-aware follow-up message based on the lead's conversation history and score."""
    lead = lead_service.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found.",
        )

    customer = customer_service.get_customer(db, lead.customer_id)
    messages = (
        message_service.list_messages(db, conversation_id=lead.conversation_id, limit=100)
        if lead.conversation_id
        else []
    )

    analyst = AIBusinessAnalyst()
    draft = analyst.draft_follow_up(lead=lead, customer=customer, messages=messages)
    return LeadFollowUpDraftResponse(draft=draft)


@router.post(
    "/{lead_id}/send-follow-up",
    response_model=LeadFollowUpSendResponse,
    summary="Save and send a follow-up message for a lead (Admin Auth Required)",
)
def send_lead_follow_up(
    lead_id: UUID,
    payload: LeadFollowUpSendRequest,
    db: DBSession,
    current_user: CurrentAdmin,
) -> LeadFollowUpSendResponse:
    """Persist a follow-up message to the lead's conversation transcript or lead notes."""
    lead = lead_service.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found.",
        )

    if lead.conversation_id and conversation_service.get_conversation(db, lead.conversation_id):
        message_service.create_message(
            db,
            MessageCreate(
                conversation_id=lead.conversation_id,
                role="admin",
                content=payload.message,
                metadata_json={
                    "type": "lead_follow_up",
                    "lead_id": str(lead.id),
                    "sent_by": current_user.email,
                },
            ),
        )
    else:
        existing_notes = (lead.notes or "").strip()
        follow_up_note = f"[Follow-Up Sent]: {payload.message}"
        updated_notes = f"{existing_notes}\n\n{follow_up_note}" if existing_notes else follow_up_note
        lead_service.update_lead(db, lead.id, LeadUpdate(notes=updated_notes))

    return LeadFollowUpSendResponse(status="success")
