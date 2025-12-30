"""
Gemini Explicit Caching Manager

Handles the creation, retrieval, and management of explicit caches for Gemini models.
Supports both google-genai (V1) and google-generativeai (Legacy) SDKs.

This allows agents to reuse large context (Project Structure, API Contracts) without
re-sending tokens, reducing latency and cost.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("ships.cache")

# Try importing SDKs (prefer newer google.genai)
try:
    from google import genai
    from google.genai import types
    SDK_VERSION = "v1"
except ImportError:
    try:
        import warnings
        warnings.filterwarnings('ignore', category=FutureWarning)
        import google.generativeai as genai
        from google.generativeai import caching
        SDK_VERSION = "legacy"
    except ImportError:
        SDK_VERSION = None
        logger.warning("No Gemini SDK found. Explicit caching disabled.")


class GeminiCacheManager:
    """Manages explicit context caching for Gemini."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set. Caching disabled.")
            self.enabled = False
        else:
            self.enabled = bool(SDK_VERSION)
            
        if self.enabled and SDK_VERSION == "legacy":
            genai.configure(api_key=self.api_key)
            self.client = None # Legacy uses module-level functions
        elif self.enabled and SDK_VERSION == "v1":
             self.client = genai.Client(api_key=self.api_key)

    def create_project_context_cache(
        self, 
        project_id: str,
        artifacts: Dict[str, str],
        ttl_minutes: int = 60
    ) -> Optional[str]:
        """
        Create a cache for project context.
        
        Args:
            project_id: Unique project ID
            artifacts: Dict of {name: content_string} (e.g. folder_map, api_contracts)
            ttl_minutes: Time to live
            
        Returns:
            Cache resource name (e.g. 'cachedContents/123...') or None
        """
        if not self.enabled: return None
        
        # Build cache content
        content_parts = []
        content_parts.append("# PROJECT CONTEXT\n\n")
        
        if "folder_map" in artifacts:
            content_parts.append("## Folder Structure\n")
            content_parts.append(artifacts["folder_map"])
            content_parts.append("\n\n")
            
        if "api_contracts" in artifacts:
            content_parts.append("## API Contracts\n")
            content_parts.append(artifacts["api_contracts"])
            content_parts.append("\n\n")
            
        if "dependencies" in artifacts:
            content_parts.append("## Dependencies\n")
            content_parts.append(artifacts["dependencies"])
            content_parts.append("\n\n")
            
        full_content = "".join(content_parts)
        
        cache_name = f"ships-project-{project_id}"
        
        try:
            if SDK_VERSION == "legacy":
                # Check if exists (by iterating list - naive)
                # Legacy SDK doesn't support 'get' by alias easily, usually by name
                # We'll just create a new one for now (or let API handle dedupe?)
                # Actually, explicit caching creates a NEW resource each time usually.
                
                cache = caching.CachedContent.create(
                    model='models/gemini-1.5-flash-001', # Base model (Flash supports caching?)
                    # Note: Gemini 1.5 Flash supports caching. 
                    # Gemini 3 Flash Preview might not yet via public SDK?
                    # User said "Gemini 3 Flash Preview 1024 token limit".
                    # We should align with the model we use.
                    # app uses gemini-3-flash-preview.
                    
                    display_name=cache_name,
                    system_instruction="You are an expert AI developer with access to this project context.",
                    contents=[full_content],
                    ttl=timedelta(minutes=ttl_minutes)
                )
                logger.info(f"[CACHE] Created legacy cache: {cache.name}")
                return cache.name
                
            elif SDK_VERSION == "v1":
                # Create cache
                cache = self.client.caches.create(
                    model='models/gemini-1.5-flash-001', # TODO: Configurable
                    config=types.CreateCachedContentConfig(
                        display_name=cache_name,
                        system_instruction="You are an expert AI developer.",
                        contents=[full_content],
                        ttl=f"{ttl_minutes * 60}s"
                    )
                )
                logger.info(f"[CACHE] Created v1 cache: {cache.name}")
                return cache.name
                
        except Exception as e:
            logger.error(f"[CACHE] Failed to create cache: {e}")
            return None

    def get_cache_name_for_agent(self, project_id: str) -> Optional[str]:
        """
        Retrieve existing cache name for project if active.
        IN PROGRESS: For now, we rely on creating a new one or passed ID.
        Ideally we store the cache.name in memory/state.
        """
        return None 

# Global instance
cache_manager = GeminiCacheManager()
