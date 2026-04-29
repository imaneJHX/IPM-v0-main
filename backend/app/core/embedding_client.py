"""Embedding abstraction — local sentence-transformers (v0) or OpenAI (v1)."""

from __future__ import annotations

import hashlib
import logging
import math
import re
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Prefix required on the QUERY side when using BGE retrieval models.
# Documents (catalog, pitches) are embedded without a prefix.
_BGE_QUERY_PREFIX = (
    "Represent this sentence for searching relevant passages: "
)
_HASH_EMBED_DIM = 256

# Lazy-loaded model cache for local embeddings
_local_model = None
_local_model_unavailable = False


def _get_local_model():
    """Load the sentence-transformers model lazily to avoid slow imports at startup."""
    global _local_model, _local_model_unavailable
    if _local_model_unavailable:
        return None
    if _local_model is None:
        try:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading local embedding model: %s", settings.embedding_model_local)
            _local_model = SentenceTransformer(settings.embedding_model_local)
        except Exception as exc:
            _local_model_unavailable = True
            logger.warning(
                "Local embedding model unavailable (%s). Falling back to hashed embeddings.",
                exc,
            )
            return None
    return _local_model


def _hashed_embedding(text: str) -> list[float]:
    """Return a deterministic lightweight fallback embedding."""
    vector = [0.0] * _HASH_EMBED_DIM
    tokens = re.findall(r"[a-z0-9]{2,}", text.lower())

    if not tokens:
        vector[0] = 1.0
        return vector

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % _HASH_EMBED_DIM
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        weight = 1.0 + (digest[3] / 255.0)
        vector[index] += sign * weight

    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


async def embed_text_async(text: str, is_query: bool = False) -> list[float]:
    """Generate an embedding vector, offloaded to a thread so it doesn't block the event loop."""
    import asyncio
    return await asyncio.to_thread(embed_text, text, is_query)


def embed_text(text: str, is_query: bool = False) -> list[float]:
    """Generate an embedding vector for a single text string.

    Pass is_query=True when embedding a search query against a BGE model so the
    required retrieval prefix is applied.  Documents (catalog entries, pitches)
    should always use is_query=False (the default).
    """
    if settings.embedding_provider == "local":
        model = _get_local_model()
        if model is None:
            return _hashed_embedding(text)
        query_text = text
        if is_query and "bge" in settings.embedding_model_local.lower():
            query_text = _BGE_QUERY_PREFIX + query_text
        embedding = model.encode(query_text, normalize_embeddings=True)
        return embedding.tolist()
    elif settings.embedding_provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.embeddings.create(
            model=settings.embedding_model_openai,
            input=text,
        )
        return response.data[0].embedding
    else:
        raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embedding vectors for multiple texts in batch."""
    if settings.embedding_provider == "local":
        model = _get_local_model()
        if model is None:
            return [_hashed_embedding(text) for text in texts]
        embeddings = model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()
    elif settings.embedding_provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.embeddings.create(
            model=settings.embedding_model_openai,
            input=texts,
        )
        return [item.embedding for item in response.data]
    else:
        raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")
