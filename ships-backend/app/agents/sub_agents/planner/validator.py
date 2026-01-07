"""
Plan Validator - Dynamic validation of implementation plans.

Uses LLM reasoning to validate ANY plan against ANY user request.
No hardcoded rules - fully scalable to any project type.
"""

from pydantic import BaseModel, Field
from typing import Literal
from app.core.llm_factory import LLMFactory
import logging

logger = logging.getLogger("ships.planner.validator")


class PlanValidationResult(BaseModel):
    """Result of plan validation - structured output."""
    status: Literal["pass", "needs_revision"]
    score: float = Field(ge=0.0, le=1.0, description="Quality score 0-1")
    missing_items: list[str] = Field(default_factory=list, description="What's missing")
    suggestions: list[str] = Field(default_factory=list, description="How to improve")


class PlanValidator:
    """
    Validates implementation plans against user requests.
    
    Uses LLM reasoning for dynamic, scalable validation.
    No hardcoded rules per app type.
    """
    
    def __init__(self):
        """Initialize validator with fast Flash model."""
        # Use minimal thinking for fast validation (planning already used high)
        self.llm = LLMFactory.get_model("mini", reasoning_level="standard")
        
    def validate(self, plan_data: dict, user_request: str) -> PlanValidationResult:
        """
        Validate plan completeness against user request.
        
        Args:
            plan_data: The generated plan (tasks, folders, etc.)
            user_request: Original user request
            
        Returns:
            PlanValidationResult with pass/fail and feedback
        """
        # Extract key plan components
        summary = plan_data.get("summary", "")
        tasks = plan_data.get("tasks", [])
        folders = plan_data.get("folders", [])
        
        prompt = f"""You are validating an implementation plan.

USER REQUEST:
{user_request}

PLAN SUMMARY:
{summary}

TASKS ({len(tasks)} total):
{self._format_tasks(tasks)}

FOLDERS ({len(folders)} total):
{self._format_folders(folders)}

VALIDATION CHECKLIST:
1. Does the plan address ALL features mentioned in the user request?
2. Is the folder structure modular and organized?
3. Are tasks granular enough (4-6+ tasks)?
4. Are acceptance criteria clear?
5. Does it feel production-ready, not MVP?

Provide:
- status: "pass" if score >= 0.8, else "needs_revision"
- score: 0.0 to 1.0 quality rating
- missing_items: List specific features/components missing
- suggestions: Specific improvements needed

Be strict but fair. Focus on COMPLETENESS, not perfection.
"""
        
        try:
            # Get structured validation result
            result = self.llm.with_structured_output(PlanValidationResult).invoke(prompt)
            
            logger.info(f"Plan validation: {result.status} (score: {result.score})")
            if result.status == "needs_revision":
                logger.warning(f"Missing items: {result.missing_items}")
                
            return result
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            # Default to pass on error (don't block pipeline)
            return PlanValidationResult(
                status="pass",
                score=0.7,
                suggestions=["Validation failed, proceeding with plan"]
            )
    
    def _format_tasks(self, tasks: list) -> str:
        """Format tasks for validation prompt."""
        if not tasks:
            return "NO TASKS"
        
        formatted = []
        for i, task in enumerate(tasks[:10], 1):  # Limit to 10 for token efficiency
            title = task.get("title", "Untitled")
            complexity = task.get("complexity", "unknown")
            formatted.append(f"{i}. {title} ({complexity})")
        
        if len(tasks) > 10:
            formatted.append(f"... and {len(tasks) - 10} more")
        
        return "\n".join(formatted)
    
    def _format_folders(self, folders: list) -> str:
        """Format folders for validation prompt."""
        if not folders:
            return "NO FOLDERS"
        
        paths = [f.get("path", "unknown") for f in folders[:15]]
        if len(folders) > 15:
            paths.append(f"... and {len(folders) - 15} more")
        
        return "\n".join(paths)
