"""
Embeddings service package.

Provides portable embedding generation with multiple provider support.
"""

from app.services.embeddings.base import EmbeddingProvider
from app.services.embeddings.factory import (
    get_embedding_provider,
    get_embedding_dimensions,
    embed,
    embed_batch,
)
from app.services.embeddings.gemini_provider import GeminiEmbedding

__all__ = [
    "EmbeddingProvider",
    "GeminiEmbedding",
    "get_embedding_provider",
    "get_embedding_dimensions",
    "embed",
    "embed_batch",
]
