"""Thin router for AI Receptionist conversational chat endpoints."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.agents.analyst import AIBusinessAnalyst
from backend.agents.receptionist import AIReceptionist
from backend.core.security import limiter
from backend.database.connection import get_db
from backend.schemas.chat import ReceptionistChatRequest, ReceptionistChatResponse
from backend.services.conversation_service import get_conversation
from backend.services.customer_service import get_customer
from backend.services.message_service import save_assistant_message, save_user_message

router = APIRouter(prefix="/chat", tags=["Chat"])

DBSession = Annotated[Session, Depends(get_db)]


def get_receptionist_agent() -> AIReceptionist:
    """Dependency provider returning an AIReceptionist instance."""
    return AIReceptionist()


ReceptionistDep = Annotated[AIReceptionist, Depends(get_receptionist_agent)]


@router.post(
    "/receptionist",
    response_model=ReceptionistChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a message to the AI Receptionist and persist the conversation turn",
)
@limiter.limit("10/minute")
def chat_with_receptionist(
    request: Request,
    payload: ReceptionistChatRequest,
    background_tasks: BackgroundTasks,
    db: DBSession,
    receptionist: ReceptionistDep,
) -> ReceptionistChatResponse:
    """Process an incoming customer message through the AI Receptionist pipeline.

    Flow:
    1. Validate Customer and Conversation existence.
    2. Save incoming User Message to SQLite (`messages` table).
    3. Generate AI reply via `AIReceptionist.generate_reply()` (RAG + 5-turn memory + Gemini + Langfuse).
    4. Save AI Assistant Message to SQLite (`messages` table).
    5. Queue `AIBusinessAnalyst().analyze_conversation` in FastAPI `BackgroundTasks`.
    6. Return the structured AI response JSON.
    """
    customer = get_customer(db, payload.customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{payload.customer_id}' not found.",
        )

    conversation = get_conversation(db, payload.conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{payload.conversation_id}' not found.",
        )

    if conversation.customer_id != customer.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversation does not belong to the specified customer_id.",
        )

    # 1. Save User Message (DB)
    user_msg = save_user_message(
        db=db,
        conversation_id=payload.conversation_id,
        content=payload.content,
    )

    # 2. Call AIReceptionist.generate_reply()
    reply_text = receptionist.generate_reply(
        session=db,
        conversation_id=str(payload.conversation_id),
        user_message=payload.content,
    )

    # 3. Save AI Message (DB)
    assistant_msg = save_assistant_message(
        db=db,
        conversation_id=payload.conversation_id,
        content=reply_text,
    )

    # 4. Trigger AI Business Analyst background task
    background_tasks.add_task(
        AIBusinessAnalyst().analyze_conversation,
        str(payload.conversation_id),
    )

    # 5. Return structured AI response
    return ReceptionistChatResponse(
        customer_id=payload.customer_id,
        conversation_id=payload.conversation_id,
        reply=reply_text,
        content=reply_text,
        user_message_id=user_msg.id,
        assistant_message_id=assistant_msg.id,
    )
