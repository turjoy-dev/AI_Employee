"""Business logic and CRUD service layer for Customers."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models import Customer
from backend.schemas.customer import CustomerCreate, CustomerUpdate


def _to_uuid(val: UUID | str) -> UUID:
    return val if isinstance(val, UUID) else UUID(str(val))


def create_customer(db: Session, customer_in: CustomerCreate) -> Customer:
    """Create and persist a new Customer record."""
    customer = Customer(**customer_in.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def get_customer(db: Session, customer_id: UUID | str) -> Optional[Customer]:
    """Retrieve a single Customer by UUID."""
    return db.get(Customer, _to_uuid(customer_id))


def get_customer_by_phone(db: Session, phone_number: str) -> Optional[Customer]:
    """Retrieve a Customer by unique phone number."""
    stmt = select(Customer).where(Customer.phone_number == phone_number)
    return db.execute(stmt).scalar_one_or_none()


def get_customer_by_email(db: Session, email: str) -> Optional[Customer]:
    """Retrieve a Customer by unique email address."""
    stmt = select(Customer).where(Customer.email == email)
    return db.execute(stmt).scalar_one_or_none()


def list_customers(db: Session, skip: int = 0, limit: int = 100) -> List[Customer]:
    """List customers with pagination ordered by newest first."""
    stmt = select(Customer).order_by(Customer.created_at.desc()).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def update_customer(
    db: Session,
    customer_id: UUID | str,
    customer_in: CustomerUpdate,
) -> Optional[Customer]:
    """Partially update an existing Customer record."""
    customer = get_customer(db, customer_id)
    if not customer:
        return None

    update_data = customer_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(customer, field, value)

    db.commit()
    db.refresh(customer)
    return customer


def delete_customer(db: Session, customer_id: UUID | str) -> bool:
    """Delete a Customer record and cascade to dependent records."""
    customer = get_customer(db, customer_id)
    if not customer:
        return False

    db.delete(customer)
    db.commit()
    return True
