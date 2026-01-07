"""
Gemini embedding provider.

Uses Google's text-embedding-004 model for generating embeddings.
768 dimensions, optimized for semantic similarity.

Updated to use google.genai (new SDK) instead of deprecated google.generativeai.
"""

import os
import logging
from typing import Optional

# Use new SDK (google.genai) instead of deprecated google.generativeai
try:
    from google import genai
    from google.genai import types
    NEW_SDK_AVAILABLE = True
except ImportError:
    # Fallback to deprecated SDK if new one not installed
    import google.generativeai as genai_legacy
    NEW_SDK_AVAILABLE = False

from app.services.embeddings.base import EmbeddingProvider

logger = logging.getLogger("ships.embeddings.gemini")

# Get API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

# Initialize client based on available SDK
if NEW_SDK_AVAILABLE and GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)
elif not NEW_SDK_AVAILABLE and GEMINI_API_KEY:
    genai_legacy.configure(api_key=GEMINI_API_KEY)
    client = None


class GeminiEmbedding(EmbeddingProvider):
    """
    Gemini-based embedding provider.
    
    Uses text-embedding-004 model with 768 dimensions.
    Suitable for semantic search and similarity matching.
    """
    
    DIMENSIONS = 768
    NAME = "gemini"
    MODEL = "text-embedding-004"
    
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
            
            if NEW_SDK_AVAILABLE:
                # New SDK API
                result = client.models.embed_content(
                    model=self.MODEL,
                    contents=truncated,
                    config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
                )
                embedding = result.embeddings[0].values
            else:
                # Legacy SDK API
                result = genai_legacy.embed_content(
                    model=f"models/{self.MODEL}",
                    content=truncated,
                    task_type="RETRIEVAL_DOCUMENT"
                )
                embedding = result['embedding']
            
            logger.debug(f"Generated embedding: {len(embedding)} dimensions")
            return list(embedding)
            
        except Exception as e:
            logger.error(f"Gemini embedding failed: {e}")
            raise
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of 768-dimensional embedding vectors
        """
        try:
            truncated = [self.truncate_text(t) for t in texts]
            
            if NEW_SDK_AVAILABLE:
                # New SDK API
                result = client.models.embed_content(
                    model=self.MODEL,
                    contents=truncated,
                    config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
                )
                embeddings = [list(e.values) for e in result.embeddings]
            else:
                # Legacy SDK API
                result = genai_legacy.embed_content(
                    model=f"models/{self.MODEL}",
                    content=truncated,
                    task_type="RETRIEVAL_DOCUMENT"
                )
                embeddings = result['embedding']
                # Handle single vs batch response format
                if truncated and isinstance(embeddings[0], float):
                    embeddings = [embeddings]
            
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
            
            if NEW_SDK_AVAILABLE:
                # New SDK API
                result = client.models.embed_content(
                    model=self.MODEL,
                    contents=truncated,
                    config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY")
                )
                return list(result.embeddings[0].values)
            else:
                # Legacy SDK API
                result = genai_legacy.embed_content(
                    model=f"models/{self.MODEL}",
                    content=truncated,
                    task_type="RETRIEVAL_QUERY"
                )
                return result['embedding']
            
        except Exception as e:
            logger.error(f"Gemini query embedding failed: {e}")
            raise

            raise
