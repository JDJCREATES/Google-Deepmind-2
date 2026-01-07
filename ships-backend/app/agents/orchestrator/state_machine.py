"""
ShipS* Orchestrator State Machine (Simplified)

This module now provides:
1. TransitionReason enum - Kept for audit logging
2. StateTransition dataclass - Kept for history/audit trail
3. TransitionLogger - Simple logger for tracking phase changes (replaces complex StateMachine)
4. Phase literals - Aligned with LangGraph's AgentGraphState.phase

The complex OrchestratorState enum and StateMachine class have been simplified
because LangGraph handles state transitions through conditional edges.
"""

from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable, Literal
from dataclasses import dataclass, field
import uuid

from pydantic import BaseModel, Field


# ============================================================================
# PHASE LITERALS (Aligned with AgentGraphState)
# ============================================================================

# These match the 'phase' field in AgentGraphState
Phase = Literal[
    "idle",
    "planning",
    "coding", 
    "validating",
    "fixing",
    "building",
    "complete",
    "error",
    "escalated"
]


# ============================================================================
# TRANSITION REASONS (Kept for audit logging)
# ============================================================================

class TransitionReason(str, Enum):
    """Reasons for state transitions. Useful for audit trails."""
    USER_REQUEST = "user_request"
    REQUEST_INTERPRETED = "request_interpreted"
    PLAN_APPROVED = "plan_approved"
    CODE_GENERATED = "code_generated"
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED = "validation_failed"
    FIX_APPLIED = "fix_applied"
    FIX_FAILED = "fix_failed"
    BUILD_SUCCEEDED = "build_succeeded"
    BUILD_FAILED = "build_failed"
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"
    USER_CANCELLED = "user_cancelled"
    UNRECOVERABLE_ERROR = "unrecoverable_error"


# ============================================================================
# TRANSITION RECORD (Kept for audit trail)
# ============================================================================

@dataclass
class StateTransition:
    """Record of a single phase transition for audit logging."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    from_phase: str = "idle"
    to_phase: str = "idle"
    reason: str = "user_request"
    details: Dict[str, Any] = field(default_factory=dict)
    gate_results: Dict[str, bool] = field(default_factory=dict)


class TransitionError(Exception):
    """Raised when a phase transition fails a quality gate."""
    def __init__(self, from_phase: str, to_phase: str, reason: str):
        self.from_phase = from_phase
        self.to_phase = to_phase
        self.reason = reason
        super().__init__(f"Cannot transition from {from_phase} to {to_phase}: {reason}")


# ============================================================================
# TRANSITION LOGGER (Simplified - just tracks history)
# ============================================================================

class TransitionLogger:
    """
    Simple transition logger for audit trails.
    
    This replaces the complex StateMachine class. LangGraph handles
    actual state transitions through conditional edges.
    
    This class only:
    - Logs phase transitions for debugging
    - Tracks history for audit trails
    - Provides summary for status endpoints
    """
    
    def __init__(self, task_id: Optional[str] = None):
        """Initialize the logger."""
        self.task_id = task_id or str(uuid.uuid4())
        self.current_phase: str = "idle"
        self.history: List[StateTransition] = []
        self.started_at = datetime.utcnow()
    
    def log_transition(
        self,
        to_phase: str,
        reason: str = "transition",
        details: Optional[Dict[str, Any]] = None,
        gate_results: Optional[Dict[str, bool]] = None
    ) -> StateTransition:
        """
        Log a phase transition.
        
        Args:
            to_phase: Target phase
            reason: Why we're transitioning
            details: Additional context
            gate_results: Results of any quality gate checks
            
        Returns:
            StateTransition record
        """
        transition = StateTransition(
            from_phase=self.current_phase,
            to_phase=to_phase,
            reason=reason,
            details=details or {},
            gate_results=gate_results or {}
        )
        
        self.history.append(transition)
        self.current_phase = to_phase
        
        return transition
    
    def get_history(self) -> List[StateTransition]:
        """Get full transition history."""
        return self.history.copy()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get logger summary for status endpoints."""
        return {
            "task_id": self.task_id,
            "current_phase": self.current_phase,
            "started_at": self.started_at.isoformat(),
            "transition_count": len(self.history),
            "last_transition": {
                "from": self.history[-1].from_phase,
                "to": self.history[-1].to_phase,
                "reason": self.history[-1].reason,
                "timestamp": self.history[-1].timestamp.isoformat()
            } if self.history else None
        }
    
    def reset(self) -> None:
        """Reset to idle phase."""
        if self.current_phase != "idle":
            self.log_transition("idle", "reset")


