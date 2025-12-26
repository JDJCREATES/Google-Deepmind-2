"""
ShipS* Orchestrator State Machine

Defines the core state machine for the orchestrator, providing:
- Deterministic state transitions
- Transition validation and logging
- State history for debugging

States:
    IDLE → PLANNING → CODING → VALIDATING → COMPLETE
                        ↓           ↓
                     FIXING ←───────┘
                        ↓
                   ESCALATED (if max retries exceeded)
"""

from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
import uuid

from pydantic import BaseModel, Field


class OrchestratorState(str, Enum):
    """
    States of the orchestrator state machine.
    
    Each state represents a phase in the code generation workflow.
    """
    IDLE = "IDLE"                   # Waiting for user request
    INTERPRETING = "INTERPRETING"   # Request Interpreter processing
    PLANNING = "PLANNING"           # Planner generating plan
    CODING = "CODING"               # Coder generating code
    VALIDATING = "VALIDATING"       # Validators checking code
    FIXING = "FIXING"               # Fixer addressing issues
    BUILDING = "BUILDING"           # Build system compiling
    COMPLETE = "COMPLETE"           # Task successfully finished
    ESCALATED = "ESCALATED"         # User intervention required
    FAILED = "FAILED"               # Unrecoverable failure


class TransitionReason(str, Enum):
    """Reasons for state transitions."""
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


