"""
Knowledge retrieval pipeline.

Semantic search for relevant past solutions based on current problem context.
Injects proven solutions into agent prompts.
"""

import logging
from typing import Optional
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeEntry
from app.services.embeddings import embed

logger = logging.getLogger("ships.knowledge.retrieval")


class EntryType(str, Enum):
    """Types of knowledge entries."""
    ERROR_FIX = "error_fix"
    PATTERN = "pattern"
    INTEGRATION = "integration"


@dataclass
class KnowledgeSuggestion:
    """A retrieved knowledge suggestion for agent prompt injection."""
    entry_id: str
    entry_type: str
    solution_description: str
    solution_pattern: str
    confidence: float
    success_count: int
    tech_stack: str
    similarity_score: float


async def retrieve_relevant_knowledge(
    db: AsyncSession,
    query: str,
    tech_stack: str,
    entry_types: Optional[list[str]] = None,
    user_id: Optional[str] = None,
    include_community: bool = True,
    limit: int = 5,
    min_confidence: float = 0.6,
) -> list[KnowledgeSuggestion]:
    """
    Retrieve relevant knowledge entries for current query.
    
    Uses vector similarity search with entry type filtering.
    
    Args:
        db: Database session
        query: Query text (error message OR feature request)
        tech_stack: Current project tech stack
        entry_types: Types to include (None = all)
        user_id: Current user for visibility filtering
        include_community: Include community-shared knowledge
        limit: Maximum suggestions to return
        min_confidence: Minimum confidence threshold
        
    Returns:
        List of ranked KnowledgeSuggestion objects
    """
    # Generate query embedding
    try:
        query_text = f"{query} {tech_stack}"
        query_embedding = await embed(query_text)
    except Exception as e:
        logger.error(f"Query embedding failed: {e}")
        return await _fallback_text_search(db, query, tech_stack, entry_types, limit)
    
    # Build visibility filter
    visibility_conditions = []
    if include_community:
        visibility_conditions.append("visibility = 'community'")
    if user_id:
        visibility_conditions.append(f"user_id = '{user_id}'")
    # Always include private entries if no user (for system queries)
    if not visibility_conditions:
        visibility_conditions.append("1=1")
    
    visibility_filter = " OR ".join(visibility_conditions)
    
    # Build entry type filter
    if entry_types:
        type_list = ", ".join([f"'{t}'" for t in entry_types])
        type_filter = f"entry_type IN ({type_list})"
    else:
        type_filter = "1=1"
    
    # Vector similarity search with pgvector
    query_sql = text(f"""
        SELECT 
            id,
            entry_type,
            solution_description,
            solution_pattern,
            confidence,
            success_count,
            tech_stack,
            1 - (context_embedding <=> :embedding) as similarity
        FROM knowledge_entries
        WHERE 
            context_embedding IS NOT NULL
            AND ({visibility_filter})
            AND ({type_filter})
            AND confidence >= :min_confidence
        ORDER BY context_embedding <=> :embedding
        LIMIT :limit
    """)
    
    try:
        result = await db.execute(
            query_sql,
            {
                "embedding": str(query_embedding),
                "limit": limit * 2,  # Over-fetch for filtering
                "min_confidence": min_confidence,
            }
        )
        rows = result.fetchall()
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return await _fallback_text_search(db, query, tech_stack, entry_types, limit)
    
    # Filter and rank results
    suggestions = []
    for row in rows:
        # Boost for matching tech stack
        tech_match = 1.2 if row.tech_stack == tech_stack else 1.0
        
        # Boost for high success count
        success_boost = min(row.success_count / 50, 0.2)
        
        # Calculate final score
        final_score = row.similarity * tech_match * row.confidence + success_boost
        
        # Only include quality matches
        if row.similarity >= 0.4:
            suggestions.append(KnowledgeSuggestion(
                entry_id=str(row.id),
                entry_type=row.entry_type,
                solution_description=row.solution_description or "",
                solution_pattern=row.solution_pattern,
                confidence=row.confidence,
                success_count=row.success_count,
                tech_stack=row.tech_stack or "",
                similarity_score=row.similarity,
            ))
    
    # Sort by composite score and limit
    suggestions.sort(key=lambda s: s.similarity_score * s.confidence, reverse=True)
    suggestions = suggestions[:limit]
    
    logger.info(f"Retrieved {len(suggestions)} knowledge suggestions")
    return suggestions


async def retrieve_for_fixer(
    db: AsyncSession,
    error_message: str,
    tech_stack: str,
    user_id: Optional[str] = None,
    limit: int = 3,
) -> list[KnowledgeSuggestion]:
    """
    Retrieve knowledge for Fixer agent.
    
    Focuses on error_fix entries only.
    
    Args:
        db: Database session
        error_message: Error to fix
        tech_stack: Project tech stack
        user_id: Current user
        limit: Max suggestions
        
    Returns:
        Ranked suggestions for error fixes
    """
    return await retrieve_relevant_knowledge(
        db=db,
        query=error_message,
        tech_stack=tech_stack,
        entry_types=[EntryType.ERROR_FIX.value],
        user_id=user_id,
        include_community=True,
        limit=limit,
        min_confidence=0.65,  # Higher threshold for fixes
    )


