"""
ShipS* Orchestrator Router

This orchestrator has been simplified to work with LangGraph:
- Removed: Complex state machine (LangGraph handles transitions)
- Removed: Sequential _run_workflow (LangGraph graph does this)
- Kept: LLM reasoning for ambiguous situations
- Kept: Error recovery system
- Kept: Audit logging via TransitionLogger

For disk-synced artifacts, use ArtifactManager from app/artifacts.
For in-memory state, use state["artifacts"] directly.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Callable, Literal
from dataclasses import dataclass, field
import uuid
import json
import re
import logging

from .state_machine import TransitionLogger, TransitionReason, StateContext
from .error_recovery import ErrorRecoverySystem, ErrorType, RecoveryResult, RecoveryStatus
from .artifact_flow import (
    ensure_artifacts_exist,
    get_artifact,
    check_phase_requirements,
    MissingArtifact,
)

# Import ArtifactManager for disk sync (the production persistence layer)
from app.artifacts import ArtifactManager, AgentType, AgentLogEntry

logger = logging.getLogger("ships.orchestrator")


@dataclass
class TaskResult:
    """Result of a complete task execution."""
    task_id: str
    success: bool
    final_phase: str
    artifacts_produced: List[str]
    transitions: List[Dict[str, Any]]
    duration_seconds: float
    error: Optional[str] = None
    user_escalation: Optional[RecoveryResult] = None


class ShipSOrchestrator:
    """
    Simplified Orchestrator for ShipS*.
    
    This class now serves as:
    1. A decision-making ROUTER for ambiguous situations (uses LLM)
    2. An audit LOGGER for tracking transitions
    3. An error RECOVERY coordinator
    
    It does NOT:
    - Run workflows (LangGraph does this via agent_graph.py)
    - Manage state transitions (LangGraph conditional edges do this)
    - Store artifacts (state["artifacts"] and ArtifactManager do this)
    
    Usage in LangGraph:
        orchestrator = ShipSOrchestrator(project_root)
        # In a conditional edge or node:
        decision = await orchestrator.decide_next_phase(state)
    """
    
    MAX_FIX_ATTEMPTS = 3
    
    def __init__(
        self, 
        project_root: str,
        artifact_manager: Optional[ArtifactManager] = None,
        reasoning_callback: Optional[Callable[[str, Any], None]] = None
    ):
        """
        Initialize the orchestrator.
        
        Args:
            project_root: Path to target project
            artifact_manager: Optional pre-configured artifact manager for disk sync
            reasoning_callback: Optional callback for streaming reasoning output
        """
        self.project_root = project_root
        self.reasoning_callback = reasoning_callback
        
        # Disk persistence layer (for frontend-visible artifacts)
        self.artifact_manager = artifact_manager or ArtifactManager(project_root)
        
        # Audit logging
        self.transition_logger = TransitionLogger()
        
        # Error recovery
        self.error_recovery = ErrorRecoverySystem()
        
        # LLM for reasoning in ambiguous situations
        from app.core.llm_factory import LLMFactory
        self._reasoning_llm = LLMFactory.get_model("orchestrator", reasoning_level="high")
    
    # =========================================================================
    # ROUTING DECISIONS
    # =========================================================================
    
    def should_proceed_to_phase(
        self, 
        state: Dict[str, Any], 
        target_phase: str
    ) -> tuple[bool, List[str]]:
        """
        Check if we can proceed to a target phase.
        
        Use this in LangGraph conditional edges.
        
        Args:
            state: LangGraph state dict
            target_phase: Phase we want to enter
            
        Returns:
            Tuple of (can_proceed, missing_requirements)
        """
        return check_phase_requirements(state, target_phase)
    
    def should_escalate(self, state: Dict[str, Any]) -> bool:
        """
        Check if we should escalate to user.
        
        Args:
            state: LangGraph state dict
            
        Returns:
            True if user intervention is needed
        """
        fix_attempts = state.get("fix_attempts", 0)
        max_attempts = state.get("max_fix_attempts", self.MAX_FIX_ATTEMPTS)
        return fix_attempts >= max_attempts
    
    async def decide_next_phase(
        self, 
        state: Dict[str, Any]
    ) -> str:
        """
        Use LLM reasoning to decide the next phase when simple rules are insufficient.
        
        Call this when multiple valid transitions exist.
        
        Args:
            state: LangGraph state dict
            
        Returns:
            Target phase literal
        """
        current_phase = state.get("phase", "idle")
        
        # First, try simple rule-based routing
        simple_next = self._simple_route(state)
        if simple_next:
            self.transition_logger.log_transition(simple_next, "rule_based")
            return simple_next
        
        # Fall back to LLM reasoning
        reasoning = await self._llm_reason({
            "current_phase": current_phase,
            "artifacts": list(state.get("artifacts", {}).keys()),
            "fix_attempts": state.get("fix_attempts", 0),
            "error_log": state.get("error_log", [])[-5:],  # Last 5 errors
        })
        
        decision = reasoning.get("suggested_phase", "error")
        self.transition_logger.log_transition(decision, f"llm_reasoning:{reasoning.get('confidence', 0)}")
        
        return decision
    
    def _simple_route(self, state: Dict[str, Any]) -> Optional[str]:
        """Simple rule-based routing. Returns None if ambiguous."""
        phase = state.get("phase", "idle")
        artifacts = state.get("artifacts", {})
        validation_passed = state.get("validation_passed", False)
        
        SIMPLE_ROUTES = {
            "idle": "planning" if "user_request" in artifacts else None,
            "planning": "coding" if "plan" in artifacts else None,
            "coding": "validating" if "code_changes" in artifacts else None,
            "validating": "complete" if validation_passed else "fixing",
            "fixing": "validating",  # Always re-validate after fix
            "building": "complete" if state.get("build_passed", False) else "fixing",
        }
        
        next_phase = SIMPLE_ROUTES.get(phase)
        
        # Check for escalation
        if next_phase == "fixing" and self.should_escalate(state):
            return "escalated"
        
        return next_phase
    
    # =========================================================================
    # ERROR HANDLING
    # =========================================================================
    
    def handle_error(
        self, 
        error_type: ErrorType, 
        context: Dict[str, Any],
        task_id: Optional[str] = None
    ) -> RecoveryResult:
        """
        Handle an error with the recovery system.
        
        Args:
            error_type: Type of error
            context: Error context
            task_id: Optional task ID for tracking
            
        Returns:
            RecoveryResult with recommended action
        """
        error_id = f"{task_id or 'unknown'}_{error_type.value}"
        result = self.error_recovery.handle_error(error_type, error_id, context)
        
        # Log to disk for frontend visibility
        self.artifact_manager.log_agent_action(
            agent=AgentType.ORCHESTRATOR,
            action=f"error_handled:{error_type.value}",
            input_summary=context.get("error_message", "Unknown error"),
            output_summary=f"Status: {result.status.value}, Attempts: {result.attempts}",
            task_id=task_id
        )
        
        return result
    
    # =========================================================================
    # AUDIT TRAIL
    # =========================================================================
    
    def get_audit_trail(self) -> Dict[str, Any]:
        """Get full audit trail for debugging."""
        return {
            "transition_history": [
                {
                    "from": t.from_phase,
                    "to": t.to_phase,
                    "reason": t.reason,
                    "timestamp": t.timestamp.isoformat(),
                }
                for t in self.transition_logger.get_history()
            ],
            "error_attempts": self.error_recovery.get_summary(),
            "current_phase": self.transition_logger.current_phase,
        }
    
    def log_phase_change(
        self, 
        from_phase: str, 
        to_phase: str, 
        reason: str = "transition",
        task_id: Optional[str] = None
    ) -> None:
        """
        Log a phase change for audit purposes.
        
        Call this from LangGraph nodes when transitioning.
        
        Args:
            from_phase: Phase we're leaving
            to_phase: Phase we're entering
            reason: Reason for transition
            task_id: Optional task ID
        """
        self.transition_logger.log_transition(to_phase, reason)
        
        # Also log to disk
        self.artifact_manager.log_agent_action(
            agent=AgentType.ORCHESTRATOR,
            action=f"phase_change:{from_phase}->{to_phase}",
            reasoning=reason,
            task_id=task_id
        )
    
    # =========================================================================
    # LLM REASONING (For Ambiguous Situations)
    # =========================================================================
    
    def _stream_reasoning(self, event_type: str, data: Any) -> None:
        """Stream reasoning events to callback if registered."""
        if self.reasoning_callback:
            self.reasoning_callback(event_type, data)
    
    async def _llm_reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM to reason about next action when rules are ambiguous.
        
        Args:
            context: Current context including phase, artifacts, errors
            
        Returns:
            Structured reasoning result with decision and confidence
        """
        current_phase = context.get("current_phase", "unknown")
        
        prompt = f"""<role>You are the ShipS* Orchestrator deciding the next phase.</role>

<state>
CURRENT_PHASE: {current_phase}
AVAILABLE_ARTIFACTS: {context.get('artifacts', [])}
FIX_ATTEMPTS: {context.get('fix_attempts', 0)}
RECENT_ERRORS: {context.get('error_log', [])}
</state>

<valid_phases>
planning, coding, validating, fixing, building, complete, error, escalated
</valid_phases>

<task>
Decide the best next phase. Consider:
1. What artifacts do we have?
2. Are there errors that need fixing?
3. Should we escalate to the user?
</task>

<output_format>
Respond with JSON only:
{{
  "observations": ["key observations"],
  "reasoning": "step-by-step analysis",
  "suggested_phase": "phase_name",
  "confidence": 0.0 to 1.0
}}
</output_format>"""
        
        self._stream_reasoning("thinking", {"status": "analyzing..."})
        
        from langchain_core.messages import HumanMessage, SystemMessage
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content="Decide the next phase. Respond with JSON.")
        ]
        
        try:
            response = await self._reasoning_llm.ainvoke(messages)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            result = {
                "observations": [],
                "reasoning": "",
                "suggested_phase": "error",
                "confidence": 0.5
            }
            
            try:
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    parsed = json.loads(json_match.group())
                    result.update(parsed)
            except (json.JSONDecodeError, AttributeError):
                result["reasoning"] = response_text
            
            # Stream events
            for obs in result.get("observations", []):
                self._stream_reasoning("observation", obs)
            
            self._stream_reasoning("reasoning", result.get("reasoning", ""))
            self._stream_reasoning("decision", result.get("suggested_phase", "error"))
            self._stream_reasoning("confidence", result.get("confidence", 0.5))
            
            # Self-critique if confidence is low
            if result.get("confidence", 0) < 0.7:
                logger.info(f"[ORCHESTRATOR] Low confidence ({result.get('confidence')}), keeping decision")
            
            return result
            
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] LLM reasoning failed: {e}")
            return {
                "observations": [f"LLM error: {e}"],
                "reasoning": "Fallback to error phase",
                "suggested_phase": "error",
                "confidence": 0.1
            }


# Convenience function for LangGraph integration
def create_orchestrator_router(
    project_root: str,
    reasoning_callback: Optional[Callable] = None
) -> ShipSOrchestrator:
    """
    Create an orchestrator configured for LangGraph routing.
    
    Args:
        project_root: Path to project
        reasoning_callback: Optional callback for streaming reasoning
        
    Returns:
        Configured ShipSOrchestrator
    """
    return ShipSOrchestrator(
        project_root=project_root,
        reasoning_callback=reasoning_callback
    )