# ============================================================================
# STATE CONTEXT (Kept - useful for passing data between agents)
# ============================================================================

class StateContext(BaseModel):
    """
    Context passed between agents during phase transitions.
    
    This contains all the information an agent needs to
    perform its task without accessing global state.
    """
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    current_phase: str = "idle"
    user_request: Optional[str] = None
    
    # Artifact references (not the artifacts themselves)
    available_artifacts: List[str] = Field(default_factory=list)
    required_outputs: List[str] = Field(default_factory=list)
    
    # Error context
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    fix_attempts: int = 0
    max_fix_attempts: int = 3
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    parameters: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# BACKWARD COMPATIBILITY (Deprecated - remove in future version)
# ============================================================================

class OrchestratorState(str, Enum):
    """
    DEPRECATED: Use Phase literals instead.
    
    Kept for backward compatibility with existing code.
    Will be removed in a future version.
    """
    IDLE = "idle"
    INTERPRETING = "interpreting"  # Mapped to "planning"
    PLANNING = "planning"
    CODING = "coding"
    VALIDATING = "validating"
    FIXING = "fixing"
    BUILDING = "building"
    COMPLETE = "complete"
    ESCALATED = "escalated"
    FAILED = "error"  # Mapped to "error"


class StateMachine(TransitionLogger):
    """
    DEPRECATED: Use TransitionLogger instead.
    
    This is a backward-compatible alias that provides the old interface.
    New code should use TransitionLogger directly.
    """
    
    # Kept for backward compatibility
    VALID_TRANSITIONS: Dict[str, List[str]] = {
        "idle": ["planning"],
        "planning": ["coding", "escalated"],
        "coding": ["validating", "fixing", "escalated"],
        "validating": ["building", "fixing", "escalated"],
        "fixing": ["validating", "escalated"],
        "building": ["complete", "fixing", "escalated"],
        "complete": ["idle"],
        "escalated": ["idle", "planning", "fixing"],
        "error": ["idle"],
    }
    
    @property
    def current_state(self) -> OrchestratorState:
        """Backward-compatible property."""
        try:
            return OrchestratorState(self.current_phase)
        except ValueError:
            return OrchestratorState.IDLE
    
    @current_state.setter
    def current_state(self, value: OrchestratorState) -> None:
        """Backward-compatible setter."""
        self.current_phase = value.value
    
    def can_transition(self, to_state: OrchestratorState) -> bool:
        """Check if transition is valid."""
        allowed = self.VALID_TRANSITIONS.get(self.current_phase, [])
        return to_state.value in allowed
    
    def transition(
        self,
        to_state: OrchestratorState,
        reason: TransitionReason,
        details: Optional[Dict[str, Any]] = None,
        skip_gates: bool = False
    ) -> StateTransition:
        """Backward-compatible transition method."""
        return self.log_transition(
            to_phase=to_state.value,
            reason=reason.value,
            details=details
        )
    
    def force_transition(self, to_state: OrchestratorState, reason: str) -> StateTransition:
        """Backward-compatible force transition."""
        return self.log_transition(
            to_phase=to_state.value,
            reason=f"forced:{reason}"
        )
    
    def register_exit_gate(self, state: OrchestratorState, gate_fn: Callable) -> None:
        """No-op for backward compatibility. Gates now handled in agent_graph.py."""
        pass
    
    def register_entry_gate(self, state: OrchestratorState, gate_fn: Callable) -> None:
        """No-op for backward compatibility. Gates now handled in agent_graph.py."""
        pass
    
    def check_exit_gate(self) -> tuple[bool, Dict[str, bool]]:
        """No-op - always passes."""
        return True, {}
    
    def check_entry_gate(self, to_state: OrchestratorState) -> tuple[bool, Dict[str, bool]]:
        """No-op - always passes."""
        return True, {}
