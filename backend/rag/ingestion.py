"""RAG ingestion service for loading, chunking, and indexing business documents."""

from pathlib import Path
from typing import Any, Dict, Optional

from llama_index.core import Settings, SimpleDirectoryReader, VectorStoreIndex
from llama_index.core.llms import MockLLM
from llama_index.core.node_parser import SentenceSplitter

from backend.core.logging import get_logger
from backend.rag.embeddings import configure_local_tokenizer, get_embedding_model
from backend.rag.vector_store import (
    DEFAULT_COLLECTION_NAME,
    get_vector_store_and_context,
)

logger = get_logger(__name__)

DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"


def ingest_business_documents(
    data_dir: Optional[Path | str] = None,
    persist_dir: Optional[Path | str] = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> Dict[str, Any]:
    """Load business documents, split into semantic chunks, and build/update the VectorStoreIndex."""
    target_data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    if not target_data_dir.exists():
        raise FileNotFoundError(f"RAG data directory not found: {target_data_dir}")

    # Configure local tokenizer, embedding model, and mock LLM so no OpenAI key is required
    tokenizer = configure_local_tokenizer()
    embed_model = get_embedding_model()
    Settings.embed_model = embed_model
    Settings.llm = MockLLM()

    logger.info(f"Loading business documents from '{target_data_dir}'...")
    reader = SimpleDirectoryReader(input_dir=str(target_data_dir))
    documents = reader.load_data()

    splitter = SentenceSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        tokenizer=tokenizer,
    )
    nodes = splitter.get_nodes_from_documents(documents)

    vector_store, storage_context, resolved_persist_dir = get_vector_store_and_context(
        persist_dir=persist_dir,
        collection_name=collection_name,
        reset=True,
    )

    index = VectorStoreIndex(
        nodes,
        storage_context=storage_context,
        embed_model=embed_model,
    )
    index.set_index_id(collection_name)

    # Persist storage context if using file-backed fallback store
    if not vector_store.__class__.__name__.startswith("Chroma"):
        index.storage_context.persist(persist_dir=str(resolved_persist_dir))

    logger.info(
        f"Ingested {len(documents)} document(s) ({len(nodes)} chunk(s)) "
        f"into collection '{collection_name}'."
    )
    return {
        "status": "success",
        "documents_loaded": len(documents),
        "chunks_indexed": len(nodes),
        "collection_name": collection_name,
    }
