"""Thin REST API routes for Knowledge Base ingestion and RAG search."""

import asyncio
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from backend.core.logging import get_logger
from backend.rag.ingestion import ingest_business_documents
from backend.rag.retrieval import search_knowledge_base
from backend.schemas.knowledge import IngestResponse, QueryRequest, QueryResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])


def get_rag_data_dir() -> Optional[Path]:
    """Dependency providing the default knowledge base data directory."""
    return None


def get_rag_persist_dir() -> Optional[Path]:
    """Dependency providing the default ChromaDB persistence directory."""
    return None


DataDirDep = Annotated[Optional[Path], Depends(get_rag_data_dir)]
PersistDirDep = Annotated[Optional[Path], Depends(get_rag_persist_dir)]


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest business documents into the vector store",
)
async def ingest_knowledge(
    data_dir: DataDirDep,
    persist_dir: PersistDirDep,
) -> dict:
    """Load markdown/text documents from backend/rag/data/ and index them in ChromaDB."""
    try:
        return await asyncio.to_thread(
            ingest_business_documents,
            data_dir=data_dir,
            persist_dir=persist_dir,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(f"Knowledge base ingestion failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest business documents.",
        ) from exc


@router.post(
    "/search",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Search the business knowledge base",
)
async def search_knowledge(
    payload: QueryRequest,
    persist_dir: PersistDirDep,
) -> dict:
    """Retrieve relevant business knowledge chunks and synthesize a grounded answer."""
    try:
        return await asyncio.to_thread(
            search_knowledge_base,
            query=payload.query,
            top_k=payload.top_k,
            persist_dir=persist_dir,
        )
    except Exception as exc:
        logger.error(f"Knowledge base search failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search the knowledge base.",
        ) from exc
