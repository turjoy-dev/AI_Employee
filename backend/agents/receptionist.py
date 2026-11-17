"""AI Receptionist Agent with RAG Context Injection, SQLite Memory, and Langfuse Tracing."""

from typing import Any, List, Optional

import httpx
from google import genai
from google.genai import types
from groq import Groq
from langfuse import observe
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.database.models import Message
from backend.rag.retrieval import search_knowledge_base
from backend.services.message_service import get_recent_conversation_messages

logger = get_logger(__name__)

DEFAULT_RECEPTIONIST_MODEL = "gemini-2.5-flash"
HISTORY_WINDOW_LIMIT = 5

RECEPTIONIST_SYSTEM_PROMPT_TEMPLATE = """You are the official AI Receptionist for AI Employee — an enterprise-grade, bilingual (English & Bangla / বাংলা) business automation platform.

### 1. CORE PERSONA & BILINGUAL COMMUNICATION
- **Language Adaptation:** Automatically detect the customer's language (English, Bangla / বাংলা, or Banglish) and respond naturally in the same language.
- **Tone:** Warm, courteous, executive, and concise. Avoid robotic filler phrases.
- **Conciseness:** Keep responses focused (typically 2-4 sentences or clean bullet points) so they are easy to read in chat or hear over voice telephony.

### 2. STRICT RAG GROUNDING & ANTI-HALLUCINATION RULES
- Base all factual answers regarding **Store & Office Hours**, **Services & Pricing ($ / BDT)**, **Refund & Cancellation Policies**, and **Human Escalation** strictly on the `<RETRIEVED_KNOWLEDGE_CONTEXT>` provided below.
- Never invent prices, discounts, store hours, or policy exceptions that are not explicitly stated in `<RETRIEVED_KNOWLEDGE_CONTEXT>`.
- If the customer asks a question not covered by the retrieved context, politely state what you can confirm and offer to connect them with a human specialist or book an Initial Business Consultation.

### 3. CONVERSATIONAL CONTINUITY & LEAD GUIDANCE
- Use the `<RECENT_CONVERSATION_HISTORY>` (up to the last 5 messages) to maintain context, avoid repeating questions, and remember customer preferences.
- When a customer shows interest in services or consultations, proactively offer to schedule an appointment or capture their contact details.

<RETRIEVED_KNOWLEDGE_CONTEXT>
{rag_context}
</RETRIEVED_KNOWLEDGE_CONTEXT>
"""


