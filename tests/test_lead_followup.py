"""Unit and integration tests for Lead Follow-Up drafting and sending endpoints."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.agents.analyst import AIBusinessAnalyst
from backend.database.models import Message


def _get_admin_headers(client: TestClient) -> dict[str, str]:
    """Register or login the default test admin user and return Authorization headers."""
    client.post(
        "/api/v1/auth/register",
        json={"email": "admin@test.local", "password": "TestAdminPassword!123"},
    )
    token_resp = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "TestAdminPassword!123"},
    )
    token = token_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_lead_with_conversation(client: TestClient) -> tuple[str, str]:
    """Create customer, conversation, messages, and lead via API and return (lead_id, conversation_id)."""
    cust_resp = client.post(
        "/api/v1/customers",
        json={
            "full_name": "Tariq Mahmud",
            "phone_number": "+8801711009988",
            "email": "tariq@example.com",
            "preferred_language": "en",
        },
    )
    assert cust_resp.status_code == 201
    customer_id = cust_resp.json()["id"]

    conv_resp = client.post(
        "/api/v1/conversations",
        json={
            "customer_id": customer_id,
            "channel": "web_chat",
            "status": "active",
            "summary": "Customer inquired about Enterprise automation setup pricing.",
        },
    )
    assert conv_resp.status_code == 201
    conversation_id = conv_resp.json()["id"]

    client.post(
        "/api/v1/messages",
        json={
            "conversation_id": conversation_id,
            "role": "user",
            "content": "Hi, how much does your Enterprise plan cost and can we schedule a demo?",
        },
    )
    client.post(
        "/api/v1/messages",
        json={
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": "Our Enterprise plan starts at $999/month. Would you like to book a consultation?",
        },
    )

    lead_resp = client.post(
        "/api/v1/leads",
        json={
            "customer_id": customer_id,
            "conversation_id": conversation_id,
            "source": "receptionist",
            "status": "qualified",
            "priority": "high",
            "score": 88,
            "notes": "High intent enterprise inquiry.",
        },
    )
    assert lead_resp.status_code == 201
    return lead_resp.json()["id"], conversation_id


def test_draft_follow_up_requires_auth_and_returns_ai_draft(client: TestClient) -> None:
    """Verify POST /api/v1/leads/{id}/draft-follow-up requires auth and returns a drafted message."""
    lead_id, _ = _seed_lead_with_conversation(client)

    unauth_resp = client.post(f"/api/v1/leads/{lead_id}/draft-follow-up")
    assert unauth_resp.status_code == 401

    headers = _get_admin_headers(client)
    mock_draft = (
        "Hi Tariq, thank you for your interest in our Enterprise plan. "
        "I would love to schedule your consultation this week—what time works best for you?"
    )
    with patch.object(AIBusinessAnalyst, "draft_follow_up", return_value=mock_draft) as mock_fn:
        resp = client.post(f"/api/v1/leads/{lead_id}/draft-follow-up", headers=headers)

    assert resp.status_code == 200
    assert resp.json() == {"draft": mock_draft}
    mock_fn.assert_called_once()


def test_draft_follow_up_404_for_missing_lead(client: TestClient) -> None:
    """Verify drafting follow-up for a nonexistent lead returns 404."""
    headers = _get_admin_headers(client)
    resp = client.post(f"/api/v1/leads/{uuid.uuid4()}/draft-follow-up", headers=headers)
    assert resp.status_code == 404


def test_draft_follow_up_triple_llm_router_groq_and_fallback() -> None:
    """Verify AIBusinessAnalyst.draft_follow_up routes via Groq and falls back cleanly if offline."""
    analyst = AIBusinessAnalyst()
    lead = SimpleNamespace(id=uuid.uuid4(), score=85, status="qualified", priority="high", notes="Interested in Standard plan.")
    customer = SimpleNamespace(full_name="Ayesha Rahman", email="ayesha@example.com", phone_number="+8801911223344")
    messages = [
        SimpleNamespace(role="user", content="Can I book a consultation for Tuesday?"),
        SimpleNamespace(role="assistant", content="Sure, we have morning slots available."),
    ]

    groq_settings = SimpleNamespace(
        llm_provider="groq",
        groq_api_key="gsk-test-key",
        groq_model="openai/gpt-oss-20b",
        ollama_base_url="http://localhost:11434/v1",
        ollama_model="gemma",
        gemini_api_key="",
        gemini_model="gemini-2.5-flash",
    )
    mock_groq_client = MagicMock()
    mock_groq_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Hi Ayesha, let's confirm your Tuesday morning consultation!"))]
    )

    with (
        patch("backend.agents.analyst.get_settings", return_value=groq_settings),
        patch("backend.agents.analyst.Groq", return_value=mock_groq_client),
    ):
        draft = analyst.draft_follow_up(lead=lead, customer=customer, messages=messages)

    assert "Ayesha" in draft
    mock_groq_client.chat.completions.create.assert_called_once()

    # Fallback check when Groq raises an exception and no other keys are configured
    mock_groq_client.chat.completions.create.side_effect = RuntimeError("Network timeout")
    with (
        patch("backend.agents.analyst.get_settings", return_value=groq_settings),
        patch("backend.agents.analyst.Groq", return_value=mock_groq_client),
    ):
        fallback_draft = analyst.draft_follow_up(lead=lead, customer=customer, messages=messages)

    assert "Ayesha Rahman" in fallback_draft
    assert "[" not in fallback_draft  # Ensure no bracketed placeholders


def test_send_follow_up_saves_admin_message_and_handles_no_conversation(
    client: TestClient,
    db_session: Session,
) -> None:
    """Verify POST /api/v1/leads/{id}/send-follow-up appends an admin message to conversation or notes."""
    headers = _get_admin_headers(client)
    lead_id, conversation_id = _seed_lead_with_conversation(client)

    follow_up_text = "Hi Tariq, checking in to schedule your Enterprise demo this Thursday at 2 PM."
    resp = client.post(
        f"/api/v1/leads/{lead_id}/send-follow-up",
        json={"message": follow_up_text},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "success"}

    saved_msgs = (
        db_session.query(Message)
        .filter(Message.conversation_id == uuid.UUID(conversation_id))
        .all()
    )
    admin_msgs = [m for m in saved_msgs if m.role == "admin"]
    assert len(admin_msgs) == 1
    assert admin_msgs[0].content == follow_up_text

    # Test lead without conversation_id persists into lead.notes
    cust_resp = client.post(
        "/api/v1/customers",
        json={"full_name": "No Conv User", "phone_number": "+8801555667788"},
    )
    orphan_lead_resp = client.post(
        "/api/v1/leads",
        json={
            "customer_id": cust_resp.json()["id"],
            "source": "website",
            "status": "new",
            "priority": "medium",
            "score": 55,
        },
    )
    orphan_lead_id = orphan_lead_resp.json()["id"]

    resp_orphan = client.post(
        f"/api/v1/leads/{orphan_lead_id}/send-follow-up",
        json={"message": "Following up via email."},
        headers=headers,
    )
    assert resp_orphan.status_code == 200
    assert resp_orphan.json() == {"status": "success"}

    updated_lead = client.get(f"/api/v1/leads/{orphan_lead_id}").json()
    assert "Following up via email." in (updated_lead["notes"] or "")


def test_send_follow_up_rejects_blank_message_and_missing_lead(client: TestClient) -> None:
    """Verify validation on blank messages and 404 on missing lead."""
    headers = _get_admin_headers(client)
    lead_id, _ = _seed_lead_with_conversation(client)

    blank_resp = client.post(
        f"/api/v1/leads/{lead_id}/send-follow-up",
        json={"message": "   "},
        headers=headers,
    )
    assert blank_resp.status_code == 422

    missing_resp = client.post(
        f"/api/v1/leads/{uuid.uuid4()}/send-follow-up",
        json={"message": "Hello there"},
        headers=headers,
    )
    assert missing_resp.status_code == 404
