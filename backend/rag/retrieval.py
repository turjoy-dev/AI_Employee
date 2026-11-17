"""RAG retrieval service returning synthesized answers and raw contexts for Ragas evaluation."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from llama_index.core import Settings, VectorStoreIndex, load_index_from_storage
from llama_index.core.llms import MockLLM

from backend.core.logging import get_logger
from backend.rag.embeddings import configure_local_tokenizer, get_embedding_model
from backend.rag.ingestion import ingest_business_documents
from backend.rag.vector_store import (
    DEFAULT_COLLECTION_NAME,
    get_vector_store_and_context,
)

logger = get_logger(__name__)


def _load_or_build_index(
    persist_dir: Optional[Path | str] = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> VectorStoreIndex:
    """Load existing VectorStoreIndex or ingest default documents if empty."""
    configure_local_tokenizer()
    embed_model = get_embedding_model()
    Settings.embed_model = embed_model
    Settings.llm = MockLLM()

    vector_store, storage_context, resolved_persist_dir = get_vector_store_and_context(
        persist_dir=persist_dir,
        collection_name=collection_name,
        reset=False,
    )

    if vector_store.__class__.__name__.startswith("Chroma"):
        chroma_coll = getattr(vector_store, "_collection", None)
        if chroma_coll is not None and chroma_coll.count() == 0:
            ingest_business_documents(
                persist_dir=resolved_persist_dir,
                collection_name=collection_name,
            )
            vector_store, storage_context, _ = get_vector_store_and_context(
                persist_dir=resolved_persist_dir,
                collection_name=collection_name,
            )
        return VectorStoreIndex.from_vector_store(
            vector_store=vector_store,
            storage_context=storage_context,
            embed_model=embed_model,
        )

    # Fallback persistent store check
    docstore_file = resolved_persist_dir / "docstore.json"
    if not docstore_file.exists():
        ingest_business_documents(
            persist_dir=resolved_persist_dir,
            collection_name=collection_name,
        )
        _, storage_context, _ = get_vector_store_and_context(
            persist_dir=resolved_persist_dir,
            collection_name=collection_name,
        )

    structs = storage_context.index_store.index_structs()
    if not structs:
        ingest_business_documents(
            persist_dir=resolved_persist_dir,
            collection_name=collection_name,
        )
        _, storage_context, _ = get_vector_store_and_context(
            persist_dir=resolved_persist_dir,
            collection_name=collection_name,
        )
        structs = storage_context.index_store.index_structs()

    target_index_id = collection_name
    available_ids = [s.index_id for s in structs]
    if target_index_id not in available_ids and available_ids:
        target_index_id = available_ids[-1]

    return load_index_from_storage(
        storage_context,
        index_id=target_index_id,
        embed_model=embed_model,
    )


_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "for",
    "from", "how", "i", "in", "is", "it", "much", "of", "on", "or", "the",
    "to", "what", "when", "where", "which", "who", "why", "with", "your",
    "business", "ai", "employee",
}


def _synthesize_grounded_answer(query: str, contexts: List[str]) -> str:
    """Synthesize a concise, grounded answer from the retrieved context chunks matching the query."""
    if not contexts:
        return "No relevant information was found in the business knowledge base."

    query_terms = {
        w for w in re.findall(r"[a-z0-9]+", query.lower())
        if w not in _STOPWORDS and len(w) > 1
    }
    if not query_terms:
        return "\n\n".join(ctx.strip() for ctx in contexts if ctx.strip())

    # Split contexts into markdown sections (by ## heading) and bullet lines
    matched_lines: List[str] = []
    for ctx in contexts:
        current_section_header = ""

        for raw_line in ctx.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("# "):
                continue
            if line.startswith("## "):
                current_section_header = line
                continue

            header_terms = set(re.findall(r"[a-z0-9]+", current_section_header.lower()))
            line_only_terms = set(re.findall(r"[a-z0-9]+", line.lower()))

            # Match if the section header itself matches a query keyword (e.g., "Store & Office Hours")
            # OR if the bullet line itself matches a specific query keyword
            header_match = any(
                qt in header_terms
                or any(ht.startswith(qt[:5]) or qt.startswith(ht[:5]) for ht in header_terms if len(ht) >= 5 and len(qt) >= 5)
                for qt in query_terms
            )
            line_match = any(
                qt in line_only_terms
                or any(lt.startswith(qt[:5]) or qt.startswith(lt[:5]) for lt in line_only_terms if len(lt) >= 5 and len(qt) >= 5)
                for qt in query_terms
            )

            # Avoid matching "24 hours" in cancellation policy when asking for "store hours"
            if not header_match and query_terms.intersection({"store", "office"}) and line_only_terms.intersection({"hours"}) and not line_only_terms.intersection({"store", "office", "consultation", "initial"}):
                line_match = False

            if (header_match or line_match) and line not in matched_lines:
                matched_lines.append(line)

    if matched_lines:
        return "\n".join(matched_lines)

    return "\n\n".join(ctx.strip() for ctx in contexts if ctx.strip())


def search_knowledge_base(
    query: str,
    top_k: int = 3,
    persist_dir: Optional[Path | str] = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> Dict[str, Any]:
    """Query the business knowledge base and return both the final answer and raw retrieved contexts.

    The returned dict structure (`query`, `answer`, `contexts`) is designed for direct
    compatibility with Ragas evaluation metrics (Faithfulness, Answer Relevance, Context Recall).
    """
    index = _load_or_build_index(
        persist_dir=persist_dir,
        collection_name=collection_name,
    )

    retriever = index.as_retriever(similarity_top_k=top_k)
    source_nodes = retriever.retrieve(query)

    contexts: List[str] = [
        node.node.get_content().strip()
        for node in source_nodes
        if node.node.get_content().strip()
    ]
    answer = _synthesize_grounded_answer(query, contexts)

    return {
        "query": query,
        "answer": answer,
        "contexts": contexts,
    }