class AIReceptionist:
    """Production AI Receptionist Agent combining Chroma/LlamaIndex RAG, SQLite memory, and Gemini LLM."""

    def __init__(
        self,
        model: str = DEFAULT_RECEPTIONIST_MODEL,
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
    def build_system_prompt(contexts: List[str]) -> str:
        """Construct the bilingual system prompt injected with retrieved RAG contexts."""
        if contexts:
            formatted_context = "\n\n---\n\n".join(ctx.strip() for ctx in contexts if ctx.strip())
        else:
            formatted_context = "No specific knowledge base context retrieved for this query."
        return RECEPTIONIST_SYSTEM_PROMPT_TEMPLATE.format(rag_context=formatted_context)

    @staticmethod
    def format_conversation_prompt(
        recent_messages: List[Message],
        user_message: str,
        contexts: List[str],
    ) -> str:
        """Format the last 5 conversation turns, retrieved RAG context, and current user message."""
        history_lines: List[str] = []
        for msg in recent_messages:
            speaker = "User" if msg.role.lower() == "user" else "Assistant"
            history_lines.append(f"{speaker}: {msg.content}")

        history_block = (
            "\n".join(history_lines)
            if history_lines
            else "No prior messages in this conversation."
        )
        context_block = (
            "\n\n".join(ctx.strip() for ctx in contexts if ctx.strip())
            if contexts
            else "No relevant knowledge base context found."
        )

        return (
            "<RETRIEVED_KNOWLEDGE_CONTEXT>\n"
            f"{context_block}\n"
            "</RETRIEVED_KNOWLEDGE_CONTEXT>\n\n"
            "<RECENT_CONVERSATION_HISTORY>\n"
            f"{history_block}\n"
            "</RECENT_CONVERSATION_HISTORY>\n\n"
            f"Current User Message: {user_message}\n"
            "Assistant Reply:"
        )

    @observe(as_type="generation")
    def generate_reply(
        self,
        session: Session,
        conversation_id: str,
        user_message: str,
    ) -> str:
        """Generate a context-aware bilingual receptionist response traced with Langfuse.

        Steps:
        1. Retrieve relevant knowledge chunks via `search_knowledge_base(user_message)`.
        2. Fetch the last 5 messages for `conversation_id` from SQLite.
        3. Construct the Bilingual System Prompt with injected RAG contexts.
        4. Call `client.models.generate_content()` using `gemini-2.5-flash`.
        """
        # 1. Retrieve relevant RAG contexts from Phase 3 knowledge base
        rag_result = search_knowledge_base(user_message)
        contexts: List[str] = rag_result.get("contexts", []) if isinstance(rag_result, dict) else []
        fallback_rag_answer: str = (
            rag_result.get("answer", "") if isinstance(rag_result, dict) else ""
        )

        # 2. Fetch the last 5 messages from Phase 2 SQLite database for conversational memory
        recent_messages = get_recent_conversation_messages(
            session,
            conversation_id=conversation_id,
            limit=HISTORY_WINDOW_LIMIT,
        )

        # 3. Construct the System Prompt and user/history prompt payload
        system_prompt = self.build_system_prompt(contexts)
        prompt_contents = self.format_conversation_prompt(
            recent_messages=recent_messages,
            user_message=user_message,
            contexts=contexts,
        )

        # 4. Route through Triple-LLM provider chain (Groq / Ollama / Gemini)
        settings = get_settings()
        is_testing = str(getattr(settings, "app_env", "")).strip().lower() == "testing"

        if self._client is not None or is_testing:
            client = self._get_client()
            try:
                response = client.models.generate_content(
                    model=self.model,
                    contents=prompt_contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.3,
                    ),
                )
                reply_text = (getattr(response, "text", None) or "").strip()
                if reply_text:
                    return reply_text
            except Exception as exc:
                logger.warning(
                    f"Gemini API call failed for conversation {conversation_id} ({exc}); "
                    "falling back to grounded RAG answer."
                )
                if fallback_rag_answer:
                    return fallback_rag_answer
                raise
            return fallback_rag_answer or (
                "Thank you for reaching out to AI Employee. How may I assist you today?"
            )

        primary = (getattr(settings, "llm_provider", "ollama") or "ollama").strip().lower()
        provider_order = [primary] + [p for p in ("groq", "ollama", "gemini") if p != primary]

        for provider in provider_order:
            try:
                if provider == "groq":
                    groq_key = (getattr(settings, "groq_api_key", None) or "").strip()
                    if not groq_key:
                        continue
                    groq_model = getattr(settings, "groq_model", "llama-3.1-8b-instant")
                    kwargs: dict[str, Any] = {
                        "model": groq_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt_contents},
                        ],
                        "temperature": 0.3,
                    }
                    if str(groq_model).startswith("openai/gpt-oss"):
                        kwargs["reasoning_effort"] = "low"
                    groq_client = Groq(api_key=groq_key)
                    resp = groq_client.chat.completions.create(**kwargs)
                    reply_text = (resp.choices[0].message.content or "").strip() if resp.choices else ""
                    if reply_text:
                        return reply_text
                elif provider == "ollama":
                    base_url = getattr(settings, "ollama_base_url", "http://localhost:11434/v1").rstrip("/")
                    ollama_model = getattr(settings, "ollama_model", "gemma")
                    resp = httpx.post(
                        f"{base_url}/chat/completions",
                        json={
                            "model": ollama_model,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": prompt_contents},
                            ],
                            "temperature": 0.3,
                        },
                        timeout=15.0,
                    )
                    resp.raise_for_status()
                    choices = resp.json().get("choices") or []
                    reply_text = ((choices[0].get("message") or {}).get("content") or "").strip() if choices else ""
                    if reply_text:
                        return reply_text
                elif provider == "gemini":
                    gemini_key = (getattr(settings, "gemini_api_key", None) or "").strip()
                    if not gemini_key or gemini_key in {"your-gemini-api-key-here", "placeholder"}:
                        continue
                    client = self._get_client()
                    response = client.models.generate_content(
                        model=self.model,
                        contents=prompt_contents,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=0.3,
                        ),
                    )
                    reply_text = (getattr(response, "text", None) or "").strip()
                    if reply_text:
                        return reply_text
            except Exception as exc:
                logger.warning(
                    f"Receptionist LLM call via '{provider}' failed for conversation {conversation_id} ({exc}); "
                    "trying fallback."
                )

        return fallback_rag_answer or (
            "Thank you for reaching out to AI Employee. How may I assist you today?"
        )
