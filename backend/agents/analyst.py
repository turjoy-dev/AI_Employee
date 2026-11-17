"""AI Business Analyst Agent for asynchronous conversation summarization and lead qualification."""

import logging
from typing import Any, List, Literal, Optional
from uuid import UUID

import httpx
from google import genai
from google.genai import types
from groq import Groq
from langfuse import observe
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

import backend.database.connection as db_connection
from backend.core.config import get_settings
from backend.database.models import Conversation, Lead, Message
from backend.services.message_service import list_messages

logger = logging.getLogger(__name__)

DEFAULT_ANALYST_MODEL = "gemini-2.5-flash"

ANALYST_SYSTEM_PROMPT = """You are the Principal AI Business Analyst for AI Employee.
Your responsibility is to evaluate customer-receptionist conversation transcripts (in English, Bangla / বাংলা, or Banglish) and produce a structured CRM intelligence assessment.

### EVALUATION GUIDELINES
1. **summary**: Write a concise, executive 1-2 sentence summary capturing the customer's core inquiry, intent, and outcome.
2. **lead_score (0 to 100)**:
   - `80-100`: High commercial intent (pricing inquiries for Standard/Enterprise tiers, consultation booking requests, or enterprise onboarding).
   - `40-79`: Moderate intent (general service questions, store hours, comparing plans).
   - `0-39`: Low intent (casual greeting, unrelated query, or explicit cancellation/disinterest).
3. **lead_status**: Must be one of `'new'`, `'qualified'`, or `'lost'`.
   - Use `'qualified'` when `lead_score >= 60` or the caller asks about pricing, services, or booking an appointment.
   - Use `'lost'` if the caller explicitly declines service or cancels permanently.
   - Otherwise use `'new'`.
4. **lead_priority**: Must be one of `'low'`, `'medium'`, or `'high'`.
   - Use `'high'` for enterprise inquiries, consultation bookings, or escalations (`lead_score >= 80` or `requires_escalation=True`).
   - Use `'medium'` for active service/pricing inquiries (`lead_score` between 40 and 79).
   - Use `'low'` for basic informational questions (`lead_score < 40`).
5. **requires_escalation**: Set to `True` if the customer reports a billing dispute, urgent technical outage, or explicitly asks to speak with the business owner or a human manager; otherwise `False`.
"""

FOLLOW_UP_SYSTEM_PROMPT = (
    "You are a professional sales assistant. Based on this lead's conversation history and score, "
    "draft a concise, polite follow-up email/message to move them towards a booking. "
    "Do not include placeholders, output the exact message."
)


class ConversationAnalysis(BaseModel):
    """Structured LLM output schema for conversation intelligence and lead scoring."""

    summary: str = Field(..., description="Concise executive summary of the conversation")
    lead_score: int = Field(..., ge=0, le=100, description="Lead qualification score from 0 to 100")
    lead_status: Literal["new", "qualified", "lost"] | str = Field(
        ...,
        description="Lead status: 'new', 'qualified', or 'lost'",
    )
    lead_priority: Literal["low", "medium", "high"] | str = Field(
        ...,
        description="Lead priority: 'low', 'medium', or 'high'",
    )
    requires_escalation: bool = Field(
        ...,
        description="Whether human manager escalation is required",
    )


def _to_uuid(val: UUID | str) -> UUID:
    return val if isinstance(val, UUID) else UUID(str(val))


