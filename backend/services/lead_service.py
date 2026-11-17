"""Business logic and CRUD service layer for Leads."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models import Lead
from backend.schemas.lead import LeadCreate, LeadUpdate


def _to_uuid(val: UUID | str) -> UUID:
    return val if isinstance(val, UUID) else UUID(str(val))


def create_lead(db: Session, lead_in: LeadCreate) -> Lead:
    """Create and persist a new Lead record."""
    lead = Lead(**lead_in.model_dump())
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def get_lead(db: Session, lead_id: UUID | str) -> Optional[Lead]:
    """Retrieve a single Lead by UUID."""
    return db.get(Lead, _to_uuid(lead_id))


def list_leads(
    db: Session,
    customer_id: Optional[UUID | str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[Lead]:
    """List leads with optional customer and status filters."""
    stmt = select(Lead)
    if customer_id is not None:
        stmt = stmt.where(Lead.customer_id == _to_uuid(customer_id))
    if status is not None:
        stmt = stmt.where(Lead.status == status)
    stmt = stmt.order_by(Lead.created_at.desc()).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def update_lead(
    db: Session,
    lead_id: UUID | str,
    lead_in: LeadUpdate,
) -> Optional[Lead]:
    """Partially update an existing Lead record."""
    lead = get_lead(db, lead_id)
    if not lead:
        return None

    update_data = lead_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lead, field, value)

    db.commit()
    db.refresh(lead)
    return lead


def delete_lead(db: Session, lead_id: UUID | str) -> bool:
    """Delete a Lead record."""
    lead = get_lead(db, lead_id)
    if not lead:
        return False

    db.delete(lead)
    db.commit()
    return True
