"""Thin REST API routes for Appointment management."""

from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.schemas.appointment import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentUpdate,
)
from backend.services import appointment_service, conversation_service, customer_service

router = APIRouter(prefix="/appointments", tags=["Appointments"])

DBSession = Annotated[Session, Depends(get_db)]


@router.post(
    "",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new appointment",
)
def create_appointment(appointment_in: AppointmentCreate, db: DBSession):
    """Book a new appointment for an existing customer."""
    if not customer_service.get_customer(db, appointment_in.customer_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )
    if appointment_in.conversation_id and not conversation_service.get_conversation(
        db, appointment_in.conversation_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return appointment_service.create_appointment(db, appointment_in)


@router.get(
    "",
    response_model=List[AppointmentResponse],
    summary="List appointments",
)
def list_appointments(
    db: DBSession,
    customer_id: Optional[UUID] = None,
    status_filter: Annotated[Optional[str], Query(alias="status")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    """List appointments with optional customer and status filters."""
    return appointment_service.list_appointments(
        db,
        customer_id=customer_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{appointment_id}",
    response_model=AppointmentResponse,
    summary="Get appointment by ID",
)
def get_appointment(appointment_id: UUID, db: DBSession):
    """Retrieve a single appointment by UUID."""
    appointment = appointment_service.get_appointment(db, appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found.",
        )
    return appointment


@router.patch(
    "/{appointment_id}",
    response_model=AppointmentResponse,
    summary="Update an appointment",
)
def update_appointment(
    appointment_id: UUID,
    appointment_in: AppointmentUpdate,
    db: DBSession,
):
    """Partially update or reschedule an existing appointment."""
    if appointment_in.conversation_id and not conversation_service.get_conversation(
        db, appointment_in.conversation_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    appointment = appointment_service.update_appointment(
        db,
        appointment_id,
        appointment_in,
    )
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found.",
        )
    return appointment


@router.delete(
    "/{appointment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an appointment",
)
def delete_appointment(appointment_id: UUID, db: DBSession) -> Response:
    """Delete an appointment record."""
    deleted = appointment_service.delete_appointment(db, appointment_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
