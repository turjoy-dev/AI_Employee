"""Phase 8 WebSocket Voice Router & Pipecat Pipeline tests."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import BackgroundTasks, WebSocketDisconnect
from fastapi.testclient import TestClient

from backend.main import create_app


def test_voice_websocket_accepts_receives_payload_and_disconnects_cleanly() -> None:
    """Verify WS /api/v1/voice/stream/{conversation_id} accepts audio, handles disconnect, and runs background tasks."""
    app = create_app()
    client = TestClient(app)
    bg_called = False

    def sample_post_call_task() -> None:
        nonlocal bg_called
        bg_called = True

    async def fake_run_voice_session(
        self,
        websocket,
        conversation_id: str,
        background_tasks: BackgroundTasks | None = None,
    ) -> None:
        assert conversation_id == "test-uuid"
        payload = await websocket.receive_bytes()
        assert payload == b"\x00\x01\x02\x03"
        if background_tasks is not None:
            background_tasks.add_task(sample_post_call_task)
        # Wait for client disconnect to simulate active session lifecycle
        try:
            await websocket.receive_bytes()
        except WebSocketDisconnect:
            raise

    with (
        patch(
            "backend.agents.voice_agent.VoiceReceptionistAgent.build_pipeline_task",
            new=AsyncMock(),
        ),
        patch(
            "backend.agents.voice_agent.VoiceReceptionistAgent.run_voice_session",
            new=fake_run_voice_session,
        ),
    ):
        with client.websocket_connect("/api/v1/voice/stream/test-uuid") as ws:
            ws.send_bytes(b"\x00\x01\x02\x03")

    assert bg_called is True


def test_voice_websocket_handles_abrupt_disconnect_without_server_crash() -> None:
    """Verify abrupt WebSocketDisconnect inside run_voice_session does not raise an unhandled error."""
    app = create_app()
    client = TestClient(app)

    mock_run = AsyncMock(side_effect=WebSocketDisconnect(code=1006))

    with (
        patch(
            "backend.agents.voice_agent.VoiceReceptionistAgent.build_pipeline_task",
            new=AsyncMock(return_value=(MagicMock(), MagicMock(), AsyncMock())),
        ),
        patch(
            "backend.agents.voice_agent.VoiceReceptionistAgent.run_voice_session",
            new=mock_run,
        ),
    ):
        with client.websocket_connect("/api/v1/voice/stream/test-uuid"):
            pass

    mock_run.assert_awaited_once()


def test_voice_agent_switches_dynamically_between_ollama_groq_and_gemini() -> None:
    """Verify VoiceReceptionistAgent._create_llm routes across OLLamaLLMService, GroqLLMService, and GoogleLLMService."""
    from types import SimpleNamespace
    from pipecat.services.google.llm import GoogleLLMService
    from pipecat.services.groq.llm import GroqLLMService
    from pipecat.services.ollama.llm import OLLamaLLMService
    from backend.agents.voice_agent import VoiceReceptionistAgent

    agent = VoiceReceptionistAgent()

    ollama_settings = SimpleNamespace(
        llm_provider="ollama",
        ollama_model="gemma",
        ollama_base_url="http://localhost:11434/v1",
        groq_api_key=None,
        groq_model="llama-3.1-8b-instant",
        gemini_api_key="",
    )
    with (
        patch("backend.agents.voice_agent.get_settings", return_value=ollama_settings),
        patch.object(VoiceReceptionistAgent, "_is_ollama_reachable", return_value=True),
    ):
        llm_ollama = agent._create_llm("Voice system prompt")
        assert isinstance(llm_ollama, OLLamaLLMService)
        assert llm_ollama._settings.model == "gemma"

    groq_settings = SimpleNamespace(
        llm_provider="groq",
        ollama_model="gemma",
        ollama_base_url="http://localhost:11434/v1",
        groq_api_key="gsk-test-key",
        groq_model="llama-3.1-8b-instant",
        gemini_api_key="",
    )
    with patch("backend.agents.voice_agent.get_settings", return_value=groq_settings):
        llm_groq = agent._create_llm("Voice system prompt")
        assert isinstance(llm_groq, GroqLLMService)
        assert llm_groq._settings.model == "llama-3.1-8b-instant"

    # When Ollama is offline and a valid Gemini key exists, fall back cleanly to Gemini
    offline_ollama_settings = SimpleNamespace(
        llm_provider="ollama",
        ollama_model="gemma",
        ollama_base_url="http://localhost:11434/v1",
        groq_api_key=None,
        groq_model="llama-3.1-8b-instant",
        gemini_api_key="real-fallback-gemini-key",
    )
    with (
        patch("backend.agents.voice_agent.get_settings", return_value=offline_ollama_settings),
        patch.object(VoiceReceptionistAgent, "_is_ollama_reachable", return_value=False),
    ):
        llm_fallback = agent._create_llm("Voice system prompt")
        assert isinstance(llm_fallback, GoogleLLMService)

    gemini_settings = SimpleNamespace(
        llm_provider="gemini",
        ollama_model="gemma",
        ollama_base_url="http://localhost:11434/v1",
        groq_api_key=None,
        groq_model="llama-3.1-8b-instant",
        gemini_api_key="test-gemini-key",
    )
    with patch("backend.agents.voice_agent.get_settings", return_value=gemini_settings):
        llm_gemini = agent._create_llm("Voice system prompt")
        assert isinstance(llm_gemini, GoogleLLMService)
        assert llm_gemini._settings.model == agent.llm_model


def test_run_voice_session_cancels_task_and_finalizes_on_pipeline_error() -> None:
    """Ensure abrupt pipeline/Ollama failures cancel Pipecat tasks and finalize the call cleanly."""
    import asyncio
    from backend.agents.voice_agent import VoiceReceptionistAgent

    agent = VoiceReceptionistAgent()
    mock_task = MagicMock()
    mock_task.cancel = AsyncMock()
    mock_finalize = AsyncMock()

    mock_runner = MagicMock()
    mock_runner.run = AsyncMock(side_effect=RuntimeError("Ollama connection refused"))

    with (
        patch.object(agent, "build_transport", return_value=MagicMock()),
        patch.object(
            agent,
            "build_pipeline_task",
            new=AsyncMock(return_value=(mock_task, MagicMock(), mock_finalize)),
        ),
        patch("backend.agents.voice_agent.PipelineRunner", return_value=mock_runner),
    ):
        asyncio.run(agent.run_voice_session(MagicMock(), "test-uuid"))

    mock_task.cancel.assert_awaited_once()
    mock_finalize.assert_awaited_once()
