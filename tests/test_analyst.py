"""Unit and integration tests for Phase 5 AI Business Analyst & FastAPI BackgroundTasks."""

import uuid
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.agents.analyst import AIBusinessAnalyst, ConversationAnalysis
from backend.database.models import Conversation, Customer, Lead
from backend.services.message_service import save_assistant_message, save_user_message


def test_analyze_conversation_updates_conversation_summary_and_creates_lead(db_session: Session):
    """Test AIBusinessAnalyst.analyze_conversation updates Conversation.summary and creates/updates Lead."""
    # 1. Create a mock customer and conversation with messages in the test database
    customer = Customer(
        full_name="Karim Chowdhury",
        phone_number="+8801711229900",
        email="karim@example.com",
        preferred_language="en",
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

    save_user_message(
        db_session,
        conversation.id,
        "Hello, we need the Enterprise AI Employee Suite ($499/month) and want to book an Initial Business Consultation.",
    )
    save_assistant_message(
        db_session,
        conversation.id,
        "Our Enterprise AI Employee Suite is $499/month and the Initial Business Consultation is $50 for 45 minutes. I would be happy to book that for you!",
    )

    # 2. Mock the Gemini API call to return a static ConversationAnalysis object
    static_analysis = ConversationAnalysis(
        summary="Customer inquired about the $499/month Enterprise AI Employee Suite and requested an Initial Business Consultation.",
        lead_score=90,
        lead_status="qualified",
        lead_priority="high",
        requires_escalation=False,
    )

    mock_gemini_response = MagicMock()
    mock_gemini_response.parsed = static_analysis
    mock_gemini_response.text = static_analysis.model_dump_json()

    with patch("backend.agents.analyst.genai.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_client_instance.models.generate_content.return_value = mock_gemini_response
        mock_client_cls.return_value = mock_client_instance

        # 3. Call analyze_conversation directly
        analyst = AIBusinessAnalyst()
        result = analyst.analyze_conversation(str(conversation.id))

        assert isinstance(result, ConversationAnalysis)
        assert result.lead_score == 90
        assert result.lead_status == "qualified"
        assert result.lead_priority == "high"
        assert result.requires_escalation is False

        mock_client_instance.models.generate_content.assert_called_once()
        call_kwargs = mock_client_instance.models.generate_content.call_args.kwargs
        assert call_kwargs["model"] == "gemini-2.5-flash"

    # 4. Assert that Conversation.summary and Lead table were updated in SQLite
    db_session.expire_all()
    updated_conversation = db_session.get(Conversation, conversation.id)
    assert updated_conversation is not None
    assert updated_conversation.summary == static_analysis.summary

    leads = list(
        db_session.execute(
            select(Lead).where(
                Lead.customer_id == customer.id,
                Lead.conversation_id == conversation.id,
            )
        )
        .scalars()
        .all()
    )
    assert len(leads) == 1
    lead = leads[0]
    assert lead.score == 90
    assert lead.status == "qualified"
    assert lead.priority == "high"

    # 5. Re-running analyze_conversation on the same conversation updates the existing Lead instead of duplicating
    escalated_analysis = ConversationAnalysis(
        summary="Customer requested urgent human manager follow-up to finalize contract.",
        lead_score=98,
        lead_status="qualified",
        lead_priority="high",
        requires_escalation=True,
    )
    mock_gemini_response.parsed = escalated_analysis
    mock_gemini_response.text = escalated_analysis.model_dump_json()

    with patch("backend.agents.analyst.genai.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_client_instance.models.generate_content.return_value = mock_gemini_response
        mock_client_cls.return_value = mock_client_instance

        analyst.analyze_conversation(str(conversation.id))

    db_session.expire_all()
    leads_after = list(
        db_session.execute(
            select(Lead).where(
                Lead.customer_id == customer.id,
                Lead.conversation_id == conversation.id,
            )
        )
        .scalars()
        .all()
    )
    assert len(leads_after) == 1
    assert leads_after[0].score == 98
    assert db_session.get(Conversation, conversation.id).summary == escalated_analysis.summary


def test_chat_receptionist_triggers_analyst_background_task(
    client: TestClient,
    db_session: Session,
):
    """Verify POST /api/v1/chat/receptionist triggers AIBusinessAnalyst().analyze_conversation in BackgroundTasks."""
    cust = client.post(
        "/api/v1/customers",
        json={"full_name": "Mahmudul Hasan", "phone_number": "+8801911887766"},
    ).json()
    conv = client.post(
        "/api/v1/conversations",
        json={"customer_id": cust["id"], "channel": "web"},
    ).json()

    mock_receptionist_resp = MagicMock()
    mock_receptionist_resp.text = "Our Standard AI Receptionist Setup is $199/month."

    static_analysis = ConversationAnalysis(
        summary="Customer asked about Standard AI Receptionist Setup pricing ($199/month).",
        lead_score=75,
        lead_status="qualified",
        lead_priority="medium",
        requires_escalation=False,
    )
    mock_analyst_resp = MagicMock()
    mock_analyst_resp.parsed = static_analysis
    mock_analyst_resp.text = static_analysis.model_dump_json()

    with (
        patch(
            "backend.agents.receptionist.search_knowledge_base",
            return_value={"query": "price", "answer": "$199/month", "contexts": ["$199/month"]},
        ),
        patch("backend.agents.receptionist.genai.Client") as mock_rec_client_cls,
        patch("backend.agents.analyst.genai.Client") as mock_ana_client_cls,
    ):
        mock_rec_client = MagicMock()
        mock_rec_client.models.generate_content.return_value = mock_receptionist_resp
        mock_rec_client_cls.return_value = mock_rec_client

        mock_ana_client = MagicMock()
        mock_ana_client.models.generate_content.return_value = mock_analyst_resp
        mock_ana_client_cls.return_value = mock_ana_client

        resp = client.post(
            "/api/v1/chat/receptionist",
            json={
                "customer_id": cust["id"],
                "conversation_id": conv["id"],
                "content": "How much is the Standard AI Receptionist Setup?",
            },
        )
        assert resp.status_code == 200

    db_session.expire_all()
    updated_conv = db_session.get(Conversation, uuid.UUID(conv["id"]))
    assert updated_conv is not None
    assert updated_conv.summary == static_analysis.summary

    lead = (
        db_session.execute(select(Lead).where(Lead.conversation_id == updated_conv.id))
        .scalars()
        .first()
    )
    assert lead is not None
    assert lead.score == 75
    assert lead.status == "qualified"
    assert lead.priority == "medium"
