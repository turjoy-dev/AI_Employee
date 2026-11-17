"""Business logic and CRUD service layer for Appointments."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models import Appointment
from backend.schemas.appointment import AppointmentCreate, AppointmentUpdate


def _to_uuid(val: UUID | str) -> UUID:
    return val if isinstance(val, UUID) else UUID(str(val))


def create_appointment(db: Session, appointment_in: AppointmentCreate) -> Appointment:
    """Create and persist a new Appointment booking."""
    appointment = Appointment(**appointment_in.model_dump())
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


def get_appointment(db: Session, appointment_id: UUID | str) -> Optional[Appointment]:
    """Retrieve a single Appointment by UUID."""
    return db.get(Appointment, _to_uuid(appointment_id))


def list_appointments(
    db: Session,
    customer_id: Optional[UUID | str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[Appointment]:
    """List appointments ordered by scheduled time."""
    stmt = select(Appointment)
    if customer_id is not None:
        stmt = stmt.where(Appointment.customer_id == _to_uuid(customer_id))
    if status is not None:
        stmt = stmt.where(Appointment.status == status)
    stmt = stmt.order_by(Appointment.scheduled_at.asc()).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def update_appointment(
    db: Session,
    appointment_id: UUID | str,
    appointment_in: AppointmentUpdate,
) -> Optional[Appointment]:
    """Partially update or reschedule an existing Appointment."""
    appointment = get_appointment(db, appointment_id)
    if not appointment:
        return None

    update_data = appointment_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(appointment, field, value)

    db.commit()
    db.refresh(appointment)
    return appointment


def delete_appointment(db: Session, appointment_id: UUID | str) -> bool:
    """Delete an Appointment record."""
    appointment = get_appointment(db, appointment_id)
    if not appointment:
        return False

    db.delete(appointment)
    db.commit()
    return True
