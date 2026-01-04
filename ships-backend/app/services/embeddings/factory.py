"""
Embedding provider factory.

Returns the configured embedding provider based on environment settings.
Supports runtime switching between providers.
"""

import os
import logging
from typing import Optional

from app.services.embeddings.base import EmbeddingProvider
from app.services.embeddings.gemini_provider import GeminiEmbedding

logger = logging.getLogger("ships.embeddings")

# Singleton instance
_provider: Optional[EmbeddingProvider] = None


def get_embedding_provider() -> EmbeddingProvider:
    """
    Get the configured embedding provider.
    
    Returns cached instance for efficiency.
    Provider is determined by EMBEDDING_PROVIDER env var.
    
    Returns:
        EmbeddingProvider: Configured provider instance
        
    Raises:
        ValueError: If provider is unknown
    """
    global _provider
    
    if _provider is not None:
        return _provider
    
    provider_name = os.getenv("EMBEDDING_PROVIDER", "gemini").lower()
    
    if provider_name == "gemini":
        _provider = GeminiEmbedding()
        logger.info(f"Using Gemini embeddings ({GeminiEmbedding.DIMENSIONS} dims)")
    # Future providers:
    # elif provider_name == "openai":
    #     from app.services.embeddings.openai_provider import OpenAIEmbedding
    #     _provider = OpenAIEmbedding()
    else:
        raise ValueError(f"Unknown embedding provider: {provider_name}")
    
    return _provider


def get_embedding_dimensions() -> int:
    """
    Get embedding dimensions for current provider.
    
    Useful for setting up vector columns in database.
    """
    return get_embedding_provider().DIMENSIONS


# Convenience function for direct use
async def embed(text: str) -> list[float]:
    """
    Generate embedding for text using configured provider.
    
    Convenience wrapper for common use case.
    """
    provider = get_embedding_provider()
    return await provider.embed(text)


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for multiple texts.
    
    Convenience wrapper for batch operations.
    """
    provider = get_embedding_provider()
    return await provider.embed_batch(texts)
