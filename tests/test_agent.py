"""Unit and integration tests for Phase 4 AI Receptionist Agent and /api/v1/chat/receptionist."""

import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.agents.receptionist import AIReceptionist
from backend.database.models import Conversation, Customer, Message
from backend.services.message_service import (
    get_recent_conversation_messages,
    save_assistant_message,
    save_user_message,
)


def test_ai_receptionist_generate_reply_fetches_last_5_messages_and_rag_contexts(db_session: Session):
    """Verify AIReceptionist.generate_reply retrieves RAG contexts, fetches last 5 messages, and calls gemini-2.5-flash."""
    customer = Customer(
        full_name="Rahim Uddin",
        phone_number="+8801711009988",
        preferred_language="bn",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    conversation = Conversation(
        customer_id=customer.id,
        channel="web",
        status="active",
    )
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)

    # Seed 6 historical messages so we can verify only the last 5 are included in memory
    for idx in range(1, 7):
        role = "user" if idx % 2 == 1 else "assistant"
        save_user_message(db_session, conversation.id, f"Turn {idx} message") if role == "user" else save_assistant_message(
            db_session, conversation.id, f"Turn {idx} message"
        )

    recent_five = get_recent_conversation_messages(db_session, conversation.id, limit=5)
    assert len(recent_five) == 5
    assert [m.content for m in recent_five] == [
        "Turn 2 message",
        "Turn 3 message",
        "Turn 4 message",
        "Turn 5 message",
        "Turn 6 message",
    ]

    mock_rag_output = {
        "query": "What is the consultation fee?",
        "answer": "- **Initial Business Consultation:** $50 (or 5,000 BDT) for a 45-minute session.",
        "contexts": [
            "## 2. Services & Pricing\n- **Initial Business Consultation:** $50 (or 5,000 BDT) for a 45-minute session."
        ],
    }

    mock_gemini_response = MagicMock()
    mock_gemini_response.text = "Our Initial Business Consultation costs $50 (or 5,000 BDT) for a 45-minute session."

    with (
        patch("backend.agents.receptionist.search_knowledge_base", return_value=mock_rag_output) as mock_search,
        patch("backend.agents.receptionist.genai.Client") as mock_client_cls,
    ):
        mock_client_instance = MagicMock()
        mock_client_instance.models.generate_content.return_value = mock_gemini_response
        mock_client_cls.return_value = mock_client_instance

        agent = AIReceptionist()
        reply = agent.generate_reply(
            session=db_session,
            conversation_id=str(conversation.id),
            user_message="What is the consultation fee?",
        )

        assert reply == "Our Initial Business Consultation costs $50 (or 5,000 BDT) for a 45-minute session."
        mock_search.assert_called_once_with("What is the consultation fee?")
        mock_client_instance.models.generate_content.assert_called_once()

        call_kwargs = mock_client_instance.models.generate_content.call_args.kwargs
        assert call_kwargs["model"] == "gemini-2.5-flash"

        # Verify that Turn 1 (6th oldest) was excluded while Turns 2..6 and RAG context were injected
        serialized_call = str(call_kwargs)
        assert "Turn 1 message" not in serialized_call
        assert "Turn 2 message" in serialized_call
        assert "Turn 6 message" in serialized_call
        assert "5,000 BDT" in serialized_call


def test_chat_receptionist_endpoint_saves_user_and_assistant_messages(
    client: TestClient,
    db_session: Session,
):
    """POST /api/v1/chat/receptionist saves both user and assistant messages and returns 200 OK."""
    cust_resp = client.post(
        "/api/v1/customers",
        json={
            "full_name": "Farhana Akter",
            "phone_number": "+8801811998877",
            "email": "farhana@example.com",
            "preferred_language": "bn",
        },
    )
    assert cust_resp.status_code == 201
    customer_id = cust_resp.json()["id"]

    conv_resp = client.post(
        "/api/v1/conversations",
        json={
            "customer_id": customer_id,
            "channel": "web",
            "status": "active",
        },
    )
    assert conv_resp.status_code == 201
    conversation_id = conv_resp.json()["id"]

    mock_rag_output = {
        "query": "আপনাদের অফিস কখন খোলা থাকে?",
        "answer": "- **Monday to Friday:** 9:00 AM - 6:00 PM (BST / UTC+6)",
        "contexts": [
            "## 1. Store & Office Hours\n- **Monday to Friday:** 9:00 AM - 6:00 PM (BST / UTC+6)\n- **Saturday:** 10:00 AM - 4:00 PM"
        ],
    }

    expected_ai_reply = (
        "আমাদের অফিস সোম থেকে শুক্রবার সকাল ৯টা থেকে সন্ধ্যা ৬টা পর্যন্ত (BST) এবং শনিবার সকাল ১০টা থেকে বিকেল ৪টা পর্যন্ত খোলা থাকে।"
    )
    mock_gemini_response = MagicMock()
    mock_gemini_response.text = expected_ai_reply

    with (
        patch("backend.agents.receptionist.search_knowledge_base", return_value=mock_rag_output) as mock_search,
        patch("backend.agents.receptionist.genai.Client") as mock_client_cls,
    ):
        mock_client_instance = MagicMock()
        mock_client_instance.models.generate_content.return_value = mock_gemini_response
        mock_client_cls.return_value = mock_client_instance

        chat_payload = {
            "customer_id": customer_id,
            "conversation_id": conversation_id,
            "content": "আপনাদের অফিস কখন খোলা থাকে?",
        }
        response = client.post("/api/v1/chat/receptionist", json=chat_payload)

        assert response.status_code == 200
        data = response.json()
        assert data["customer_id"] == customer_id
        assert data["conversation_id"] == conversation_id
        assert data["reply"] == expected_ai_reply
        assert data["content"] == expected_ai_reply
        assert "user_message_id" in data
        assert "assistant_message_id" in data

        mock_search.assert_called_once_with("আপনাদের অফিস কখন খোলা থাকে?")
        assert mock_client_instance.models.generate_content.call_count >= 1

    # Verify both user and assistant messages were persisted to the SQLite test database
    saved_messages = (
        db_session.query(Message)
        .filter(Message.conversation_id == uuid.UUID(conversation_id))
        .order_by(Message.timestamp.asc())
        .all()
    )
    assert len(saved_messages) == 2
    assert saved_messages[0].role == "user"
    assert saved_messages[0].content == "আপনাদের অফিস কখন খোলা থাকে?"
    assert saved_messages[1].role == "assistant"
    assert saved_messages[1].content == expected_ai_reply


def test_chat_receptionist_returns_404_for_missing_customer_or_conversation(client: TestClient):
    """Ensure /api/v1/chat/receptionist validates customer_id and conversation_id existence."""
    fake_customer_id = str(uuid.uuid4())
    fake_conversation_id = str(uuid.uuid4())

    resp = client.post(
        "/api/v1/chat/receptionist",
        json={
            "customer_id": fake_customer_id,
            "conversation_id": fake_conversation_id,
            "content": "Hello!",
        },
    )
    assert resp.status_code == 404
