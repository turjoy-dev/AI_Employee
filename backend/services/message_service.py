"""Business logic and CRUD service layer for Messages."""

from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models import Message
from backend.schemas.message import MessageCreate, MessageUpdate


def _to_uuid(val: UUID | str) -> UUID:
    return val if isinstance(val, UUID) else UUID(str(val))


def create_message(db: Session, message_in: MessageCreate) -> Message:
    """Create and persist a new Message turn in a conversation."""
    data = message_in.model_dump(exclude_none=True)
    message = Message(**data)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def save_user_message(
    db: Session,
    conversation_id: UUID | str,
    content: str,
    metadata_json: Optional[dict[str, Any] | str] = None,
) -> Message:
    """Persist an incoming customer/user message to the Message table."""
    return create_message(
        db,
        MessageCreate(
            conversation_id=_to_uuid(conversation_id),
            role="user",
            content=content,
            metadata_json=metadata_json,
        ),
    )


def save_assistant_message(
    db: Session,
    conversation_id: UUID | str,
    content: str,
    metadata_json: Optional[dict[str, Any] | str] = None,
) -> Message:
    """Persist a generated AI assistant reply to the Message table."""
    return create_message(
        db,
        MessageCreate(
            conversation_id=_to_uuid(conversation_id),
            role="assistant",
            content=content,
            metadata_json=metadata_json,
        ),
    )


def get_recent_conversation_messages(
    db: Session,
    conversation_id: UUID | str,
    limit: int = 5,
) -> List[Message]:
    """Fetch the last `limit` messages for a conversation in chronological order."""
    if limit <= 0:
        return []
    stmt = (
        select(Message)
        .where(Message.conversation_id == _to_uuid(conversation_id))
        .order_by(Message.timestamp.asc(), Message.created_at.asc())
    )
    all_messages = list(db.execute(stmt).scalars().all())
    return all_messages[-limit:]



def get_message(db: Session, message_id: UUID | str) -> Optional[Message]:
    """Retrieve a single Message by UUID."""
    return db.get(Message, _to_uuid(message_id))


def list_messages(
    db: Session,
    conversation_id: Optional[UUID | str] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[Message]:
    """List messages chronologically, optionally filtered by conversation."""
    stmt = select(Message)
    if conversation_id is not None:
        stmt = stmt.where(Message.conversation_id == _to_uuid(conversation_id))
    stmt = stmt.order_by(Message.timestamp.asc()).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def update_message(
    db: Session,
    message_id: UUID | str,
    message_in: MessageUpdate,
) -> Optional[Message]:
    """Partially update an existing Message record."""
    message = get_message(db, message_id)
    if not message:
        return None

    update_data = message_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(message, field, value)

    db.commit()
    db.refresh(message)
    return message


def delete_message(db: Session, message_id: UUID | str) -> bool:
    """Delete a single Message record."""
    message = get_message(db, message_id)
    if not message:
        return False

    db.delete(message)
    db.commit()
    return True
