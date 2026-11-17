"""Integration and unit tests for Phase 3 RAG pipeline (Ingestion, Retrieval, and API)."""

from pathlib import Path
from fastapi.testclient import TestClient

from backend.api.routes.knowledge import get_rag_persist_dir
from backend.rag.ingestion import ingest_business_documents
from backend.rag.retrieval import search_knowledge_base


def test_rag_service_ingest_and_search_directly(tmp_path: Path):
    """Test ingest_business_documents and search_knowledge_base services directly."""
    persist_dir = tmp_path / "chroma_test_service"

    ingest_result = ingest_business_documents(persist_dir=persist_dir)
    assert ingest_result["status"] == "success"
    assert ingest_result["documents_loaded"] >= 1
    assert ingest_result["chunks_indexed"] >= 1

    search_result = search_knowledge_base(
        query="What is the price of an Initial Business Consultation and what are the store hours?",
        top_k=3,
        persist_dir=persist_dir,
    )
    assert isinstance(search_result, dict)
    assert "answer" in search_result
    assert "contexts" in search_result
    assert isinstance(search_result["answer"], str)
    assert len(search_result["answer"].strip()) > 0
    assert isinstance(search_result["contexts"], list)
    assert len(search_result["contexts"]) >= 1

    combined_context = " ".join(search_result["contexts"]).lower()
    assert "$50" in combined_context or "9:00 am" in combined_context


def test_knowledge_api_ingest_and_search_endpoints(client: TestClient, tmp_path: Path):
    """Test POST /api/v1/knowledge/ingest and POST /api/v1/knowledge/search endpoints."""
    persist_dir = tmp_path / "chroma_test_api"
    client.app.dependency_overrides[get_rag_persist_dir] = lambda: persist_dir

    try:
        # 1. Trigger /api/v1/knowledge/ingest
        ingest_resp = client.post("/api/v1/knowledge/ingest")
        assert ingest_resp.status_code in (200, 201)
        ingest_data = ingest_resp.json()
        assert ingest_data["status"] == "success"
        assert ingest_data["documents_loaded"] >= 1
        assert ingest_data["chunks_indexed"] >= 1

        # 2. Trigger /api/v1/knowledge/search with a query about business_faq.md
        search_resp = client.post(
            "/api/v1/knowledge/search",
            json={
                "query": "What is the subscription refund policy and Saturday store hours?",
                "top_k": 3,
            },
        )
        assert search_resp.status_code == 200
        search_data = search_resp.json()

        assert "answer" in search_data
        assert "contexts" in search_data
        assert isinstance(search_data["answer"], str)
        assert len(search_data["answer"].strip()) > 0
        assert isinstance(search_data["contexts"], list)
        assert len(search_data["contexts"]) >= 1

        combined_contexts = " ".join(search_data["contexts"]).lower()
        assert "14-day" in combined_contexts or "saturday" in combined_contexts

        # 3. Trigger /api/v1/knowledge/ingest a SECOND time (idempotency check) and search again
        second_ingest_resp = client.post("/api/v1/knowledge/ingest")
        assert second_ingest_resp.status_code in (200, 201)

        second_search_resp = client.post(
            "/api/v1/knowledge/search",
            json={
                "query": "What are the store hours and how much does an Initial Business Consultation cost?",
                "top_k": 3,
            },
        )
        assert second_search_resp.status_code == 200
        second_search_data = second_search_resp.json()
        assert len(second_search_data["answer"].strip()) > 0
        assert len(second_search_data["contexts"]) >= 1
    finally:
        client.app.dependency_overrides.pop(get_rag_persist_dir, None)
