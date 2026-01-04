"""
Knowledge retrieval pipeline.

Semantic search for relevant past solutions based on current problem context.
Injects proven solutions into agent prompts.
"""

import logging
from typing import Optional
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeEntry
from app.services.embeddings import embed

logger = logging.getLogger("ships.knowledge.retrieval")


@dataclass
class KnowledgeSuggestion:
    """A retrieved knowledge suggestion for agent prompt injection."""
    entry_id: str
    solution_description: str
    solution_pattern: str
    confidence: float
    success_count: int
    tech_stack: str
    similarity_score: float


async def retrieve_relevant_knowledge(
    db: AsyncSession,
    error_message: str,
    tech_stack: str,
    user_id: Optional[str] = None,
    include_community: bool = True,
    limit: int = 5,
) -> list[KnowledgeSuggestion]:
    """
    Retrieve relevant knowledge entries for current problem.
    
    Uses vector similarity search to find past solutions
    that may apply to the current error.
    
    Args:
        db: Database session
        error_message: Current error to find solutions for
        tech_stack: Current project tech stack
        user_id: Current user for visibility filtering
        include_community: Include community-shared knowledge
        limit: Maximum suggestions to return
        
    Returns:
        List of ranked KnowledgeSuggestion objects
    """
    # Generate query embedding
    try:
        query_text = f"{error_message} {tech_stack}"
        query_embedding = await embed(query_text)
    except Exception as e:
        logger.error(f"Query embedding failed: {e}")
        return await _fallback_text_search(db, error_message, tech_stack, limit)
    
    # Build visibility filter
    visibility_conditions = ["visibility = 'community'"] if include_community else []
    if user_id:
        visibility_conditions.append(f"user_id = '{user_id}'")
    
    visibility_filter = " OR ".join(visibility_conditions) if visibility_conditions else "1=1"
    
    # Vector similarity search with pgvector
    query = text(f"""
        SELECT 
            id,
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
            AND confidence >= 0.6
        ORDER BY context_embedding <=> :embedding
        LIMIT :limit
    """)
    
    try:
        result = await db.execute(
            query,
            {
                "embedding": str(query_embedding),
                "limit": limit * 2  # Fetch extra for filtering
            }
        )
        rows = result.fetchall()
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return await _fallback_text_search(db, error_message, tech_stack, limit)
    
    # Filter and rank results
    suggestions = []
    for row in rows:
        # Boost for matching tech stack
        tech_match = 1.2 if row.tech_stack == tech_stack else 1.0
        
        # Boost for high success count
        success_boost = min(row.success_count / 50, 0.2)
        
        # Calculate final score
        final_score = row.similarity * tech_match * row.confidence + success_boost
        
        # Only include high-quality matches
        if row.similarity >= 0.5:
            suggestions.append(KnowledgeSuggestion(
                entry_id=str(row.id),
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


async def _fallback_text_search(
    db: AsyncSession,
    error_message: str,
    tech_stack: str,
    limit: int,
) -> list[KnowledgeSuggestion]:
    """
    Fallback text-based search when vector search unavailable.
    """
    # Extract key terms from error
    terms = error_message.lower().split()[:5]
    
    result = await db.execute(
        select(KnowledgeEntry)
        .where(KnowledgeEntry.tech_stack == tech_stack)
        .where(KnowledgeEntry.confidence >= 0.6)
        .order_by(KnowledgeEntry.success_count.desc())
        .limit(limit)
    )
    
    entries = result.scalars().all()
    
    return [
        KnowledgeSuggestion(
            entry_id=str(e.id),
            solution_description=e.solution_description or "",
            solution_pattern=e.solution_pattern,
            confidence=e.confidence,
            success_count=e.success_count,
            tech_stack=e.tech_stack or "",
            similarity_score=0.5,  # Default score for fallback
        )
        for e in entries
    ]


def format_suggestions_for_prompt(
    suggestions: list[KnowledgeSuggestion]
) -> str:
    """
    Format knowledge suggestions for injection into agent prompt.
    
    Args:
        suggestions: List of KnowledgeSuggestion objects
        
    Returns:
        Formatted markdown string for prompt injection
    """
    if not suggestions:
        return ""
    
    lines = ["## Proven Solutions from Ships Knowledge Base\n"]
    lines.append("The following solutions have worked for similar issues:\n")
    
    for i, s in enumerate(suggestions, 1):
        confidence_pct = int(s.confidence * 100)
        lines.append(f"### Solution {i} (Used {s.success_count}x, {confidence_pct}% success rate)")
        
        if s.solution_description:
            lines.append(f"**Approach:** {s.solution_description}")
        
        lines.append(f"```\n{s.solution_pattern}\n```\n")
    
    lines.append("Consider applying these proven patterns if applicable.\n")
    
    return "\n".join(lines)