async def retrieve_for_coder(
    db: AsyncSession,
    feature_request: str,
    tech_stack: str,
    user_id: Optional[str] = None,
    limit: int = 3,
) -> list[KnowledgeSuggestion]:
    """
    Retrieve knowledge for Coder agent.
    
    Includes both patterns (preferred) and error_fix entries
    (to avoid known mistakes).
    
    Args:
        db: Database session
        feature_request: What to build
        tech_stack: Project tech stack
        user_id: Current user
        limit: Max suggestions
        
    Returns:
        Ranked suggestions for code generation
    """
    return await retrieve_relevant_knowledge(
        db=db,
        query=feature_request,
        tech_stack=tech_stack,
        entry_types=[EntryType.PATTERN.value, EntryType.ERROR_FIX.value],
        user_id=user_id,
        include_community=True,
        limit=limit,
        min_confidence=0.6,
    )


async def _fallback_text_search(
    db: AsyncSession,
    query: str,
    tech_stack: str,
    entry_types: Optional[list[str]],
    limit: int,
) -> list[KnowledgeSuggestion]:
    """
    Fallback text-based search when vector search unavailable.
    """
    stmt = (
        select(KnowledgeEntry)
        .where(KnowledgeEntry.tech_stack == tech_stack)
        .where(KnowledgeEntry.confidence >= 0.6)
        .order_by(KnowledgeEntry.success_count.desc())
        .limit(limit)
    )
    
    if entry_types:
        stmt = stmt.where(KnowledgeEntry.entry_type.in_(entry_types))
    
    result = await db.execute(stmt)
    entries = result.scalars().all()
    
    return [
        KnowledgeSuggestion(
            entry_id=str(e.id),
            entry_type=e.entry_type,
            solution_description=e.solution_description or "",
            solution_pattern=e.solution_pattern,
            confidence=e.confidence,
            success_count=e.success_count,
            tech_stack=e.tech_stack or "",
            similarity_score=0.5,
        )
        for e in entries
    ]


def format_suggestions_for_prompt(
    suggestions: list[KnowledgeSuggestion],
    for_agent: str = "fixer",
) -> str:
    """
    Format knowledge suggestions for injection into agent prompt.
    
    Different formatting based on target agent.
    
    Args:
        suggestions: List of KnowledgeSuggestion objects
        for_agent: Target agent ("fixer" or "coder")
        
    Returns:
        Formatted markdown string for prompt injection
    """
    if not suggestions:
        return ""
    
    if for_agent == "coder":
        return _format_for_coder(suggestions)
    else:
        return _format_for_fixer(suggestions)


def _format_for_fixer(suggestions: list[KnowledgeSuggestion]) -> str:
    """Format suggestions for Fixer agent."""
    lines = ["## Proven Fixes from Ships Knowledge Base\n"]
    lines.append("These solutions have successfully fixed similar errors:\n")
    
    for i, s in enumerate(suggestions, 1):
        confidence_pct = int(s.confidence * 100)
        lines.append(f"### Fix {i} (Success rate: {confidence_pct}%, Used {s.success_count}x)")
        
        if s.solution_description:
            lines.append(f"**What worked:** {s.solution_description}")
        
        lines.append(f"```\n{s.solution_pattern[:500]}\n```\n")
    
    lines.append("Apply the most relevant fix pattern above.\n")
    return "\n".join(lines)


def _format_for_coder(suggestions: list[KnowledgeSuggestion]) -> str:
    """Format suggestions for Coder agent."""
    lines = ["## Relevant Patterns from Ships Knowledge Base\n"]
    
    patterns = [s for s in suggestions if s.entry_type == "pattern"]
    fixes = [s for s in suggestions if s.entry_type == "error_fix"]
    
    if patterns:
        lines.append("### Successful Implementation Patterns\n")
        for i, s in enumerate(patterns, 1):
            lines.append(f"**Pattern {i}** ({s.success_count}x successful)")
            if s.solution_description:
                lines.append(f"- {s.solution_description}")
            lines.append(f"```\n{s.solution_pattern[:400]}\n```\n")
    
    if fixes:
        lines.append("### Known Pitfalls to Avoid\n")
        lines.append("Previous implementations encountered these issues:\n")
        for s in fixes[:2]:  # Limit pitfall warnings
            if s.solution_description:
                lines.append(f"- Solved by: {s.solution_description}")
    
    lines.append("\nLeverage these patterns while implementing the requested feature.\n")
    return "\n".join(lines)

