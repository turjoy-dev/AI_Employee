---
name: llamaindex-rag
description: Use when building document ingestion, knowledge base indexing, vector store retrieval, or query engines for business documents, FAQs, and pricing.
---

# LlamaIndex RAG & Knowledge Base

## Overview
A comprehensive guide for building the business knowledge ingestion, semantic indexing, and retrieval pipeline for AI Employee, based on [run-llama/llama_index](../../references/repositories/llama-index/README.md).

## When to Use
- Ingesting documents from `knowledge_base/` (PDFs, Markdown, text files, FAQs)
- Chunking business policies and price lists into semantic nodes
- Indexing text into vector stores (Chroma, Qdrant, Faiss, SQLite)
- Retrieving relevant context for the AI Receptionist and Business Analyst
- Building query engines with metadata filters and conversational memory

## RAG Architecture for AI Employee

```text
knowledge_base/ (PDF, MD, TXT, DOCX)
          │
          ▼
┌────────────────────────┐
│ SimpleDirectoryReader  │ ──► Reads raw business documents
└───────────┬────────────┘
            ▼
┌────────────────────────┐
│ SentenceSplitter /     │ ──► Chunk size: 512, Overlap: 50
│ SemanticSplitter       │
└───────────┬────────────┘
            ▼
┌────────────────────────┐
│ Embeddings Model       │ ──► Local (bge-small) or Gemini text-embedding-004
└───────────┬────────────┘
            ▼
┌────────────────────────┐
│ VectorStoreIndex       │ ──► Local vector index on disk
└───────────┬────────────┘
            │
      Query │ ◄── Customer asks: "What are your cancellation policies?"
            ▼
┌────────────────────────┐
│ VectorIndexRetriever   │ ──► Top-K (k=3) similarity search
└───────────┬────────────┘
            ▼
┌────────────────────────┐
│ Response Synthesizer   │ ──► Grounded response to Receptionist / Analyst
└────────────────────────┘
```

## Quick Implementation Recipe

### 1. Ingestion and Indexing
```python
from pathlib import Path
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext, load_index_from_storage
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.llms.gemini import Gemini

STORAGE_DIR = "./storage"

def build_or_load_knowledge_base(data_dir: str = "./knowledge_base"):
    parser = SentenceSplitter(chunk_size=512, chunk_overlap=50)
    
    if Path(STORAGE_DIR).exists():
        # Load persisted index from disk
        storage_context = StorageContext.from_defaults(persist_dir=STORAGE_DIR)
        return load_index_from_storage(storage_context)
    
    # Ingest business documents
    documents = SimpleDirectoryReader(data_dir).load_data()
    nodes = parser.get_nodes_from_documents(documents)
    
    # Build vector index
    index = VectorStoreIndex(nodes)
    index.storage_context.persist(persist_dir=STORAGE_DIR)
    return index
```

### 2. Query Engine for Receptionist Context Retrieval
```python
def query_business_knowledge(index, user_query: str) -> str:
    query_engine = index.as_query_engine(
        similarity_top_k=3,
        response_mode="compact"
    )
    response = query_engine.query(user_query)
    return str(response)
```

## Best Practices
- **Chunk Size Tuning**: For business FAQs and price lists, 256-512 token chunks with 50-token overlap preserve specific pricing facts without losing context.
- **Metadata Tagging**: Tag documents with category metadata (e.g. `category: pricing`, `category: hours`, `category: policies`) to enable targeted retrieval filtering.
- **Local Persistence**: Always persist the vector index to disk so the application doesn't re-index on every server restart.

## Anti-Patterns & Common Mistakes
- **Re-indexing on Every Request**: Never re-run `VectorStoreIndex.from_documents` inside an API route. Build once on startup or via a dedicated ingestion worker.
- **No Overlap in Chunking**: Chunking with 0 overlap splits sentences and definitions across boundaries, breaking context.

## Local Repository Reference
The full framework source code, integrations, and guides are located at:
`references/repositories/llama-index/`
- [README.md](../../references/repositories/llama-index/README.md)
- [Core Package (`llama-index-core`)](../../references/repositories/llama-index/llama-index-core/)
- [Integrations (`llama-index-integrations`)](../../references/repositories/llama-index/llama-index-integrations/)
