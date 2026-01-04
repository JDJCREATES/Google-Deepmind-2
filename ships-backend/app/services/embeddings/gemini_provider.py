"""
Gemini embedding provider.

Uses Google's text-embedding-004 model for generating embeddings.
768 dimensions, optimized for semantic similarity.
"""

import os
import logging
from typing import Optional
import google.generativeai as genai

from app.services.embeddings.base import EmbeddingProvider

logger = logging.getLogger("ships.embeddings.gemini")

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


class GeminiEmbedding(EmbeddingProvider):
    """
    Gemini-based embedding provider.
    
    Uses text-embedding-004 model with 768 dimensions.
    Suitable for semantic search and similarity matching.
    """
    
    DIMENSIONS = 768
    NAME = "gemini"
    MODEL = "models/text-embedding-004"
    
    def __init__(self):
        """Initialize Gemini embedding provider."""
        if not GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set - embeddings will fail")
    
    async def embed(self, text: str) -> list[float]:
        """
        Generate embedding for single text using Gemini.
        
        Args:
            text: Input text to embed
            
        Returns:
            768-dimensional embedding vector
            
        Raises:
            Exception: If embedding fails
        """
        try:
            truncated = self.truncate_text(text)
            
            result = genai.embed_content(
                model=self.MODEL,
                content=truncated,
                task_type="RETRIEVAL_DOCUMENT"
            )
            
            embedding = result['embedding']
            logger.debug(f"Generated embedding: {len(embedding)} dimensions")
            
            return embedding
            
        except Exception as e:
            logger.error(f"Gemini embedding failed: {e}")
            raise
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.
        
        Note: Gemini's embed_content supports batch via list input.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of 768-dimensional embedding vectors
        """
        try:
            truncated = [self.truncate_text(t) for t in texts]
            
            result = genai.embed_content(
                model=self.MODEL,
                content=truncated,
                task_type="RETRIEVAL_DOCUMENT"
            )
            
            # embed_content returns list of embeddings for list input
            embeddings = result['embedding']
            
            # Handle single vs batch response format
            if texts and isinstance(embeddings[0], float):
                # Single text returned flat list
                return [embeddings]
            
            logger.debug(f"Generated {len(embeddings)} embeddings")
            return embeddings
            
        except Exception as e:
            logger.error(f"Gemini batch embedding failed: {e}")
            raise
    
    async def embed_query(self, query: str) -> list[float]:
        """
        Generate embedding optimized for query/search.
        
        Uses RETRIEVAL_QUERY task type for better search performance.
        """
        try:
            truncated = self.truncate_text(query)
            
            result = genai.embed_content(
                model=self.MODEL,
                content=truncated,
                task_type="RETRIEVAL_QUERY"
            )
            
            return result['embedding']
            
        except Exception as e:
            logger.error(f"Gemini query embedding failed: {e}")
            raise
