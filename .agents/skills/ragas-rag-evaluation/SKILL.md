---
name: ragas-rag-evaluation
description: Use when measuring and evaluating RAG pipeline quality, retrieval accuracy, context relevance, faithfulness, or generating synthetic test datasets.
---

# Ragas RAG Evaluation Framework

## Overview
A quantitative evaluation framework for measuring Retrieval-Augmented Generation (RAG) quality and preventing AI hallucinations, based on [explodinggradients/ragas](../../references/repositories/ragas/README.md).

## When to Use
- Auditing the accuracy of the AI Receptionist knowledge base
- Measuring if retrieved business knowledge actually answers customer questions
- Detecting hallucinations where the LLM invents non-existent business policies or pricing
- Benchmarking different chunking strategies, embeddings, or retrieval algorithms
- Generating synthetic Q&A test datasets from raw business documents

## Core Metrics

| Metric | What It Measures | Target |
| :--- | :--- | :--- |
| **Faithfulness** | Answers are grounded *only* in retrieved context (0.0 - 1.0; prevents hallucination). | $\ge 0.90$ |
| **Answer Relevance** | Answer directly addresses the customer query without fluff. | $\ge 0.85$ |
| **Context Precision** | Signal-to-noise ratio in retrieved knowledge chunks (top chunks matter most). | $\ge 0.80$ |
| **Context Recall** | Whether all information needed to answer the question was retrieved. | $\ge 0.85$ |
| **Aspect Critique** | Custom checks (e.g. politeness, conciseness, adherence to brand tone). | Pass |

## Quick Implementation Recipe

```python
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevance,
    context_precision,
    context_recall,
)

# Prepare evaluation sample of real customer questions
data_samples = {
    "question": [
        "What are your working hours on Saturdays?",
        "How much does a dental cleaning cost?"
    ],
    "answer": [
        "We are open on Saturdays from 9:00 AM to 3:00 PM.",
        "A standard dental cleaning starts at $80, depending on the examination."
    ],
    "contexts": [
        ["Our clinic is open Monday to Friday 8 AM to 6 PM, and Saturdays 9 AM to 3 PM. Closed on Sundays."],
        ["Dental Services Pricing: Consultation $40, Standard Dental Cleaning starts at $80."]
    ],
    "ground_truth": [
        "Saturdays 9 AM to 3 PM.",
        "Starts at $80."
    ]
}

dataset = Dataset.from_dict(data_samples)

# Run evaluation
score_results = evaluate(
    dataset,
    metrics=[
        faithfulness,
        answer_relevance,
        context_precision,
        context_recall,
    ],
)

print(score_results)
# Output: {'faithfulness': 1.00, 'answer_relevance': 0.94, 'context_precision': 1.00, 'context_recall': 1.00}
```

## Anti-Patterns & Common Mistakes
- **Testing Without Ground Truth**: Always curate a verified gold-standard set of 20-50 real business Q&As to test against before deploying new knowledge base revisions.
- **Ignoring Low Faithfulness**: If faithfulness drops below 0.85, the model is fabricating information. Fix prompt grounding or increase chunk overlap.
- **Over-chunking**: Very small chunks (<100 tokens) break semantic context, severely degrading context recall.

## Local Repository Reference
The full source code, metric algorithms, and evaluation guides are located at:
`references/repositories/ragas/`
- [README.md](../../references/repositories/ragas/README.md)
- [CLAUDE.md](../../references/repositories/ragas/CLAUDE.md)
- [Source Code (`src/ragas`)](../../references/repositories/ragas/src/ragas/)
- [Examples](../../references/repositories/ragas/examples/)
