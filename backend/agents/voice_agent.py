"""Free local real-time Voice Receptionist agent powered by Pipecat, Silero VAD, Faster-Whisper, Gemini 2.5 Flash, and Piper TTS."""

import asyncio
import json
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import UUID

import httpx
import torch
from fastapi import BackgroundTasks, WebSocketDisconnect
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import (
    Frame,
    InputAudioRawFrame,
    LLMRunFrame,
    OutputAudioRawFrame,
    TextFrame,
    TranscriptionFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.serializers.base_serializer import FrameSerializer
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.ollama.llm import OLLamaLLMService
from pipecat.services.piper.tts import PiperTTSService
from pipecat.services.whisper.stt import Model as WhisperModelSize
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.transcriptions.language import Language
from pipecat.transports.base_transport import BaseTransport
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

import backend.database.connection as db_connection
from backend.agents.analyst import AIBusinessAnalyst
from backend.agents.receptionist import DEFAULT_RECEPTIONIST_MODEL
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.rag.retrieval import search_knowledge_base
from backend.services.conversation_service import get_conversation
from backend.services.message_service import save_assistant_message, save_user_message

logger = get_logger(__name__)

DEFAULT_WHISPER_MODEL = WhisperModelSize.BASE
DEFAULT_PIPER_VOICE = "en_US-lessac-medium"
DEFAULT_AUDIO_IN_SAMPLE_RATE = 16000
DEFAULT_AUDIO_OUT_SAMPLE_RATE = 22050


def resolve_compute_device() -> Tuple[str, str, bool]:
    """Select optimal Whisper device/compute_type and Piper CUDA flag for local hardware."""
    if torch.cuda.is_available():
        return "cuda", "float16", True
    return "cpu", "int8", False


class RawAudioFrameSerializer(FrameSerializer):
    """Lightweight serializer bridging browser raw PCM16 WebSocket audio and Pipecat frames."""

    def __init__(
        self,
        sample_rate: int = DEFAULT_AUDIO_IN_SAMPLE_RATE,
        num_channels: int = 1,
        params: Optional[FrameSerializer.InputParams] = None,
    ) -> None:
        super().__init__(params)
        self._sample_rate = sample_rate
        self._num_channels = num_channels

    async def serialize(self, frame: Frame) -> str | bytes | None:
        """Convert outgoing Pipecat audio/text frames into WebSocket bytes or JSON text."""
        if isinstance(frame, OutputAudioRawFrame):
            return frame.audio
        if isinstance(frame, TranscriptionFrame):
            return json.dumps({"type": "user_transcript", "text": frame.text})
        if isinstance(frame, TextFrame):
            return json.dumps({"type": "assistant_text", "text": frame.text})
        return None

    async def deserialize(self, data: str | bytes) -> Frame | None:
        """Convert incoming browser WebSocket binary PCM16 chunks or JSON text into Pipecat frames."""
        if isinstance(data, (bytes, bytearray)) and data:
            # 16kHz PCM16 mono requires 2 bytes per sample; trim any incomplete trailing byte
            usable_len = len(data) - (len(data) % (2 * self._num_channels))
            if usable_len <= 0:
                return None
            return InputAudioRawFrame(
                audio=bytes(data[:usable_len]),
                sample_rate=self._sample_rate,
                num_channels=self._num_channels,
            )
        if isinstance(data, str) and data.strip():
            try:
                payload = json.loads(data)
                if isinstance(payload, dict) and payload.get("type") == "text":
                    text = str(payload.get("text", "")).strip()
                    if text:
                        return TranscriptionFrame(text=text, user_id="caller", timestamp="")
            except json.JSONDecodeError:
                return TranscriptionFrame(text=data.strip(), user_id="caller", timestamp="")
        return None


def build_voice_system_prompt(rag_query: str = "services pricing hours policies") -> str:
    """Build a spoken-conversation receptionist system prompt grounded in Phase 3 RAG context."""
    contexts: List[str] = []
    try:
        rag_result = search_knowledge_base(rag_query, top_k=4)
        contexts = list(rag_result.get("contexts", []))
    except Exception as exc:
        logger.warning(f"Voice RAG lookup skipped due to retrieval error: {exc}")

    context_block = (
        "\n\n---\n\n".join(ctx.strip() for ctx in contexts if ctx.strip())
        if contexts
        else "No specific business knowledge base context retrieved."
    )

    return (
        "You are the official AI Voice Receptionist for AI Employee. "
        "Speak naturally, warmly, and concisely in 1-3 short sentences suitable for real-time voice audio. "
        "Avoid markdown formatting, bullet symbols, asterisks, or emojis since your output is spoken aloud. "
        "Base all factual answers about pricing, business hours, policies, and services strictly on the "
        "retrieved business knowledge context below.\n\n"
        "<RETRIEVED_KNOWLEDGE_CONTEXT>\n"
        f"{context_block}\n"
        "</RETRIEVED_KNOWLEDGE_CONTEXT>"
    )


def _extract_transcript_turns(context: LLMContext) -> List[Tuple[str, str]]:
    """Extract ordered (role, content) turns from the Pipecat LLMContext."""
    turns: List[Tuple[str, str]] = []
    for raw_msg in context.get_messages():
        if not isinstance(raw_msg, dict):
            continue
        role = str(raw_msg.get("role", "")).lower()
        if role not in {"user", "assistant"}:
            continue
        content = raw_msg.get("content", "")
        if isinstance(content, list):
            text_parts = [
                str(part.get("text", ""))
                for part in content
                if isinstance(part, dict) and part.get("text")
            ]
            content_str = " ".join(text_parts).strip()
        else:
            content_str = str(content or "").strip()

        if content_str:
            turns.append((role, content_str))
    return turns


def _persist_voice_transcript(
    conversation_id: str,
    turns: List[Tuple[str, str]],
) -> int:
    """Persist completed voice call transcript turns to SQLite outside the audio event loop."""
    if not turns:
        return 0

    try:
        conv_uuid = UUID(str(conversation_id))
    except ValueError:
        logger.warning(f"Skipping DB transcript persistence for non-UUID conversation_id '{conversation_id}'.")
        return 0

    saved_count = 0
    session = db_connection.SessionLocal()
    try:
        conversation = get_conversation(session, conv_uuid)
        if not conversation:
            logger.warning(f"Conversation '{conversation_id}' not found; skipping voice transcript persistence.")
            return 0

        for role, content in turns:
            if role == "user":
                save_user_message(session, conv_uuid, content)
            else:
                save_assistant_message(session, conv_uuid, content)
            saved_count += 1
        return saved_count
    except Exception as exc:
        logger.error(f"Failed to persist voice transcript for '{conversation_id}': {exc}", exc_info=True)
        session.rollback()
        return 0
    finally:
        session.close()


class VoiceReceptionistAgent:
    """Orchestrates a local zero-cost Pipecat voice pipeline (Silero + Whisper + Gemini + Piper)."""

    def __init__(
        self,
        *,
        whisper_model: WhisperModelSize | str = DEFAULT_WHISPER_MODEL,
        piper_voice: str = DEFAULT_PIPER_VOICE,
        llm_model: str = DEFAULT_RECEPTIONIST_MODEL,
        vad_factory: Optional[Callable[[], Any]] = None,
        stt_factory: Optional[Callable[[], Any]] = None,
        llm_factory: Optional[Callable[[str], Any]] = None,
        tts_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.whisper_model = whisper_model
        self.piper_voice = piper_voice
        self.llm_model = llm_model
        self._vad_factory = vad_factory
        self._stt_factory = stt_factory
        self._llm_factory = llm_factory
        self._tts_factory = tts_factory

    def _create_vad(self) -> Any:
        if self._vad_factory is not None:
            return self._vad_factory()
        return SileroVADAnalyzer(params=VADParams(stop_secs=0.4))

    def _create_stt(self) -> Any:
        if self._stt_factory is not None:
            return self._stt_factory()
        device, compute_type, _ = resolve_compute_device()
        return WhisperSTTService(
            device=device,
            compute_type=compute_type,
            settings=WhisperSTTService.Settings(
                model=self.whisper_model.value if hasattr(self.whisper_model, "value") else str(self.whisper_model),
                language=Language.EN,
            ),
        )

    @staticmethod
    def _is_ollama_reachable(base_url: str, timeout_secs: float = 1.0) -> bool:
        """Probe the local Ollama OpenAI-compatible endpoint without blocking long."""
        probe_url = f"{base_url.rstrip('/')}/models"
        try:
            resp = httpx.get(probe_url, timeout=timeout_secs)
            return resp.status_code < 500
        except Exception as exc:
            logger.warning(f"Local Ollama health probe failed at '{probe_url}': {exc}")
            return False

    def _create_llm(self, system_prompt: str) -> Any:
        if self._llm_factory is not None:
            return self._llm_factory(system_prompt)

        settings = get_settings()
        provider = getattr(settings, "llm_provider", "ollama").strip().lower()
        ollama_base_url = getattr(settings, "ollama_base_url", "http://localhost:11434/v1")
        groq_key = (getattr(settings, "groq_api_key", None) or "").strip()
        groq_model = getattr(settings, "groq_model", "llama-3.1-8b-instant")
        gemini_key = (settings.gemini_api_key or "").strip()
        has_valid_gemini_key = bool(
            gemini_key and gemini_key not in {"your-gemini-api-key-here", "placeholder"}
        )

        if provider == "gemini":
            api_key = gemini_key or "placeholder-gemini-api-key"
            return GoogleLLMService(
                api_key=api_key,
                settings=GoogleLLMService.Settings(
                    model=self.llm_model,
                    system_instruction=system_prompt,
                ),
            )

        groq_settings_kwargs: Dict[str, Any] = {
            "model": groq_model,
            "system_instruction": system_prompt,
        }
        if groq_model.startswith("openai/gpt-oss"):
            groq_settings_kwargs["reasoning_effort"] = "low"

        if provider == "groq":
            api_key = groq_key or "placeholder-groq-api-key"
            return GroqLLMService(
                api_key=api_key,
                settings=GroqLLMService.Settings(**groq_settings_kwargs),
            )

        # Default: Local Ollama (with graceful cloud fallback if offline)
        if self._is_ollama_reachable(ollama_base_url):
            return OLLamaLLMService(
                api_key="ollama",
                base_url=ollama_base_url,
                settings=OLLamaLLMService.Settings(
                    model=getattr(settings, "ollama_model", "gemma"),
                    system_instruction=system_prompt,
                ),
            )
        if groq_key:
            logger.warning("Ollama server is offline/unreachable; falling back seamlessly to Groq.")
            return GroqLLMService(
                api_key=groq_key,
                settings=GroqLLMService.Settings(**groq_settings_kwargs),
            )
        if has_valid_gemini_key:
            logger.warning(
                "Ollama server is offline/unreachable; falling back seamlessly to Gemini."
            )
            return GoogleLLMService(
                api_key=gemini_key,
                settings=GoogleLLMService.Settings(
                    model=self.llm_model,
                    system_instruction=system_prompt,
                ),
            )
        logger.error(
            f"Ollama server unreachable at '{ollama_base_url}' and no fallback GROQ_API_KEY/GEMINI_API_KEY configured."
        )
        return OLLamaLLMService(
            api_key="ollama",
            base_url=ollama_base_url,
            settings=OLLamaLLMService.Settings(
                model=getattr(settings, "ollama_model", "gemma"),
                system_instruction=system_prompt,
            ),
        )

    def _create_tts(self) -> Any:
        if self._tts_factory is not None:
            return self._tts_factory()
        _, _, use_cuda = resolve_compute_device()
        return PiperTTSService(
            use_cuda=use_cuda,
            settings=PiperTTSService.Settings(
                voice=self.piper_voice,
            ),
        )

    def build_transport(self, websocket: Any) -> FastAPIWebsocketTransport:
        """Create a FastAPIWebsocketTransport configured for browser bidirectional audio."""
        settings = get_settings()
        return FastAPIWebsocketTransport(
            websocket=websocket,
            params=FastAPIWebsocketParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                audio_in_sample_rate=DEFAULT_AUDIO_IN_SAMPLE_RATE,
                audio_out_sample_rate=DEFAULT_AUDIO_OUT_SAMPLE_RATE,
                add_wav_header=False,
                allowed_origins=list(settings.allowed_origins),
                serializer=RawAudioFrameSerializer(
                    sample_rate=DEFAULT_AUDIO_IN_SAMPLE_RATE,
                    num_channels=1,
                ),
            ),
        )

    async def build_pipeline_task(
        self,
        transport: BaseTransport,
        conversation_id: str,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> Tuple[PipelineTask, LLMContext, Callable[[], asyncio.Future | Any]]:
        """Assemble Transport -> VAD -> STT -> LLM -> TTS -> Transport Pipecat PipelineTask.

        Model initialization runs off the event loop via ``asyncio.to_thread`` so local
        Whisper/Piper model loads never block incoming WebSocket handshakes.
        """
        system_prompt = await asyncio.to_thread(build_voice_system_prompt)
        vad, stt, tts, llm = await asyncio.gather(
            asyncio.to_thread(self._create_vad),
            asyncio.to_thread(self._create_stt),
            asyncio.to_thread(self._create_tts),
            asyncio.to_thread(self._create_llm, system_prompt),
        )
        # Re-bind live RAG system prompt once both RAG retrieval and reachability probe finish
        if hasattr(llm, "_settings") and hasattr(llm._settings, "system_instruction"):
            llm._settings.system_instruction = system_prompt

        context = LLMContext(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                }
            ]
        )
        user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
            context,
            user_params=LLMUserAggregatorParams(vad_analyzer=vad),
        )

        pipeline = Pipeline(
            [
                transport.input(),
                stt,
                user_aggregator,
                llm,
                tts,
                transport.output(),
                assistant_aggregator,
            ]
        )

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                audio_in_sample_rate=DEFAULT_AUDIO_IN_SAMPLE_RATE,
                audio_out_sample_rate=DEFAULT_AUDIO_OUT_SAMPLE_RATE,
                enable_metrics=True,
                enable_usage_metrics=False,
            ),
        )

        finalized = False

        async def finalize_call() -> None:
            nonlocal finalized
            if finalized:
                return
            finalized = True

            turns = _extract_transcript_turns(context)
            if turns:
                await asyncio.to_thread(_persist_voice_transcript, conversation_id, turns)
                analyst = AIBusinessAnalyst()
                if background_tasks is not None:
                    background_tasks.add_task(analyst.analyze_conversation, str(conversation_id))
                else:
                    await asyncio.to_thread(analyst.analyze_conversation, str(conversation_id))

        @transport.event_handler("on_client_connected")
        async def on_client_connected(_transport: Any, _client: Any) -> None:
            logger.info(f"Voice client connected for conversation '{conversation_id}'")
            try:
                context.add_message(
                    {
                        "role": "user",
                        "content": "Hello! Please greet me warmly and ask how you can help me today.",
                    }
                )
                await task.queue_frames([LLMRunFrame()])
            except Exception as exc:
                logger.error(
                    f"Failed queuing initial voice greeting for '{conversation_id}': {exc}",
                    exc_info=True,
                )

        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(_transport: Any, _client: Any) -> None:
            logger.info(f"Voice client disconnected for conversation '{conversation_id}'")
            try:
                await task.cancel()
            except Exception as exc:
                logger.debug(f"Ignored task.cancel error during disconnect for '{conversation_id}': {exc}")
            await finalize_call()

        @task.event_handler("on_pipeline_finished")
        async def on_pipeline_finished(_task: Any, _frame: Any) -> None:
            await finalize_call()

        return task, context, finalize_call

    async def run_voice_session(
        self,
        websocket: Any,
        conversation_id: str,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> None:
        """Run the end-to-end Pipecat voice session for an accepted WebSocket connection."""
        transport = self.build_transport(websocket)
        task, _context, finalize_call = await self.build_pipeline_task(
            transport=transport,
            conversation_id=conversation_id,
            background_tasks=background_tasks,
        )
        runner = PipelineRunner(handle_sigint=False)
        try:
            await runner.run(task)
        except WebSocketDisconnect:
            logger.info(f"Voice WebSocket disconnected abruptly for conversation '{conversation_id}'")
        except Exception as exc:
            logger.error(
                f"Voice pipeline error for conversation '{conversation_id}': {exc}",
                exc_info=True,
            )
        finally:
            try:
                await task.cancel()
            except Exception as exc:
                logger.debug(f"Ignored task.cancel cleanup error for '{conversation_id}': {exc}")
            await finalize_call()
