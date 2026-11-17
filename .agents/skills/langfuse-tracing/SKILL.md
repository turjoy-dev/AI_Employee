---
name: langfuse-tracing
description: Use when adding observability, LLM tracing, prompt management, cost tracking, or evaluation scoring to AI agents and RAG pipelines.
---

# Langfuse Tracing & LLM Observability

## Overview
A complete reference for adding production-grade observability, distributed tracing, prompt management, and analytics to LLM-powered systems, based on [langfuse/langfuse](../../references/repositories/langfuse/README.md).

## When to Use
- Tracing multi-turn receptionist conversations and analyst pipelines
- Tracking latency, token counts, and API costs for Gemini/OpenAI
- Versioning and managing system prompts centrally
- Collecting user feedback and assigning quality/relevance scores
- Debugging unexpected agent responses, tool call errors, or RAG failures

## Core Observability Architecture

```text
User Request
     │
     ▼
┌───────────────────────────────┐
│ Trace: "customer-call-1234"   │
│ ┌───────────────────────────┐ │
│ │ Span: "rag-retrieval"     │ │ ──► Documents retrieved & latency
│ └─────────────┬─────────────┘ │
│               ▼               │
│ ┌───────────────────────────┐ │
│ │ Generation: "llm-response"│ │ ──► Input/Output tokens, cost, model
│ └─────────────┬─────────────┘ │
│               ▼               │
│ ┌───────────────────────────┐ │
│ │ Span: "book-appointment"  │ │ ──► Tool arguments, result, execution time
│ └───────────────────────────┘ │
└───────────────────────────────┘
```

## Quick Implementation Recipe

### 1. Basic Function Tracing with `@observe()`
```python
from langfuse.decorators import observe, langfuse_context
from google import genai

@observe()
async def generate_receptionist_reply(caller_id: str, message: str, context: str) -> str:
    # Tag customer and session context
    langfuse_context.update_current_trace(
        user_id=caller_id,
        session_id=f"session_{caller_id}",
        tags=["receptionist", "inbound"]
    )

    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"Context: {context}\n\nCaller: {message}"
    )

    # Attach token usage for cost analytics
    langfuse_context.update_current_observation(
        input={"message": message, "context": context},
        output=response.text,
        metadata={"model": "gemini-2.5-flash"}
    )
    return response.text
```

### 2. Prompt Management from Langfuse
```python
from langfuse import Langfuse

langfuse = Langfuse()

# Fetch versioned production prompt
prompt = langfuse.get_prompt("receptionist_persona", version=2)
compiled_system_prompt = prompt.compile(business_name="Green Valley Clinic")
```

### 3. Logging Evaluation Scores
```python
# Record qualitative scores for analysis
langfuse.score(
    name="lead_qualification",
    value=1.0,  # 1.0 = Qualified Lead, 0.0 = General Inquiry
    comment="Customer requested pricing and booked an appointment.",
    trace_id=trace_id
)
```

## Anti-Patterns & Common Mistakes
- **Hardcoding API Keys**: Set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_HOST` in `.env`.
- **Blocking Tracing Calls**: Langfuse SDK batches and sends traces asynchronously in background threads. Never wait synchronously on trace flushing during user-facing request cycles.
- **Tracing Sensitive PII Unmasked**: Never log raw credit cards or plain unmasked passwords to trace metadata.

## Local Repository Reference
The full platform source code, SDK packages, and documentation are located at:
`references/repositories/langfuse/`
- [README.md](../../references/repositories/langfuse/README.md)
- [Python SDK Docs & Examples](../../references/repositories/langfuse/packages/)
- [Docker Compose Local Deployment](../../references/repositories/langfuse/docker-compose.yml)
