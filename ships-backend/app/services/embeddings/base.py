"""
Embedding provider abstraction layer.

Enables portable embeddings - switch providers without data migration.
Currently supports Gemini, extensible to OpenAI and others.
"""

from abc import ABC, abstractmethod
from typing import Optional
import logging

logger = logging.getLogger("ships.embeddings")


class EmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.
    
    All providers must implement embed() and embed_batch().
    Dimension is provider-specific and must be declared.
    """
    
    # Subclasses must define this
    DIMENSIONS: int = 0
    NAME: str = "base"
    
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """
        Generate embedding vector for a single text.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        pass
    
    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of input texts
            
        Returns:
            List of embedding vectors
        """
        pass
    
    def truncate_text(self, text: str, max_tokens: int = 8000) -> str:
        """
        Truncate text to fit within token limits.
        
        Rough estimate: 1 token ~= 4 characters.
        """
        max_chars = max_tokens * 4
        if len(text) > max_chars:
            logger.debug(f"Truncating text from {len(text)} to {max_chars} chars")
            return text[:max_chars]
        return text
