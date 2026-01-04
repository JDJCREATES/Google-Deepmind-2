"""
Knowledge integration with agent workflow.

Hooks into agent success/failure paths to capture and retrieve knowledge.
"""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.knowledge import (
    capture_successful_fix,
    retrieve_relevant_knowledge,
    format_suggestions_for_prompt,
    record_failure,
    KnowledgeSuggestion,
)

logger = logging.getLogger("ships.knowledge.integration")


class KnowledgeIntegration:
    """
    Integrates Collective Intelligence with agent workflow.
    
    Call methods at appropriate points in the agent lifecycle:
    - on_error: When an error is detected, retrieve suggestions
    - on_fix_success: When a fix succeeds, capture it
    - on_fix_failure: When a suggested fix doesn't work
    """
    
    def __init__(self, db: AsyncSession, user_id: Optional[str] = None):
        """
        Initialize knowledge integration.
        
        Args:
            db: Database session
            user_id: Current user ID for visibility/attribution
        """
        self.db = db
        self.user_id = user_id
        self.use_community = True  # Default to include community knowledge
        self.current_suggestions: list[KnowledgeSuggestion] = []
    
    async def on_error(
        self,
        error_message: str,
        tech_stack: str,
    ) -> str:
        """
        Called when an error is detected.
        
        Retrieves relevant knowledge and returns prompt injection text.
        
        Args:
            error_message: The error to find solutions for
            tech_stack: Current project tech stack
            
        Returns:
            Formatted suggestions for prompt injection (empty if none found)
        """
        try:
            self.current_suggestions = await retrieve_relevant_knowledge(
                db=self.db,
                error_message=error_message,
                tech_stack=tech_stack,
                user_id=self.user_id,
                include_community=self.use_community,
                limit=3,
            )
            
            if self.current_suggestions:
                logger.info(
                    f"Found {len(self.current_suggestions)} relevant solutions "
                    f"for error in {tech_stack}"
                )
                return format_suggestions_for_prompt(self.current_suggestions)
            
            return ""
            
        except Exception as e:
            logger.error(f"Knowledge retrieval failed: {e}")
            return ""
    
    async def on_fix_success(
        self,
        session_id: str,
        error_message: str,
        solution_code: str,
        solution_description: str,
        diff: str,
        before_errors: list[str],
        after_errors: list[str],
        project_context: dict,
        user_approved: bool = False,
        user_continued: bool = False,
    ) -> bool:
        """
        Called when a fix succeeds.
        
        Captures the successful fix if it passes validation.
        
        Args:
            session_id: Agent session ID
            error_message: Error that was fixed
            solution_code: Code that fixed it
            solution_description: Description of the fix
            diff: Git-style diff
            before_errors: Errors before fix
            after_errors: Errors after fix (should be fewer)
            project_context: Project info
            user_approved: User explicitly approved
            user_continued: User continued working
            
        Returns:
            True if captured, False otherwise
        """
        try:
            entry = await capture_successful_fix(
                db=self.db,
                session_id=session_id,
                error_message=error_message,
                solution_code=solution_code,
                solution_description=solution_description,
                diff=diff,
                before_errors=before_errors,
                after_errors=after_errors,
                project_context=project_context,
                user_id=self.user_id,
                visibility="private",  # User can opt-in to community later
                user_approved=user_approved,
                user_continued=user_continued,
            )
            
            return entry is not None
            
        except Exception as e:
            logger.error(f"Knowledge capture failed: {e}")
            return False
    
    async def on_fix_failure(
        self,
        used_suggestion_id: Optional[str] = None,
    ) -> None:
        """
        Called when a fix fails.
        
        Records failure if a suggestion was used.
        
        Args:
            used_suggestion_id: ID of the suggestion that was tried
        """
        if used_suggestion_id:
            try:
                await record_failure(self.db, used_suggestion_id)
            except Exception as e:
                logger.error(f"Failed to record failure: {e}")
    
    def get_best_suggestion(self) -> Optional[KnowledgeSuggestion]:
        """Get the highest-confidence current suggestion."""
        if self.current_suggestions:
            return max(self.current_suggestions, key=lambda s: s.confidence)
        return None
