"""
Knowledge capture pipeline.

Handles the complete flow from successful fix to stored knowledge entry.
Includes validation, normalization, deduplication, and storage.
"""

import logging
from typing import Optional
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeEntry
from app.services.embeddings import embed
from app.services.knowledge.validation import (
    validate_for_capture,
    SessionContext,
    BuildState,
    ValidationResult,
)
from app.services.knowledge.normalization import (
    normalize_error,
    generate_error_signature,
    extract_tech_stack,
    extract_solution_pattern,
)

logger = logging.getLogger("ships.knowledge.capture")


async def capture_successful_fix(
    db: AsyncSession,
    session_id: str,
    error_message: str,
    solution_code: str,
    solution_description: str,
    diff: str,
    before_errors: list[str],
    after_errors: list[str],
    project_context: dict,
    user_id: Optional[str] = None,
    visibility: str = "private",
    user_approved: bool = False,
    user_continued: bool = False,
    user_reverted: bool = False,
) -> Optional[KnowledgeEntry]:
    """
    Capture a successful fix for future retrieval.
    
    Validates the fix through all gates, normalizes content,
    checks for duplicates, and stores if valid.
    
    Args:
        db: Database session
        session_id: Current agent session ID
        error_message: The error that was fixed
        solution_code: Full code that fixed the issue
        solution_description: Human-readable description of fix
        diff: Git-style diff of changes
        before_errors: Errors before fix
        after_errors: Errors after fix
        project_context: Project info for tech stack detection
        user_id: Optional user ID for attribution
        visibility: Sharing scope (private, team, community)
        user_approved: User explicitly approved the fix
        user_continued: User continued working (implicit approval)
        user_reverted: User reverted the change
        
    Returns:
        KnowledgeEntry if captured, None if validation failed
    """
    # Build validation context
    before_state = BuildState(
        status="error",
        errors=before_errors,
        warnings=[]
    )
    after_state = BuildState(
        status="success" if not after_errors else "error",
        errors=after_errors,
        warnings=[]
    )
    
    context = SessionContext(
        session_id=session_id,
        diff=diff,
        before_state=before_state,
        after_state=after_state,
        user_approved=user_approved,
        user_continued=user_continued,
        user_reverted=user_reverted,
    )
    
    # Run validation gates
    validation = validate_for_capture(context)
    
    if not validation.passed:
        logger.info(
            f"Capture rejected: {validation.reason} "
            f"(gates failed: {validation.gates_failed})"
        )
        return None
    
    # Normalize error
    error_sig = normalize_error(error_message)
    error_signature = generate_error_signature(error_message)
    
    # Extract tech stack
    tech_stack = extract_tech_stack(project_context)
    
    # Check for existing similar entry
    existing = await find_similar_entry(db, error_sig, tech_stack)
    
    if existing:
        # Merge with existing entry
        existing.increment_success()
        await db.commit()
        logger.info(
            f"Merged with existing entry {existing.id} "
            f"(success_count now {existing.success_count})"
        )
        return existing
    
    # Generate embedding for new entry
    try:
        embedding_text = f"{error_sig} {tech_stack} {solution_description}"
        context_embedding = await embed(embedding_text)
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        context_embedding = None
    
    # Extract pattern from solution
    solution_pattern = extract_solution_pattern(solution_code)
    
    # Create new entry
    entry = KnowledgeEntry(
        entry_type="error_fix",
        error_signature=error_sig,
        tech_stack=tech_stack,
        context_embedding=context_embedding,
        solution_pattern=solution_pattern,
        solution_description=solution_description,
        confidence=validation.confidence,
        visibility=visibility,
        user_id=user_id,
    )
    
    # Compress full solution
    entry.compress_solution(solution_code)
    
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    
    logger.info(
        f"Captured new knowledge entry {entry.id} "
        f"(confidence: {entry.confidence:.2f}, tech: {tech_stack})"
    )
    
    return entry


async def find_similar_entry(
    db: AsyncSession,
    error_signature: str,
    tech_stack: str,
    threshold: float = 0.95
) -> Optional[KnowledgeEntry]:
    """
    Find existing entry with very similar error signature.
    
    Used for deduplication before inserting new entries.
    
    Args:
        db: Database session
        error_signature: Normalized error string
        tech_stack: Tech stack identifier
        threshold: Similarity threshold (not used for exact match)
        
    Returns:
        Existing entry if found, None otherwise
    """
    # First try exact match on signature
    result = await db.execute(
        select(KnowledgeEntry)
        .where(KnowledgeEntry.error_signature == error_signature)
        .where(KnowledgeEntry.tech_stack == tech_stack)
        .where(KnowledgeEntry.entry_type == "error_fix")
        .limit(1)
    )
    
    existing = result.scalar_one_or_none()
    
    if existing:
        logger.debug(f"Found exact match: {existing.id}")
        return existing
    
    # Could add vector similarity search here for fuzzy matching
    # For now, rely on exact signature match
    
    return None


async def record_failure(
    db: AsyncSession,
    entry_id: str,
) -> None:
    """
    Record that a knowledge entry was used but didn't work.
    
    Decreases confidence for entries that don't help.
    
    Args:
        db: Database session
        entry_id: ID of the entry that was tried
    """
    result = await db.execute(
        select(KnowledgeEntry).where(KnowledgeEntry.id == entry_id)
    )
    entry = result.scalar_one_or_none()
    
    if entry:
        entry.increment_failure()
        await db.commit()
        logger.info(f"Recorded failure for entry {entry_id}")
