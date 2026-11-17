"""Thin FastAPI WebSocket router for real-time Pipecat voice streaming."""

import asyncio
from fastapi import APIRouter, BackgroundTasks, WebSocket, WebSocketDisconnect, status

from backend.agents.voice_agent import VoiceReceptionistAgent
from backend.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Voice"])

MAX_CONCURRENT_VOICE_STREAMS = 10
_voice_session_lock = asyncio.Lock()
_active_voice_sessions = 0


@router.websocket("/stream/{conversation_id}")
async def voice_stream(websocket: WebSocket, conversation_id: str) -> None:
    """Handle bidirectional WebSocket audio streaming for a voice receptionist session."""
    global _active_voice_sessions

    async with _voice_session_lock:
        if _active_voice_sessions >= MAX_CONCURRENT_VOICE_STREAMS:
            logger.warning(
                f"Rejected voice WebSocket for '{conversation_id}': max concurrency "
                f"({MAX_CONCURRENT_VOICE_STREAMS}) reached."
            )
            await websocket.close(
                code=status.WS_1013_TRY_AGAIN_LATER,
                reason="Voice server busy. Please try again shortly.",
            )
            return
        _active_voice_sessions += 1

    await websocket.accept()
    logger.info(f"Accepted voice WebSocket stream for conversation '{conversation_id}'")

    background_tasks = BackgroundTasks()
    agent = VoiceReceptionistAgent()

    try:
        await agent.run_voice_session(
            websocket=websocket,
            conversation_id=conversation_id,
            background_tasks=background_tasks,
        )
    except ValueError as exc:
        logger.warning(f"Rejected voice WebSocket for '{conversation_id}': {exc}")
        try:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Origin not allowed.",
            )
        except Exception:
            pass
    except WebSocketDisconnect:
        logger.info(f"Voice WebSocket disconnected by client for conversation '{conversation_id}'")
    except Exception as exc:
        logger.error(
            f"Unexpected error in voice WebSocket for conversation '{conversation_id}': {exc}",
            exc_info=True,
        )
    finally:
        async with _voice_session_lock:
            _active_voice_sessions = max(0, _active_voice_sessions - 1)
        if background_tasks.tasks:
            try:
                await background_tasks()
            except Exception as exc:
                logger.error(
                    f"Failed running voice post-call background tasks for '{conversation_id}': {exc}",
                    exc_info=True,
                )
