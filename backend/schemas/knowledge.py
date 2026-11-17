"""Pydantic v2 schemas for Knowledge Base ingestion and RAG retrieval."""

from typing import List
from pydantic import BaseModel, ConfigDict, Field


class IngestResponse(BaseModel):
    """Schema returned after ingesting business documents into the vector store."""

    model_config = ConfigDict(from_attributes=True)

    status: str = Field(default="success", description="Ingestion operation status")
    documents_loaded: int = Field(..., ge=0, description="Number of source documents read")
    chunks_indexed: int = Field(..., ge=0, description="Number of text chunks indexed in vector store")
    collection_name: str = Field(..., description="Target ChromaDB collection name")


class QueryRequest(BaseModel):
    """Schema for querying the business knowledge base."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Customer or analyst question to search in the knowledge base",
    )
    top_k: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Number of top relevant chunks to retrieve",
    )


class QueryResponse(BaseModel):
    """Schema returned by knowledge base search, structured for Ragas evaluation."""

    model_config = ConfigDict(from_attributes=True)

    query: str = Field(..., description="Original search query")
    answer: str = Field(..., description="Synthesized answer grounded in retrieved contexts")
    contexts: List[str] = Field(
        default_factory=list,
        description="Raw text chunks retrieved from the vector store (for Ragas faithfulness/recall)",
    )
