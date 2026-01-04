"""
Knowledge integration with agent workflow.

Provides CoderKnowledge and FixerKnowledge classes for seamless
integration with respective agents.
"""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.knowledge.capture import (
    capture_successful_fix,
    capture_successful_pattern,
    record_failure,
)
from app.services.knowledge.retrieval import (
    retrieve_for_fixer,
    retrieve_for_coder,
    format_suggestions_for_prompt,
    KnowledgeSuggestion,
)
from app.services.knowledge.normalization import extract_tech_stack

logger = logging.getLogger("ships.knowledge.integration")


class FixerKnowledge:
    """
    Knowledge integration for Fixer agent.
    
    Retrieves proven fixes and captures successful error resolutions.
    
    Usage:
        knowledge = FixerKnowledge(db, user_id, tech_stack)
        
        # Before fixing
        suggestions = await knowledge.get_suggestions(error)
        prompt_injection = knowledge.format_for_prompt()
        
        # After successful fix
        await knowledge.capture_fix(error, solution_code, description, diff, ...)
    """
    
    def __init__(
        self,
        db: AsyncSession,
        user_id: Optional[str] = None,
        tech_stack: str = "unknown",
    ):
        """
        Initialize Fixer knowledge integration.
        
        Args:
            db: Database session
            user_id: Current user ID
            tech_stack: Project tech stack (e.g., "react+fastapi")
        """
        self.db = db
        self.user_id = user_id
        self.tech_stack = tech_stack
        self._current_suggestions: list[KnowledgeSuggestion] = []
        self._used_suggestion_id: Optional[str] = None
    
    async def get_suggestions(
        self,
        error_message: str,
        limit: int = 3,
    ) -> list[KnowledgeSuggestion]:
        """
        Get fix suggestions for an error.
        
        Args:
            error_message: The error to fix
            limit: Maximum suggestions
            
        Returns:
            List of relevant fix suggestions
        """
        try:
            self._current_suggestions = await retrieve_for_fixer(
                db=self.db,
                error_message=error_message,
                tech_stack=self.tech_stack,
                user_id=self.user_id,
                limit=limit,
            )
            
            if self._current_suggestions:
                logger.info(
                    f"Found {len(self._current_suggestions)} fix suggestions "
                    f"for error in {self.tech_stack}"
                )
            
            return self._current_suggestions
            
        except Exception as e:
            logger.error(f"Failed to retrieve fix suggestions: {e}")
            return []
    
    def format_for_prompt(self) -> str:
        """
        Format current suggestions for prompt injection.
        
        Returns:
            Formatted markdown for agent prompt
        """
        return format_suggestions_for_prompt(
            self._current_suggestions,
            for_agent="fixer",
        )
    
    def mark_suggestion_used(self, entry_id: str) -> None:
        """Mark which suggestion was used (for failure tracking)."""
        self._used_suggestion_id = entry_id
    
    async def capture_fix(
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
        user_reverted: bool = False,
    ) -> bool:
        """
        Capture a successful fix.
        
        Call after confirming build passed and error was resolved.
        
        Returns:
            True if captured successfully
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
                visibility="private",
                user_approved=user_approved,
                user_continued=user_continued,
                user_reverted=user_reverted,
            )
            return entry is not None
            
        except Exception as e:
            logger.error(f"Failed to capture fix: {e}")
            return False
    
    async def report_failure(self) -> None:
        """Report that the used suggestion didn't work."""
        if self._used_suggestion_id:
            try:
                await record_failure(self.db, self._used_suggestion_id)
                self._used_suggestion_id = None
            except Exception as e:
                logger.error(f"Failed to report failure: {e}")


class CoderKnowledge:
    """
    Knowledge integration for Coder agent.
    
    Retrieves patterns and past fixes to inform code generation,
    and captures successful code patterns.
    
    Usage:
        knowledge = CoderKnowledge(db, user_id, tech_stack)
        
        # Before coding
        suggestions = await knowledge.get_suggestions(feature_request)
        prompt_injection = knowledge.format_for_prompt()
        
        # After successful code generation
        await knowledge.capture_pattern(feature_request, code, description, files)
    """
    
    def __init__(
        self,
        db: AsyncSession,
        user_id: Optional[str] = None,
        tech_stack: str = "unknown",
    ):
        """
        Initialize Coder knowledge integration.
        
        Args:
            db: Database session
            user_id: Current user ID
            tech_stack: Project tech stack
        """
        self.db = db
        self.user_id = user_id
        self.tech_stack = tech_stack
        self._current_suggestions: list[KnowledgeSuggestion] = []
    
    async def get_suggestions(
        self,
        feature_request: str,
        limit: int = 3,
    ) -> list[KnowledgeSuggestion]:
        """
        Get code pattern suggestions for a feature request.
        
        Args:
            feature_request: What to build
            limit: Maximum suggestions
            
        Returns:
            List of relevant pattern/fix suggestions
        """
        try:
            self._current_suggestions = await retrieve_for_coder(
                db=self.db,
                feature_request=feature_request,
                tech_stack=self.tech_stack,
                user_id=self.user_id,
                limit=limit,
            )
            
            if self._current_suggestions:
                patterns = sum(1 for s in self._current_suggestions if s.entry_type == "pattern")
                fixes = len(self._current_suggestions) - patterns
                logger.info(
                    f"Found {patterns} patterns and {fixes} relevant fixes "
                    f"for '{feature_request[:50]}...'"
                )
            
            return self._current_suggestions
            
        except Exception as e:
            logger.error(f"Failed to retrieve coder suggestions: {e}")
            return []
    
    def format_for_prompt(self) -> str:
        """
        Format current suggestions for prompt injection.
        
        Returns:
            Formatted markdown for agent prompt
        """
        return format_suggestions_for_prompt(
            self._current_suggestions,
            for_agent="coder",
        )
    
    async def capture_pattern(
        self,
        session_id: str,
        feature_request: str,
        generated_code: str,
        code_description: str,
        files_created: list[str],
        build_passed: bool = True,
        user_continued: bool = False,
        user_approved: bool = False,
    ) -> bool:
        """
        Capture a successful code pattern.
        
        Call after confirming build passed and user accepted the code.
        
        Returns:
            True if captured successfully
        """
        try:
            entry = await capture_successful_pattern(
                db=self.db,
                session_id=session_id,
                feature_request=feature_request,
                generated_code=generated_code,
                code_description=code_description,
                tech_stack=self.tech_stack,
                files_created=files_created,
                user_id=self.user_id,
                visibility="private",
                build_passed=build_passed,
                user_continued=user_continued,
                user_approved=user_approved,
            )
            return entry is not None
            
        except Exception as e:
            logger.error(f"Failed to capture pattern: {e}")
            return False


# Legacy alias for backward compatibility
class KnowledgeIntegration(FixerKnowledge):
    """Legacy alias. Use FixerKnowledge or CoderKnowledge instead."""
    
    async def on_error(self, error_message: str, tech_stack: str) -> str:
        """Legacy method."""
        self.tech_stack = tech_stack
        await self.get_suggestions(error_message)
        return self.format_for_prompt()
    
    async def on_fix_success(self, **kwargs) -> bool:
        """Legacy method."""
        return await self.capture_fix(**kwargs)
    
    async def on_fix_failure(self, used_suggestion_id: Optional[str] = None) -> None:
        """Legacy method."""
        if used_suggestion_id:
            self.mark_suggestion_used(used_suggestion_id)
        await self.report_failure()
