---
name: livekit-voice-agents
description: Use when building real-time conversational voice agents, WebRTC audio streaming, Voice Activity Detection (VAD), Speech-to-Text (STT), Text-to-Speech (TTS), or turn-taking for AI Receptionist.
---

# LiveKit Voice Agents

## Overview
A comprehensive guide for building ultra-low-latency conversational voice agents with WebRTC, based on [livekit/agents](../../references/repositories/livekit-agents/README.md). Powers the real-time AI Receptionist for bidirectional voice calls.

## When to Use
- Implementing real-time customer voice conversations
- Setting up audio streaming pipelines with WebRTC
- Integrating VAD (Voice Activity Detection), STT, LLM, and TTS
- Managing human-like turn-taking, barge-in, and interruption handling
- Connecting voice sessions to telephony (SIP) or browser audio

## Core Architecture

```text
User Speech (Mic)
      │
      ▼
┌───────────────┐
│ WebRTC Track  │
└───────┬───────┘
        ▼
┌───────────────┐
│  Silero VAD   │ ──► Voice detected / Turn start
└───────┬───────┘
        ▼
┌───────────────┐
│ STT (Deepgram)│ ──► Live Speech-to-Text Stream
└───────┬───────┘
        ▼
┌───────────────┐
│  LLM (Gemini) │ ──► Streaming Token Generation & Tool Calls
└───────┬───────┘
        ▼
┌───────────────┐
│  TTS (Eleven) │ ──► Synthesized Audio Chunks
└───────┬───────┘
        ▼
Audio Playout to User (Barge-in cancels playout on interrupt)
```

## Quick Implementation Recipe

```python
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, llm
from livekit.agents.voice import AgentSession, Agent
from livekit.plugins import deepgram, elevenlabs, openai, silero

async def entrypoint(ctx: JobContext):
    # Connect to WebRTC room and subscribe to audio
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Initialize Voice Pipeline
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-2-general"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=elevenlabs.TTS(),
    )

    # Define Receptionist Agent with Business Persona and Functions
    agent = Agent(
        instructions="""
        You are Sarah, the AI Receptionist for the business.
        - Greet callers warmly in English or Bangla.
        - Answer questions regarding opening hours, services, and pricing.
        - Inquire politely for name, contact details, and requirements.
        - If the caller needs appointment booking, execute the booking tool.
        - If the caller is upset or requests a human, escalate immediately.
        """,
    )

    # Start conversational session
    await session.start(agent=agent, room=ctx.room)
    await session.say("Hello! Thanks for calling. How can I assist you today?")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
```

## Handling Interruption & Turn Detection
- **Silero VAD**: Listens continuously for speech onset. If speech occurs while TTS is outputting audio, `AgentSession` halts the TTS stream instantly (**Barge-in**).
- **End-of-Turn Delay**: Configure `min_endpointing_delay` (typically 400ms-600ms) to ensure natural speech pauses don't trigger premature agent interruption.

## Multilingual Support (English & Bangla)
- Configure STT language detection or bilingual models (`deepgram.STT(language="bn")` or `"en"`).
- Instruct the LLM system prompt to detect language dynamically and match the caller's language.

## Anti-Patterns & Common Mistakes
- **High Audio Latency**: Never use standard HTTP REST TTS endpoints inside live WebRTC loops. Always use streaming WebSocket-based TTS (`Cartesia` or `ElevenLabs Streaming`).
- **Missing Barge-in**: Agents that talk over customers frustrate callers. Always couple VAD with playback cancellation.
- **Blocking inside async job**: Never execute synchronous CPU or blocking file tasks inside the voice loop; use async worker tasks.

## Local Repository Reference
The full source code, plugins, and examples are located at:
`references/repositories/livekit-agents/`
- [README.md](../../references/repositories/livekit-agents/README.md)
- [AGENTS.md](../../references/repositories/livekit-agents/AGENTS.md)
- [Voice Agents Directory](../../references/repositories/livekit-agents/livekit-agents/livekit/agents/voice/)
- [Examples](../../references/repositories/livekit-agents/examples/)
