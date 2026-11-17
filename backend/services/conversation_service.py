"""Business logic and CRUD service layer for Conversations."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models import Conversation
from backend.schemas.conversation import ConversationCreate, ConversationUpdate


def _to_uuid(val: UUID | str) -> UUID:
    return val if isinstance(val, UUID) else UUID(str(val))


def create_conversation(db: Session, conversation_in: ConversationCreate) -> Conversation:
    """Create and persist a new Conversation record."""
    data = conversation_in.model_dump(exclude_none=True)
    conversation = Conversation(**data)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_conversation(db: Session, conversation_id: UUID | str) -> Optional[Conversation]:
    """Retrieve a single Conversation by UUID."""
    return db.get(Conversation, _to_uuid(conversation_id))


def list_conversations(
    db: Session,
    customer_id: Optional[UUID | str] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[Conversation]:
    """List conversations with optional customer filter and pagination."""
    stmt = select(Conversation)
    if customer_id is not None:
        stmt = stmt.where(Conversation.customer_id == _to_uuid(customer_id))
    stmt = stmt.order_by(Conversation.started_at.desc()).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def update_conversation(
    db: Session,
    conversation_id: UUID | str,
    conversation_in: ConversationUpdate,
) -> Optional[Conversation]:
    """Partially update an existing Conversation record."""
    conversation = get_conversation(db, conversation_id)
    if not conversation:
        return None

    update_data = conversation_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(conversation, field, value)

    db.commit()
    db.refresh(conversation)
    return conversation


def delete_conversation(db: Session, conversation_id: UUID | str) -> bool:
    """Delete a Conversation record and cascade to its messages."""
    conversation = get_conversation(db, conversation_id)
    if not conversation:
        return False

    db.delete(conversation)
    db.commit()
    return True
