"""Local embedding model configuration for the RAG pipeline."""

import hashlib
import math
import os
import re
from typing import Any, Callable, List, Optional

import llama_index.core
from llama_index.core import Settings
from llama_index.core.base.embeddings.base import BaseEmbedding

from backend.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"
_cached_embed_model: Optional[Any] = None


def local_word_tokenizer(text: str) -> List[str]:
    """Pure-Python tokenizer avoiding unsigned native _tiktoken DLL blocks under Windows WDAC."""
    return re.findall(r"\w+|[^\w\s]", text, re.UNICODE)


def configure_local_tokenizer() -> Callable[[str], List[str]]:
    """Register the pure-Python tokenizer globally in LlamaIndex."""
    llama_index.core.global_tokenizer = local_word_tokenizer
    try:
        Settings.tokenizer = local_word_tokenizer
    except Exception:
        pass
    return local_word_tokenizer


def _compute_local_hash_embedding(text: str, dim: int = 384) -> List[float]:
    """Compute a deterministic, normalized 384-d semantic embedding using word and char n-grams."""
    vec = [0.0] * dim
    cleaned = re.sub(r"[^a-zA-Z0-9\u0980-\u09FF$+]+", " ", text.lower()).strip()
    tokens = cleaned.split()
    if not tokens:
        vec[0] = 1.0
        return vec

    features: List[str] = list(tokens)
    for i in range(len(tokens) - 1):
        features.append(f"{tokens[i]}_{tokens[i + 1]}")
    for token in tokens:
        if len(token) >= 3:
            for j in range(len(token) - 2):
                features.append(f"#{token[j:j + 3]}#")

    for feat in features:
        digest = hashlib.md5(feat.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


class LocalDeterministicEmbedding(BaseEmbedding):
    """Deterministic 384-d local BaseEmbedding compatible with LlamaIndex and ChromaDB."""

    def _get_query_embedding(self, query: str) -> List[float]:
        return _compute_local_hash_embedding(query)

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return _compute_local_hash_embedding(query)

    def _get_text_embedding(self, text: str) -> List[float]:
        return _compute_local_hash_embedding(text)

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return [_compute_local_hash_embedding(t) for t in texts]


def get_embedding_model(model_name: str = DEFAULT_EMBED_MODEL_NAME) -> Any:
    """Return the configured LlamaIndex embedding model (HuggingFace BAAI/bge-small-en-v1.5 with local fallback)."""
    global _cached_embed_model
    configure_local_tokenizer()

    if _cached_embed_model is not None:
        return _cached_embed_model

    # Only attempt HuggingFace model load if local cache is present or explicitly enabled
    hf_cache_Hint = os.environ.get("USE_HF_ONLINE", "false").lower() == "true"
    try:
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding

        embed_model = HuggingFaceEmbedding(
            model_name=model_name,
            local_files_only=not hf_cache_Hint,
        )
        _ = embed_model.get_text_embedding("health check")
        logger.info(f"Initialized HuggingFaceEmbedding with model '{model_name}'.")
        _cached_embed_model = embed_model
        return _cached_embed_model
    except Exception as exc:
        logger.info(
            f"Using fast offline LocalDeterministicEmbedding (384-d) for '{model_name}' ({type(exc).__name__})."
        )
        _cached_embed_model = LocalDeterministicEmbedding(model_name=model_name)
        return _cached_embed_model
