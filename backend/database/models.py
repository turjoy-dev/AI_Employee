"""SQLAlchemy 2.x declarative models and business domain schema."""

import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    TypeDecorator,
    Uuid,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    validates,
)


def utc_now() -> datetime:
    """Return current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Ensure datetimes stored and retrieved from SQLite are always timezone-aware UTC."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Optional[datetime], _dialect: Any) -> Optional[datetime]:
        if value is not None:
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value: Optional[datetime], _dialect: Any) -> Optional[datetime]:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


def _ensure_uuid(value: Optional[uuid.UUID | str]) -> Optional[uuid.UUID]:
    """Coerce string UUID values to uuid.UUID objects."""
    if value is None or isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


class TimestampMixin:
    """Mixin providing UTC created_at and updated_at audit timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
        nullable=False,
    )


class SystemMetadata(Base):
    """Stores system configuration and migration metadata for verification."""

    __tablename__ = "system_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=utc_now,
        server_default=func.now(),
        onupdate=utc_now,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<SystemMetadata(key='{self.key}', value='{self.value}')>"


class User(TimestampMixin, Base):
    """Represents a business owner or administrator account for authentication."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(50),
        default="admin",
        server_default="admin",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="1",
        nullable=False,
    )

    @validates("id")
    def _validate_uuid(self, _key: str, value: Optional[uuid.UUID | str]) -> Optional[uuid.UUID]:
        return _ensure_uuid(value)

    def __repr__(self) -> str:
        return f"<User(id='{self.id}', email='{self.email}', role='{self.role}')>"



class Customer(TimestampMixin, Base):
    """Represents a business customer or caller."""

    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=True,
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=True,
    )
    preferred_language: Mapped[str] = mapped_column(
        String(20),
        default="en",
        server_default="en",
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation",
        back_populates="customer",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    leads: Mapped[List["Lead"]] = relationship(
        "Lead",
        back_populates="customer",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    appointments: Mapped[List["Appointment"]] = relationship(
        "Appointment",
        back_populates="customer",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @validates("id")
    def _validate_uuid(self, _key: str, value: Optional[uuid.UUID | str]) -> Optional[uuid.UUID]:
        return _ensure_uuid(value)

    def __repr__(self) -> str:
        return f"<Customer(id='{self.id}', full_name='{self.full_name}')>"


class Conversation(TimestampMixin, Base):
    """Represents an interaction session between a customer and an AI agent."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(
        String(50),
        default="web",
        server_default="web",
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="active",
        server_default="active",
        nullable=False,
        index=True,
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime(),
        nullable=True,
    )

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.timestamp",
    )
    leads: Mapped[List["Lead"]] = relationship(
        "Lead",
        back_populates="conversation",
        passive_deletes=True,
    )
    appointments: Mapped[List["Appointment"]] = relationship(
        "Appointment",
        back_populates="conversation",
        passive_deletes=True,
    )

    @validates("id", "customer_id")
    def _validate_uuid(self, _key: str, value: Optional[uuid.UUID | str]) -> Optional[uuid.UUID]:
        return _ensure_uuid(value)

    def __repr__(self) -> str:
        return f"<Conversation(id='{self.id}', customer_id='{self.customer_id}', status='{self.status}')>"


class Message(TimestampMixin, Base):
    """Represents a single utterance or message turn within a conversation."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[dict[str, Any] | str]] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")

    @validates("id", "conversation_id")
    def _validate_uuid(self, _key: str, value: Optional[uuid.UUID | str]) -> Optional[uuid.UUID]:
        return _ensure_uuid(value)

    def __repr__(self) -> str:
        return f"<Message(id='{self.id}', conversation_id='{self.conversation_id}', role='{self.role}')>"


class Lead(TimestampMixin, Base):
    """Represents a sales opportunity or business lead identified from customer interactions."""

    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(
        String(100),
        default="receptionist",
        server_default="receptionist",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="new",
        server_default="new",
        nullable=False,
        index=True,
    )
    priority: Mapped[str] = mapped_column(
        String(50),
        default="medium",
        server_default="medium",
        nullable=False,
        index=True,
    )
    score: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="leads")
    conversation: Mapped[Optional["Conversation"]] = relationship("Conversation", back_populates="leads")

    @validates("id", "customer_id", "conversation_id")
    def _validate_uuid(self, _key: str, value: Optional[uuid.UUID | str]) -> Optional[uuid.UUID]:
        return _ensure_uuid(value)

    def __repr__(self) -> str:
        return f"<Lead(id='{self.id}', customer_id='{self.customer_id}', status='{self.status}')>"


class Appointment(TimestampMixin, Base):
    """Represents a scheduled customer appointment or booking."""

    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        index=True,
    )
    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        default=30,
        server_default="30",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="scheduled",
        server_default="scheduled",
        nullable=False,
        index=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="appointments")
    conversation: Mapped[Optional["Conversation"]] = relationship(
        "Conversation",
        back_populates="appointments",
    )

    @validates("id", "customer_id", "conversation_id")
    def _validate_uuid(self, _key: str, value: Optional[uuid.UUID | str]) -> Optional[uuid.UUID]:
        return _ensure_uuid(value)

    def __repr__(self) -> str:
        return f"<Appointment(id='{self.id}', title='{self.title}', scheduled_at='{self.scheduled_at}')>"
