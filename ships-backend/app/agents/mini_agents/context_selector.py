"""
ShipS* Context Selector

Lightweight filter to reduce token waste and prevent over-contextualization.
NOT an LLM agent - this is deterministic logic.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class ContextRelevance(str, Enum):
    """How relevant is a piece of context."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass
class ContextItem:
    """A piece of context that could be included."""
    path: str
    content: str
    relevance: ContextRelevance
    token_estimate: int
    reason: str


class ContextSelector:
    """
    Lightweight filter to reduce token waste and prevent over-contextualization.
    
    NOT an LLM agent - this is deterministic logic.
    
    Benefits:
    - Faster iteration
    - More deterministic Validator and Fixer behavior
    - Lower cost
    """
    
    # File extensions by relevance
    EXTENSION_RELEVANCE = {
        ".ts": ContextRelevance.HIGH,
        ".tsx": ContextRelevance.HIGH,
        ".js": ContextRelevance.HIGH,
        ".jsx": ContextRelevance.HIGH,
        ".py": ContextRelevance.HIGH,
        ".json": ContextRelevance.MEDIUM,
        ".css": ContextRelevance.MEDIUM,
        ".yaml": ContextRelevance.MEDIUM,
        ".yml": ContextRelevance.MEDIUM,
        ".md": ContextRelevance.LOW,
        ".txt": ContextRelevance.LOW,
        ".png": ContextRelevance.NONE,
        ".jpg": ContextRelevance.NONE,
        ".lock": ContextRelevance.NONE,
    }
    
    EXCLUDE_PATTERNS = [
        "node_modules/", "__pycache__/", ".git/",
        "dist/", "build/", ".next/", "coverage/"
    ]
    
    def __init__(self, max_tokens: int = 8000, chars_per_token: int = 4):
        self.max_tokens = max_tokens
        self.chars_per_token = chars_per_token
    
    def select(
        self,
        task: Dict[str, Any],
        available_files: Dict[str, str],
        priority_paths: Optional[List[str]] = None,
        force_include: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """Select relevant context for a task within token budget."""
        priority_paths = priority_paths or []
        force_include = force_include or []
        
        scored_items: List[ContextItem] = []
        
        for path, content in available_files.items():
            if self._should_exclude(path):
                continue
            
            relevance = self._calculate_relevance(path, content, task, priority_paths)
            token_estimate = len(content) // self.chars_per_token
            
            scored_items.append(ContextItem(
                path=path, content=content, relevance=relevance,
                token_estimate=token_estimate, reason=""
            ))
        
        # Sort by relevance then token count
        relevance_order = {
            ContextRelevance.HIGH: 0, ContextRelevance.MEDIUM: 1,
            ContextRelevance.LOW: 2, ContextRelevance.NONE: 3
        }
        scored_items.sort(key=lambda x: (relevance_order[x.relevance], x.token_estimate))
        
        selected: Dict[str, str] = {}
        used_tokens = 0
        
        # Force-include first
        for item in scored_items:
            if item.path in force_include:
                selected[item.path] = item.content
                used_tokens += item.token_estimate
        
        # Fill with highest relevance
        for item in scored_items:
            if item.path in selected or item.relevance == ContextRelevance.NONE:
                continue
            if used_tokens + item.token_estimate <= self.max_tokens:
                selected[item.path] = item.content
                used_tokens += item.token_estimate
        
        return selected
    
    def _should_exclude(self, path: str) -> bool:
        return any(p in path for p in self.EXCLUDE_PATTERNS)
    
    def _calculate_relevance(
        self, path: str, content: str, task: Dict[str, Any], priority_paths: List[str]
    ) -> ContextRelevance:
        for priority in priority_paths:
            if path.startswith(priority):
                return ContextRelevance.HIGH
        
        for ext, relevance in self.EXTENSION_RELEVANCE.items():
            if path.endswith(ext):
                return relevance
        
        return ContextRelevance.LOW
