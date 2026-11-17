---
name: vocode-telephony
description: Use when implementing phone calling, telephony integrations (Twilio, Vonage), inbound/outbound phone calls, or bidirectional audio streaming for automated customer calls.
---

# Vocode Telephony & Phone Agents

## Overview
A reference for connecting AI voice agents to real phone lines (Twilio, Vonage, SIP) and orchestrating inbound/outbound phone calls, based on [vocodedev/vocode-api-python](../../references/repositories/vocode-api-python/README.md).

## When to Use
- Connecting the AI Receptionist to phone numbers
- Handling inbound customer phone calls via Twilio/Vonage webhooks
- Executing automated outbound follow-up calls or appointment confirmations
- Managing telephony audio streaming, transcribers, and synthesizers
- Executing in-call actions (e.g. transfer call, book calendar slot, send SMS)

## Telephony Architecture

```text
Phone Network (PSTN / Mobile)
            │
            ▼
┌────────────────────────┐
│  Telephony Provider    │ (Twilio / Vonage)
└───────────┬────────────┘
            │ Bidirectional Audio WebSocket / Webhook
            ▼
┌────────────────────────┐
│  FastAPI Webhook /     │ ◄── Handles incoming call events & returns TwiML
│  Vocode Call Server    │
└───────────┬────────────┘
            ▼
┌────────────────────────┐
│ Transcriber (STT)      │ (Deepgram, Google, AssemblyAI)
└───────────┬────────────┘
            ▼
┌────────────────────────┐
│ Agent Core (LLM)       │ (System Prompt, State, Actions)
└───────────┬────────────┘
            ▼
┌────────────────────────┐
│ Synthesizer (TTS)      │ (ElevenLabs, Azure, Rime, Cartesia)
└───────────┬────────────┘
            ▼
Telephony Audio Stream (8kHz Mu-law) back to caller
```

## Quick Implementation Recipe

### 1. Programmatic Outbound Call
```python
from vocode.client import AsyncVocode

async def make_appointment_reminder_call(to_phone: str, customer_name: str, appointment_time: str):
    client = AsyncVocode(token="VOCODE_API_KEY")
    
    call = await client.calls.create_call(
        to_number=to_phone,
        from_number="+1234567890",
        agent={
            "prompt": {
                "content": f"""
                You are calling on behalf of the business to confirm {customer_name}'s appointment 
                scheduled for {appointment_time}. 
                Be polite and brief. Ask if they can make it or need to reschedule.
                """
            },
            "initial_message": f"Hello {customer_name}, this is AI Employee calling to confirm your appointment.",
            "actions": [
                {"type": "action_transfer_call", "config": {"transfer_phone_number": "+1987654321"}}
            ]
        }
    )
    return call.id
```

### 2. Inbound Webhook Handler in FastAPI
```python
from fastapi import APIRouter, Request, Response
from twilio.twiml.voice_response import VoiceResponse, Connect

router = APIRouter(prefix="/telephony", tags=["Telephony"])

@router.post("/twilio/inbound")
async def handle_inbound_call(request: Request):
    """Answers inbound phone calls and connects them to the real-time agent stream."""
    vr = VoiceResponse()
    connect = Connect()
    connect.stream(url="wss://your-domain.com/telephony/audio-stream")
    vr.append(connect)
    return Response(content=str(vr), media_type="application/xml")
```

## Telephony Best Practices
- **Audio Format Matching**: Standard telephony uses 8,000Hz or 16,000Hz $\mu$-law (PCMU) audio. Ensure transcribers and synthesizers are set to 8kHz/16kHz to avoid transcoding latency.
- **Warm Handoff / Transfer**: Always configure a fallback phone transfer action (`action_transfer_call`) so customers can be transferred to a live human when requested.
- **Answering Machine Detection (AMD)**: For outbound campaigns, enable AMD so the agent waits for a human "hello" instead of talking over voicemail greetings.

## Anti-Patterns & Common Mistakes
- **Exposing Twilio Webhooks Without Validation**: Always validate the `X-Twilio-Signature` header to prevent unauthorized spoofed requests.
- **Long Pauses**: Telephony users expect answers within 1.0 - 1.5 seconds. Optimize STT endpointing and TTS streaming.

## Local Repository Reference
The full SDK source code, types, and endpoint references are located at:
`references/repositories/vocode-api-python/`
- [README.md](../../references/repositories/vocode-api-python/README.md)
- [reference.md](../../references/repositories/vocode-api-python/reference.md)
- [SDK Source](../../references/repositories/vocode-api-python/src/vocode/)
