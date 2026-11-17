"""Unit and integration tests for Phase 2 SQLAlchemy 2.0 business models and relationships."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from backend.database.models import (
    Appointment,
    Conversation,
    Customer,
    Lead,
    Message,
)


def test_customer_and_relationships_creation(db_session: Session):
    """Verify UUID primary keys, UTC timestamps, and ORM relationships across all 5 entities."""
    customer = Customer(
        full_name="Rahim Uddin",
        phone_number="+8801711000001",
        email="rahim@example.com",
        preferred_language="bn",
        notes="Interested in premium consultation.",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    assert isinstance(customer.id, UUID)
    assert isinstance(customer.created_at, datetime)
    assert customer.created_at.tzinfo == timezone.utc
    assert isinstance(customer.updated_at, datetime)
    assert customer.updated_at.tzinfo == timezone.utc
    assert customer.preferred_language == "bn"

    # Create Conversation
    conversation = Conversation(
        customer_id=customer.id,
        channel="voice",
        status="active",
        summary="Caller asked about consultation pricing.",
    )
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)

    assert isinstance(conversation.id, UUID)
    assert conversation.customer_id == customer.id

    # Create Messages
    msg1 = Message(
        conversation_id=conversation.id,
        role="user",
        content="আসসালামু আলাইকুম, আপনাদের সার্ভিস চার্জ কত?",
        metadata_json={"language": "bn", "confidence": 0.98},
    )
    msg2 = Message(
        conversation_id=conversation.id,
        role="assistant",
        content="ওয়ালাইকুম আসসালাম! আমাদের কনসালটেশন ফি ১০০০ টাকা।",
        metadata_json={"language": "bn"},
    )
    db_session.add_all([msg1, msg2])
    db_session.commit()

    # Create Lead
    lead = Lead(
        customer_id=customer.id,
        conversation_id=conversation.id,
        source="receptionist",
        status="qualified",
        priority="high",
        score=85,
        notes="Ready to book this week.",
    )
    db_session.add(lead)

    # Create Appointment
    scheduled_time = datetime.now(timezone.utc) + timedelta(days=2)
    appointment = Appointment(
        customer_id=customer.id,
        conversation_id=conversation.id,
        title="Initial Business Consultation",
        scheduled_at=scheduled_time,
        duration_minutes=45,
        status="scheduled",
    )
    db_session.add(appointment)
    db_session.commit()

    db_session.refresh(customer)
    db_session.refresh(conversation)

    assert len(customer.conversations) == 1
    assert len(conversation.messages) == 2
    assert conversation.messages[0].metadata_json == {"language": "bn", "confidence": 0.98}
    assert len(customer.leads) == 1
    assert customer.leads[0].score == 85
    assert len(customer.appointments) == 1
    assert customer.appointments[0].duration_minutes == 45


def test_cascade_delete_customer_removes_all_dependents(db_session: Session):
    """Deleting a customer should cascade-delete conversations, messages, leads, and appointments."""
    customer = Customer(full_name="Cascade Test User", phone_number="+8801711000002")
    db_session.add(customer)
    db_session.commit()

    conversation = Conversation(customer_id=customer.id, channel="web")
    db_session.add(conversation)
    db_session.commit()

    message = Message(conversation_id=conversation.id, role="user", content="Hello")
    lead = Lead(customer_id=customer.id, conversation_id=conversation.id)
    appointment = Appointment(
        customer_id=customer.id,
        conversation_id=conversation.id,
        title="Demo Call",
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add_all([message, lead, appointment])
    db_session.commit()

    conv_id = conversation.id
    msg_id = message.id
    lead_id = lead.id
    appt_id = appointment.id

    # Delete customer
    db_session.delete(customer)
    db_session.commit()
    db_session.expire_all()

    assert db_session.get(Conversation, conv_id) is None
    assert db_session.get(Message, msg_id) is None
    assert db_session.get(Lead, lead_id) is None
    assert db_session.get(Appointment, appt_id) is None


def test_delete_conversation_cascades_messages_and_nullifies_lead_and_appointment_fk(
    db_session: Session,
):
    """Deleting a conversation deletes its messages and sets conversation_id=NULL on leads/appointments."""
    customer = Customer(full_name="Partial Cascade User", phone_number="+8801711000003")
    db_session.add(customer)
    db_session.commit()

    conversation = Conversation(customer_id=customer.id, channel="phone")
    db_session.add(conversation)
    db_session.commit()

    message = Message(conversation_id=conversation.id, role="user", content="Book me in")
    lead = Lead(customer_id=customer.id, conversation_id=conversation.id, score=90)
    appointment = Appointment(
        customer_id=customer.id,
        conversation_id=conversation.id,
        title="Follow-up",
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=3),
    )
    db_session.add_all([message, lead, appointment])
    db_session.commit()

    msg_id = message.id
    lead_id = lead.id
    appt_id = appointment.id

    db_session.delete(conversation)
    db_session.commit()
    db_session.expire_all()

    assert db_session.get(Message, msg_id) is None
    remaining_lead = db_session.get(Lead, lead_id)
    remaining_appt = db_session.get(Appointment, appt_id)
    assert remaining_lead is not None
    assert remaining_lead.conversation_id is None
    assert remaining_appt is not None
    assert remaining_appt.conversation_id is None
