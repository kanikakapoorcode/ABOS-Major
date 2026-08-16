"""
Embedding utility for the Level-2 memory layer.
Uses LiteLLM's embedding API so we can switch providers via config.
"""

import logging
from typing import List

from litellm import aembedding

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Map LLM providers to their embedding models
EMBEDDING_MODEL_MAP = {
    "gemini": "gemini/text-embedding-004",
    "openai": "openai/text-embedding-3-small",
}

EMBEDDING_DIM = 1536  # Must match Vector(1536) in the feedback model


def _get_embedding_model() -> str:
    """Derive embedding model from ACTIVE_LLM provider prefix."""
    provider = settings.ACTIVE_LLM.split("/")[0].lower()
    return EMBEDDING_MODEL_MAP.get(provider, "openai/text-embedding-3-small")


async def embed_text(text: str) -> List[float]:
    """
    Embed a text string and return a 1536-dim float vector.
    Falls back to a zero vector on failure to avoid crashing the pipeline.
    """
    if not text or not text.strip():
        return [0.0] * EMBEDDING_DIM

    try:
        model = _get_embedding_model()
        response = await aembedding(model=model, input=[text])
        embedding = response.data[0]["embedding"]

        # Pad or truncate to EMBEDDING_DIM if provider returns different size
        if len(embedding) < EMBEDDING_DIM:
            embedding = embedding + [0.0] * (EMBEDDING_DIM - len(embedding))
        elif len(embedding) > EMBEDDING_DIM:
            embedding = embedding[:EMBEDDING_DIM]

        return embedding
    except Exception as e:
        logger.error(f"[Embeddings] Failed to embed text: {e}")
        return [0.0] * EMBEDDING_DIM
