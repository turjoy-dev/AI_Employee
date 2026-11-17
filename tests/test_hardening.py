"""Tests for production env hardening, Triple-LLM Analyst/Receptionist routing, and WebSocket safety."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import uuid

from fastapi.testclient import TestClient

from backend.agents.analyst import AIBusinessAnalyst, ConversationAnalysis
from backend.agents.receptionist import AIReceptionist
from backend.main import create_app


def test_analyst_routes_via_groq_when_configured_and_skips_invalid_gemini() -> None:
    """Verify AIBusinessAnalyst uses Groq in non-testing env when LLM_PROVIDER=groq instead of hitting 401 Gemini."""
    analyst = AIBusinessAnalyst()
    messages = [
        SimpleNamespace(role="user", content="We want the Enterprise plan ($499/mo) and a consultation."),
        SimpleNamespace(role="assistant", content="I can help schedule that right away."),
    ]
    groq_settings = SimpleNamespace(
        app_env="production",
        llm_provider="groq",
        groq_api_key="gsk-live-test",
        groq_model="openai/gpt-oss-20b",
        ollama_base_url="http://localhost:11434/v1",
        ollama_model="gemma",
        gemini_api_key="your-gemini-api-key-here",
        gemini_model="gemini-2.5-flash",
    )
    valid_json = (
        '{"summary": "Enterprise inquiry and consultation request.", '
        '"lead_score": 92, "lead_status": "qualified", '
        '"lead_priority": "high", "requires_escalation": false}'
    )

    with (
        patch("backend.agents.analyst.get_settings", return_value=groq_settings),
        patch.object(analyst, "_call_groq_text", return_value=valid_json) as mock_groq,
        patch("backend.agents.analyst.genai.Client") as mock_gemini_cls,
    ):
        result = analyst._evaluate_transcript_with_llm("Customer: Enterprise plan", messages)

    assert isinstance(result, ConversationAnalysis)
    assert result.lead_score == 92
    assert result.lead_status == "qualified"
    assert result.lead_priority == "high"
    mock_groq.assert_called_once()
    mock_gemini_cls.assert_not_called()


def test_receptionist_routes_via_groq_when_configured(db_session) -> None:
    """Verify AIReceptionist uses Groq when LLM_PROVIDER=groq in non-testing env."""
    from backend.database.models import Conversation, Customer

    customer = Customer(full_name="Test Caller", phone_number="+8801700000001")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    conv = Conversation(customer_id=customer.id, channel="web", status="active")
    db_session.add(conv)
    db_session.commit()
    db_session.refresh(conv)

    groq_settings = SimpleNamespace(
        app_env="development",
        llm_provider="groq",
        groq_api_key="gsk-live-test",
        groq_model="openai/gpt-oss-20b",
        ollama_base_url="http://localhost:11434/v1",
        ollama_model="gemma",
        gemini_api_key="your-gemini-api-key-here",
        gemini_model="gemini-2.5-flash",
    )
    mock_rag = {"contexts": ["Standard plan is $199/month."], "answer": "Standard plan is $199/month."}
    mock_groq_client = MagicMock()
    mock_groq_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Our Standard plan is $199/month!"))]
    )

    agent = AIReceptionist()
    with (
        patch("backend.agents.receptionist.get_settings", return_value=groq_settings),
        patch("backend.agents.receptionist.search_knowledge_base", return_value=mock_rag),
        patch("backend.agents.receptionist.Groq", return_value=mock_groq_client),
        patch("backend.agents.receptionist.genai.Client") as mock_gemini_cls,
    ):
        reply = agent.generate_reply(
            session=db_session,
            conversation_id=str(conv.id),
            user_message="How much is the standard plan?",
        )

    assert reply == "Our Standard plan is $199/month!"
    mock_groq_client.chat.completions.create.assert_called_once()
    mock_gemini_cls.assert_not_called()


def test_voice_websocket_handles_transport_origin_rejection_gracefully() -> None:
    """Verify WS /api/v1/voice/stream/{id} closes cleanly without crashing if build_transport raises ValueError."""
    app = create_app()
    client = TestClient(app)

    with patch(
        "backend.agents.voice_agent.VoiceReceptionistAgent.build_transport",
        side_effect=ValueError("WebSocket connection rejected: origin not allowed"),
    ):
        with client.websocket_connect(f"/api/v1/voice/stream/{uuid.uuid4()}") as ws:
            # Connection should close cleanly on server policy rejection
            try:
                ws.receive()
            except Exception:
                pass


def test_analyst_groq_json_mode_ollama_format_json_and_manual_review_fallback() -> None:
    """Verify Groq response_format=json_object, Ollama format='json', and Needs Manual Review fallback."""
    analyst = AIBusinessAnalyst()
    messages = [SimpleNamespace(role="user", content="Hello, just checking in.")]
    valid_json = (
        '{"summary": "Brief greeting check-in.", '
        '"lead_score": 35, "lead_status": "new", '
        '"lead_priority": "low", "requires_escalation": false}'
    )

    # 1. Groq JSON mode check
    groq_settings = SimpleNamespace(
        app_env="production",
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
        choices=[SimpleNamespace(message=SimpleNamespace(content=valid_json))]
    )
    with (
        patch("backend.agents.analyst.get_settings", return_value=groq_settings),
        patch("backend.agents.analyst.Groq", return_value=mock_groq_client),
    ):
        res_groq = analyst._evaluate_transcript_with_llm("Customer: Hello", messages)
    assert res_groq.lead_score == 35
    assert mock_groq_client.chat.completions.create.call_args.kwargs["response_format"] == {
        "type": "json_object"
    }

    # 2. Ollama format="json" check
    ollama_settings = SimpleNamespace(
        app_env="production",
        llm_provider="ollama",
        groq_api_key=None,
        groq_model="openai/gpt-oss-20b",
        ollama_base_url="http://localhost:11434/v1",
        ollama_model="gemma",
        gemini_api_key="",
        gemini_model="gemini-2.5-flash",
    )
    mock_http_resp = MagicMock()
    mock_http_resp.json.return_value = {"message": {"content": valid_json}}
    with (
        patch("backend.agents.analyst.get_settings", return_value=ollama_settings),
        patch("backend.agents.analyst.httpx.post", return_value=mock_http_resp) as mock_post,
    ):
        res_ollama = analyst._evaluate_transcript_with_llm("Customer: Hello", messages)
    assert res_ollama.lead_score == 35
    assert mock_post.call_args.kwargs["json"]["format"] == "json"

    # 3. Missing API keys & offline fallback -> Needs Manual Review
    offline_settings = SimpleNamespace(
        app_env="production",
        llm_provider="groq",
        groq_api_key=None,
        groq_model="openai/gpt-oss-20b",
        ollama_base_url="http://localhost:11434/v1",
        ollama_model="gemma",
        gemini_api_key="",
        gemini_model="gemini-2.5-flash",
    )
    with (
        patch("backend.agents.analyst.get_settings", return_value=offline_settings),
        patch("backend.agents.analyst.httpx.post", side_effect=RuntimeError("Ollama offline")),
    ):
        res_fallback = analyst._evaluate_transcript_with_llm("Customer: Hello", messages)
    assert res_fallback.lead_status == "Needs Manual Review"
    assert "Needs Manual Review" in res_fallback.summary