class AIBusinessAnalyst:
    """AI Business Analyst that evaluates conversation transcripts and updates CRM records."""

    def __init__(
        self,
        model: str = DEFAULT_ANALYST_MODEL,
        api_key: Optional[str] = None,
        client: Optional[Any] = None,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self._client = client

    def _get_client(self) -> genai.Client:
        """Return an initialized Google GenAI Client."""
        if self._client is not None:
            return self._client
        settings = get_settings()
        effective_api_key = (
            self.api_key
            or settings.gemini_api_key
            or "placeholder-gemini-api-key"
        )
        return genai.Client(api_key=effective_api_key)

    @staticmethod
    def format_transcript(messages: List[Message]) -> str:
        """Format ordered conversation messages into a single chat transcript string."""
        if not messages:
            return "No messages recorded in this conversation."
        lines: List[str] = []
        for msg in messages:
            role_label = "Customer" if msg.role.lower() == "user" else "AI Receptionist"
            lines.append(f"{role_label}: {msg.content}")
        return "\n".join(lines)

    @staticmethod
    def _parse_analysis_response(response: Any) -> Optional[ConversationAnalysis]:
        """Extract a validated ConversationAnalysis instance from a google-genai response."""
        if isinstance(response, ConversationAnalysis):
            return response

        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, ConversationAnalysis):
            return parsed
        if isinstance(parsed, dict):
            return ConversationAnalysis.model_validate(parsed)

        raw_text = getattr(response, "text", None)
        if isinstance(raw_text, str) and raw_text.strip():
            return ConversationAnalysis.model_validate_json(raw_text.strip())

        return None

    @staticmethod
    def _heuristic_fallback_analysis(messages: List[Message]) -> ConversationAnalysis:
        """Deterministic fallback analysis when no live Gemini API key is configured locally."""
        user_texts = [m.content.strip() for m in messages if m.role.lower() == "user" and m.content.strip()]
        combined_lower = " ".join(m.content for m in messages).lower()

        requires_escalation = any(
            kw in combined_lower
            for kw in ("dispute", "outage", "owner", "human manager", "urgent", "escalat")
        )
        high_intent = any(
            kw in combined_lower
            for kw in ("consultation", "enterprise", "book", "appointment", "price", "cost", "setup", "$", "bdt")
        )

        if requires_escalation:
            score = 90
            status = "qualified"
            priority = "high"
        elif high_intent:
            score = 80
            status = "qualified"
            priority = "high" if ("consultation" in combined_lower or "enterprise" in combined_lower) else "medium"
        else:
            score = 40
            status = "Needs Manual Review"
            priority = "low"

        latest_inquiry = user_texts[-1] if user_texts else "General customer interaction."
        summary = f"[Needs Manual Review] Customer inquiry ({len(messages)} turns): {latest_inquiry[:160]}"

        return ConversationAnalysis(
            summary=summary,
            lead_score=score,
            lead_status=status,
            lead_priority=priority,
            requires_escalation=requires_escalation,
        )

    @staticmethod
    def _extract_json_text(raw_text: str) -> str:
        """Strip optional markdown code fences around JSON output."""
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        return cleaned

    @observe(as_type="generation")
    def _evaluate_transcript_with_llm(self, transcript: str, messages: List[Message]) -> ConversationAnalysis:
        """Evaluate conversation transcript via Triple-LLM router (Groq/Ollama/Gemini) with heuristic fallback."""
        settings = get_settings()
        is_testing = str(getattr(settings, "app_env", "")).strip().lower() == "testing"
        prompt = (
            "Analyze the following customer support conversation transcript and return ONLY a valid JSON object "
            "with exact keys: summary (string), lead_score (integer 0-100), "
            "lead_status ('new'|'qualified'|'lost'), lead_priority ('low'|'medium'|'high'), "
            "requires_escalation (boolean).\n\n"
            f"<CONVERSATION_TRANSCRIPT>\n{transcript}\n</CONVERSATION_TRANSCRIPT>"
        )

        # Preserve direct Gemini path when a client is explicitly injected or during unit tests
        if self._client is not None or is_testing:
            try:
                client = self._get_client()
                response = client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=ANALYST_SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        response_schema=ConversationAnalysis,
                        temperature=0.1,
                    ),
                )
                analysis = self._parse_analysis_response(response)
                if analysis is not None:
                    return analysis
            except Exception as exc:
                logger.warning(
                    f"Gemini Analyst structured output call failed ({exc}); using deterministic heuristic fallback."
                )
            return self._heuristic_fallback_analysis(messages)

        primary = (getattr(settings, "llm_provider", "ollama") or "ollama").strip().lower()
        provider_order = [primary] + [p for p in ("groq", "ollama", "gemini") if p != primary]

        for provider in provider_order:
            try:
                if provider == "groq":
                    raw = self._call_groq_text(
                        settings, ANALYST_SYSTEM_PROMPT, prompt, json_mode=True
                    )
                    if raw:
                        return ConversationAnalysis.model_validate_json(self._extract_json_text(raw))
                elif provider == "ollama":
                    raw = self._call_ollama_text(
                        settings, ANALYST_SYSTEM_PROMPT, prompt, json_mode=True
                    )
                    if raw:
                        return ConversationAnalysis.model_validate_json(self._extract_json_text(raw))
                elif provider == "gemini":
                    gemini_key = (getattr(settings, "gemini_api_key", None) or "").strip()
                    if not gemini_key or gemini_key in {"your-gemini-api-key-here", "placeholder"}:
                        continue
                    client = self._get_client()
                    response = client.models.generate_content(
                        model=self.model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=ANALYST_SYSTEM_PROMPT,
                            response_mime_type="application/json",
                            response_schema=ConversationAnalysis,
                            temperature=0.1,
                        ),
                    )
                    analysis = self._parse_analysis_response(response)
                    if analysis is not None:
                        return analysis
            except Exception as exc:
                logger.warning(
                    f"Analyst evaluation via '{provider}' failed ({exc}); trying next provider."
                )

        return self._heuristic_fallback_analysis(messages)

    def analyze_conversation(
        self,
        conversation_id_or_session: str | UUID | Session,
        maybe_conversation_id: Optional[str | UUID] = None,
        *,
        session: Optional[Session] = None,
    ) -> Optional[ConversationAnalysis]:
        """Analyze a conversation transcript and update Conversation.summary and the Lead table.

        Initializes a fresh SQLite session when invoked as a FastAPI BackgroundTask to prevent
        cross-thread session sharing conflicts, while also supporting an explicit `session` for direct tests.
        """
        external_session: Optional[Session] = session
        if isinstance(conversation_id_or_session, Session):
            external_session = conversation_id_or_session
            if maybe_conversation_id is None:
                raise ValueError("conversation_id is required when passing a Session as the first argument.")
            conv_uuid = _to_uuid(maybe_conversation_id)
        else:
            conv_uuid = _to_uuid(conversation_id_or_session)

        owns_session = external_session is None
        db: Session = external_session if external_session is not None else db_connection.SessionLocal()

        try:
            conversation = db.get(Conversation, conv_uuid)
            if not conversation:
                logger.warning(f"AIBusinessAnalyst: Conversation '{conv_uuid}' not found.")
                return None

            customer_uuid = _to_uuid(conversation.customer_id)
            conversation_uuid = _to_uuid(conversation.id)

            # 1. Fetch all messages for this conversation_id and format into a transcript
            messages = list_messages(db, conversation_id=conversation_uuid, limit=500)
            transcript = self.format_transcript(messages)

            # 2. Evaluate transcript with Gemini Structured Outputs (`ConversationAnalysis`)
            analysis = self._evaluate_transcript_with_llm(transcript, messages)

            # 3. Update Conversation.summary
            conversation.summary = analysis.summary
            db.commit()
            db.refresh(conversation)

            # 4. Strictly map ConversationAnalysis fields to SQLAlchemy Lead model fields
            mapped_score = max(0, min(100, int(analysis.lead_score)))
            mapped_status = str(analysis.lead_status).strip().lower() or "new"
            mapped_priority = str(analysis.lead_priority).strip().lower() or "medium"

            escalation_note = (
                " [ESCALATION REQUIRED: Transfer to human manager]"
                if analysis.requires_escalation
                else ""
            )
            lead_notes = f"{analysis.summary}{escalation_note}"

            try:
                existing_lead = (
                    db.execute(
                        select(Lead).where(
                            Lead.customer_id == customer_uuid,
                            Lead.conversation_id == conversation_uuid,
                        )
                    )
                    .scalars()
                    .first()
                )

                if existing_lead is not None:
                    existing_lead.customer_id = customer_uuid
                    existing_lead.conversation_id = conversation_uuid
                    existing_lead.score = mapped_score
                    existing_lead.status = mapped_status
                    existing_lead.priority = mapped_priority
                    existing_lead.notes = lead_notes
                    db.commit()
                    db.refresh(existing_lead)
                else:
                    new_lead = Lead(
                        customer_id=customer_uuid,
                        conversation_id=conversation_uuid,
                        source="receptionist",
                        score=mapped_score,
                        status=mapped_status,
                        priority=mapped_priority,
                        notes=lead_notes,
                    )
                    db.add(new_lead)
                    db.commit()
                    db.refresh(new_lead)
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to create lead: {e}", exc_info=True)
                raise

            return analysis
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create lead: {e}", exc_info=True)
            raise
        finally:
            if owns_session:
                db.close()

    @staticmethod
    def _heuristic_follow_up_draft(lead: Any, customer: Any, messages: List[Any]) -> str:
        """Return a polite, placeholder-free follow-up message when LLMs are unavailable."""
        customer_name = (getattr(customer, "full_name", None) or "").strip()
        greeting = f"Hi {customer_name}," if customer_name else "Hello,"

        last_user_msg = next(
            (
                m.content.strip()
                for m in reversed(messages)
                if getattr(m, "role", "").lower() == "user" and getattr(m, "content", "").strip()
            ),
            "",
        )
        notes = (getattr(lead, "notes", None) or "").strip()

        if last_user_msg:
            context_snippet = last_user_msg[:120].rstrip(".!?")
            topic_line = f'Following up on your recent inquiry ("{context_snippet}"), '
        elif notes:
            topic_line = f"Following up on our recent notes ({notes[:120].rstrip('.')}), "
        else:
            topic_line = "Thank you for connecting with AI Employee. Following up on our conversation, "

        return (
            f"{greeting}\n\n"
            f"{topic_line}we would be happy to walk you through the next steps and answer any remaining questions. "
            "Would you like to schedule a quick 15-minute consultation this week at a time convenient for you?\n\n"
            "Best regards,\nAI Employee Team"
        )

    def _call_groq_text(
        self,
        settings: Any,
        system_prompt: str,
        user_prompt: str,
        *,
        json_mode: bool = False,
    ) -> Optional[str]:
        """Generate text (or structured JSON) via Groq Chat Completions API."""
        groq_key = (getattr(settings, "groq_api_key", None) or "").strip()
        if not groq_key:
            return None
        groq_model = getattr(settings, "groq_model", "llama-3.1-8b-instant")
        kwargs: dict[str, Any] = {
            "model": groq_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1 if json_mode else 0.4,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if str(groq_model).startswith("openai/gpt-oss"):
            kwargs["reasoning_effort"] = "low"
        client = Groq(api_key=groq_key)
        response = client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content if response.choices else ""
        return (content or "").strip() or None

    def _call_ollama_text(
        self,
        settings: Any,
        system_prompt: str,
        user_prompt: str,
        *,
        json_mode: bool = False,
    ) -> Optional[str]:
        """Generate text (or local JSON via format='json') through Ollama."""
        base_url = getattr(settings, "ollama_base_url", "http://localhost:11434/v1").rstrip("/")
        ollama_model = getattr(settings, "ollama_model", "gemma")

        if json_mode:
            ollama_root = base_url[:-3] if base_url.endswith("/v1") else base_url
            resp = httpx.post(
                f"{ollama_root}/api/chat",
                json={
                    "model": ollama_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
                timeout=20.0,
            )
            resp.raise_for_status()
            content = (resp.json().get("message") or {}).get("content") or ""
            return content.strip() or None

        resp = httpx.post(
            f"{base_url}/chat/completions",
            json={
                "model": ollama_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.4,
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            return None
        content = (choices[0].get("message") or {}).get("content") or ""
        return content.strip() or None

    def _call_gemini_text(self, settings: Any, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Generate text via Google Gemini SDK."""
        gemini_key = (getattr(settings, "gemini_api_key", None) or "").strip()
        if not gemini_key or gemini_key in {"your-gemini-api-key-here", "placeholder"}:
            return None
        client = self._get_client() if self._client is not None else genai.Client(api_key=gemini_key)
        model_name = getattr(settings, "gemini_model", self.model) or self.model
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.4,
            ),
        )
        return (getattr(response, "text", None) or "").strip() or None

    @observe(as_type="generation")
    def draft_follow_up(
        self,
        lead: Any,
        customer: Any,
        messages: List[Any],
    ) -> str:
        """Draft a personalized follow-up message using the configured Triple-LLM router."""
        customer_name = (getattr(customer, "full_name", None) or "").strip() or "Valued Customer"
        customer_email = (getattr(customer, "email", None) or "").strip() or "Not provided"
        customer_phone = (getattr(customer, "phone_number", None) or "").strip() or "Not provided"
        transcript = self.format_transcript(messages)

        user_prompt = (
            f"Customer Name: {customer_name}\n"
            f"Customer Email: {customer_email}\n"
            f"Customer Phone: {customer_phone}\n"
            f"Lead Score: {getattr(lead, 'score', 0)}/100\n"
            f"Lead Status: {getattr(lead, 'status', 'new')}\n"
            f"Lead Priority: {getattr(lead, 'priority', 'medium')}\n"
            f"Analyst Notes: {getattr(lead, 'notes', None) or 'None'}\n\n"
            f"Conversation History:\n{transcript}"
        )

        settings = get_settings()
        primary = (getattr(settings, "llm_provider", "ollama") or "ollama").strip().lower()
        provider_order = [primary] + [p for p in ("groq", "ollama", "gemini") if p != primary]

        callers = {
            "groq": self._call_groq_text,
            "ollama": self._call_ollama_text,
            "gemini": self._call_gemini_text,
        }

        for provider in provider_order:
            caller = callers.get(provider)
            if caller is None:
                continue
            try:
                draft = caller(settings, FOLLOW_UP_SYSTEM_PROMPT, user_prompt)
                if draft:
                    return draft
            except Exception as exc:
                logger.warning(f"Follow-up draft via '{provider}' failed ({exc}); trying fallback.")

        return self._heuristic_follow_up_draft(lead, customer, messages)
