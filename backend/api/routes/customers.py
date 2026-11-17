"""Thin REST API routes for Customer management."""

from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.database.connection import get_db
from backend.database.models import User
from backend.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate
from backend.services import customer_service

router = APIRouter(prefix="/customers", tags=["Customers"])

DBSession = Annotated[Session, Depends(get_db)]
CurrentAdmin = Annotated[User, Depends(get_current_user)]


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new customer",
)
def create_customer(customer_in: CustomerCreate, db: DBSession):
    """Create a new customer record."""
    if customer_in.phone_number and customer_service.get_customer_by_phone(
        db, customer_in.phone_number
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A customer with this phone number already exists.",
        )
    if customer_in.email and customer_service.get_customer_by_email(db, customer_in.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A customer with this email already exists.",
        )
    return customer_service.create_customer(db, customer_in)


@router.get(
    "",
    response_model=List[CustomerResponse],
    summary="List customers (Admin Auth Required)",
)
def list_customers(
    db: DBSession,
    _current_user: CurrentAdmin,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    """Retrieve a paginated list of customers."""
    return customer_service.list_customers(db, skip=skip, limit=limit)


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Get customer by ID",
)
def get_customer(customer_id: UUID, db: DBSession):
    """Retrieve a customer by UUID."""
    customer = customer_service.get_customer(db, customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )
    return customer


@router.patch(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Update a customer",
)
def update_customer(customer_id: UUID, customer_in: CustomerUpdate, db: DBSession):
    """Partially update an existing customer."""
    if customer_in.phone_number:
        existing_phone = customer_service.get_customer_by_phone(db, customer_in.phone_number)
        if existing_phone and existing_phone.id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A customer with this phone number already exists.",
            )
    if customer_in.email:
        existing_email = customer_service.get_customer_by_email(db, customer_in.email)
        if existing_email and existing_email.id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A customer with this email already exists.",
            )
    customer = customer_service.update_customer(db, customer_id, customer_in)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )
    return customer


@router.delete(
    "/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a customer",
)
def delete_customer(customer_id: UUID, db: DBSession) -> Response:
    """Delete a customer and cascade delete associated records."""
    deleted = customer_service.delete_customer(db, customer_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