@dataclass
class StateTransition:
    """Record of a single state transition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    from_state: OrchestratorState = OrchestratorState.IDLE
    to_state: OrchestratorState = OrchestratorState.IDLE
    reason: TransitionReason = TransitionReason.USER_REQUEST
    details: Dict[str, Any] = field(default_factory=dict)
    gate_results: Dict[str, bool] = field(default_factory=dict)


class TransitionError(Exception):
    """Raised when a state transition is invalid."""
    def __init__(self, from_state: OrchestratorState, to_state: OrchestratorState, reason: str):
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        super().__init__(f"Cannot transition from {from_state} to {to_state}: {reason}")


class StateMachine:
    """
    Deterministic state machine for the orchestrator.
    
    This class manages state transitions with:
    - Valid transition enforcement
    - Exit/entry gate checking
    - Transition history logging
    
    The state machine does NOT think - it only routes based on
    deterministic rules and gate check results.
    """
    
    # Valid transitions: from_state -> [allowed_to_states]
    VALID_TRANSITIONS: Dict[OrchestratorState, List[OrchestratorState]] = {
        OrchestratorState.IDLE: [
            OrchestratorState.INTERPRETING,
        ],
        OrchestratorState.INTERPRETING: [
            OrchestratorState.PLANNING,
            OrchestratorState.ESCALATED,  # If ambiguous request
        ],
        OrchestratorState.PLANNING: [
            OrchestratorState.CODING,
            OrchestratorState.ESCALATED,  # If plan rejected
        ],
        OrchestratorState.CODING: [
            OrchestratorState.VALIDATING,
            OrchestratorState.FIXING,     # If immediate issues detected
            OrchestratorState.ESCALATED,
        ],
        OrchestratorState.VALIDATING: [
            OrchestratorState.BUILDING,   # All validations passed
            OrchestratorState.FIXING,     # Validation failed
            OrchestratorState.ESCALATED,
        ],
        OrchestratorState.FIXING: [
            OrchestratorState.VALIDATING, # Re-validate after fix
            OrchestratorState.ESCALATED,  # Max retries exceeded
        ],
        OrchestratorState.BUILDING: [
            OrchestratorState.COMPLETE,   # Build succeeded
            OrchestratorState.FIXING,     # Build failed
            OrchestratorState.ESCALATED,
        ],
        OrchestratorState.COMPLETE: [
            OrchestratorState.IDLE,       # Ready for next request
        ],
        OrchestratorState.ESCALATED: [
            OrchestratorState.IDLE,       # User resolved, start fresh
            OrchestratorState.PLANNING,   # User provided more info
            OrchestratorState.FIXING,     # User made manual fix
        ],
        OrchestratorState.FAILED: [
            OrchestratorState.IDLE,       # Start over
        ],
    }
    
    def __init__(self, task_id: Optional[str] = None):
        """
        Initialize the state machine.
        
        Args:
            task_id: Optional task identifier for tracking
        """
        self.task_id = task_id or str(uuid.uuid4())
        self.current_state = OrchestratorState.IDLE
        self.history: List[StateTransition] = []
        self.started_at = datetime.utcnow()
        
        # Gate callbacks (set by orchestrator)
        self._exit_gates: Dict[OrchestratorState, Callable[[], tuple[bool, Dict[str, bool]]]] = {}
        self._entry_gates: Dict[OrchestratorState, Callable[[], tuple[bool, Dict[str, bool]]]] = {}
    
    def register_exit_gate(
        self, 
        state: OrchestratorState, 
        gate_fn: Callable[[], tuple[bool, Dict[str, bool]]]
    ) -> None:
        """
        Register an exit gate for a state.
        
        The gate function should return (passed, check_results).
        
        Args:
            state: State to register exit gate for
            gate_fn: Function that returns (passed, {check_name: passed})
        """
        self._exit_gates[state] = gate_fn
    
    def register_entry_gate(
        self, 
        state: OrchestratorState, 
        gate_fn: Callable[[], tuple[bool, Dict[str, bool]]]
    ) -> None:
        """
        Register an entry gate for a state.
        
        Args:
            state: State to register entry gate for
            gate_fn: Function that returns (passed, {check_name: passed})
        """
        self._entry_gates[state] = gate_fn
    
    def can_transition(self, to_state: OrchestratorState) -> bool:
        """
        Check if transition to target state is valid.
        
        Args:
            to_state: Target state
            
        Returns:
            True if transition is allowed
        """
        allowed = self.VALID_TRANSITIONS.get(self.current_state, [])
        return to_state in allowed
    
    def check_exit_gate(self) -> tuple[bool, Dict[str, bool]]:
        """
        Check the exit gate for the current state.
        
        Returns:
            Tuple of (all_passed, individual_check_results)
        """
        gate_fn = self._exit_gates.get(self.current_state)
        if gate_fn is None:
            return True, {}  # No gate = always pass
        
        return gate_fn()
    
    def check_entry_gate(self, to_state: OrchestratorState) -> tuple[bool, Dict[str, bool]]:
        """
        Check the entry gate for a target state.
        
        Args:
            to_state: State we're trying to enter
            
        Returns:
            Tuple of (all_passed, individual_check_results)
        """
        gate_fn = self._entry_gates.get(to_state)
        if gate_fn is None:
            return True, {}  # No gate = always pass
        
        return gate_fn()
    
    def transition(
        self, 
        to_state: OrchestratorState, 
        reason: TransitionReason,
        details: Optional[Dict[str, Any]] = None,
        skip_gates: bool = False
    ) -> StateTransition:
        """
        Attempt to transition to a new state.
        
        This is the core method. It:
        1. Validates the transition is allowed
        2. Checks exit gate of current state
        3. Checks entry gate of target state
        4. Logs the transition
        5. Updates current state
        
        Args:
            to_state: Target state
            reason: Why we're transitioning
            details: Additional context
            skip_gates: Skip gate checks (for error recovery)
            
        Returns:
            StateTransition record
            
        Raises:
            TransitionError: If transition is invalid or gates fail
        """
        details = details or {}
        gate_results: Dict[str, bool] = {}
        
        # Validate transition is allowed
        if not self.can_transition(to_state):
            raise TransitionError(
                self.current_state,
                to_state,
                f"Transition not allowed from {self.current_state}"
            )
        
        if not skip_gates:
            # Check exit gate
            exit_passed, exit_results = self.check_exit_gate()
            gate_results.update({f"exit_{k}": v for k, v in exit_results.items()})
            
            if not exit_passed:
                raise TransitionError(
                    self.current_state,
                    to_state,
                    f"Exit gate failed: {exit_results}"
                )
            
            # Check entry gate
            entry_passed, entry_results = self.check_entry_gate(to_state)
            gate_results.update({f"entry_{k}": v for k, v in entry_results.items()})
            
            if not entry_passed:
                raise TransitionError(
                    self.current_state,
                    to_state,
                    f"Entry gate failed: {entry_results}"
                )
        
        # Create transition record
        transition = StateTransition(
            from_state=self.current_state,
            to_state=to_state,
            reason=reason,
            details=details,
            gate_results=gate_results
        )
        
        # Log and transition
        self.history.append(transition)
        self.current_state = to_state
        
        return transition
    
    def force_transition(
        self, 
        to_state: OrchestratorState, 
        reason: str
    ) -> StateTransition:
        """
        Force a transition without validation (for error recovery).
        
        Use sparingly - only for error states.
        
        Args:
            to_state: Target state
            reason: Why we're forcing
            
        Returns:
            StateTransition record
        """
        transition = StateTransition(
            from_state=self.current_state,
            to_state=to_state,
            reason=TransitionReason.UNRECOVERABLE_ERROR,
            details={"forced_reason": reason}
        )
        
        self.history.append(transition)
        self.current_state = to_state
        
        return transition
    
    def reset(self) -> None:
        """Reset state machine to IDLE."""
        if self.current_state != OrchestratorState.IDLE:
            self.transition(
                OrchestratorState.IDLE,
                TransitionReason.USER_CANCELLED,
                skip_gates=True
            )
    
    def get_history(self) -> List[StateTransition]:
        """Get full transition history."""
        return self.history.copy()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get state machine summary."""
        return {
            "task_id": self.task_id,
            "current_state": self.current_state.value,
            "started_at": self.started_at.isoformat(),
            "transition_count": len(self.history),
            "last_transition": self.history[-1] if self.history else None
        }


# ============================================================================
# STATE CONTEXT (for passing between agents)
# ============================================================================

class StateContext(BaseModel):
    """
    Context passed between agents during state transitions.
    
    This contains all the information an agent needs to
    perform its task without accessing global state.
    """
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    current_state: OrchestratorState = OrchestratorState.IDLE
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
    
    class Config:
        use_enum_values = True
