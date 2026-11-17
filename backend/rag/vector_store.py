"""Persistent ChromaDB vector store setup and LlamaIndex StorageContext integration."""

from pathlib import Path
from typing import Any, Optional, Tuple

from backend.core.logging import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHROMA_PATH = PROJECT_ROOT / "chroma_db"
DEFAULT_COLLECTION_NAME = "business_knowledge"


def get_chroma_client(persist_dir: Optional[Path | str] = None) -> Any:
    """Initialize a persistent ChromaDB client saving to ./chroma_db/."""
    import chromadb

    target_path = Path(persist_dir) if persist_dir else DEFAULT_CHROMA_PATH
    target_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(target_path))


def get_vector_store_and_context(
    persist_dir: Optional[Path | str] = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    reset: bool = False,
) -> Tuple[Any, Any, Path]:
    """Create or load the persistent ChromaVectorStore and LlamaIndex StorageContext.

    If Windows Application Control blocks native Rust/C++ extensions in chromadb,
    falls back cleanly to LlamaIndex's persistent SimpleVectorStore in the same directory.
    """
    from llama_index.core import StorageContext

    target_path = Path(persist_dir) if persist_dir else DEFAULT_CHROMA_PATH
    target_path.mkdir(parents=True, exist_ok=True)

    try:
        from llama_index.vector_stores.chroma import ChromaVectorStore

        chroma_client = get_chroma_client(target_path)
        if reset:
            try:
                chroma_client.delete_collection(name=collection_name)
            except Exception:
                pass
        chroma_collection = chroma_client.get_or_create_collection(name=collection_name)
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        return vector_store, storage_context, target_path
    except Exception as exc:
        logger.warning(
            f"ChromaVectorStore native binding unavailable ({exc}); "
            f"using persistent LlamaIndex SimpleVectorStore at '{target_path}'."
        )
        from llama_index.core.vector_stores import SimpleVectorStore

        docstore_file = target_path / "docstore.json"
        if not reset and docstore_file.exists():
            storage_context = StorageContext.from_defaults(persist_dir=str(target_path))
            vector_store = storage_context.vector_store
        else:
            vector_store = SimpleVectorStore()
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
        return vector_store, storage_context, target_path
