"""
ShipS* State Machine Enforcement

HARD RULES enforced as LOGIC, NOT INTELLIGENCE.

These are invariants that CANNOT be violated:
1. No skipping Validator
2. No Coder after Fixer without re-validation
3. No execution if Validator fails
4. No Fixer without Validation Report

This module provides deterministic state transitions
and guards that apply BEFORE any agent decisions.
"""

from typing import Optional, List, Dict, Any, Literal
from enum import Enum
from dataclasses import dataclass
from datetime import datetime


class PipelinePhase(str, Enum):
    """Hard states in the pipeline."""
    IDLE = "idle"
    PLANNING = "planning"
    PLAN_REVIEW = "plan_review"
    CODING = "coding"
    VALIDATING = "validating"
    VALIDATION_FAILED = "validation_failed"
    FIXING = "fixing"
    EXECUTION_READY = "execution_ready"
    EXECUTING = "executing"
    COMPLETE = "complete"
    ERROR = "error"
    ESCALATED = "escalated"


# ============================================================================
# TRANSITION TABLE - The law of the system
# ============================================================================

VALID_TRANSITIONS: Dict[PipelinePhase, List[PipelinePhase]] = {
    PipelinePhase.IDLE: [PipelinePhase.PLANNING],
    PipelinePhase.PLANNING: [PipelinePhase.PLAN_REVIEW, PipelinePhase.ERROR],
    PipelinePhase.PLAN_REVIEW: [PipelinePhase.CODING, PipelinePhase.PLANNING],
    PipelinePhase.CODING: [PipelinePhase.VALIDATING],  # MUST go to validator
    PipelinePhase.VALIDATING: [PipelinePhase.EXECUTION_READY, PipelinePhase.VALIDATION_FAILED],
    PipelinePhase.VALIDATION_FAILED: [PipelinePhase.FIXING, PipelinePhase.ESCALATED],
    PipelinePhase.FIXING: [PipelinePhase.VALIDATING, PipelinePhase.PLANNING, PipelinePhase.ESCALATED],  # MUST re-validate
    PipelinePhase.EXECUTION_READY: [PipelinePhase.EXECUTING],
    PipelinePhase.EXECUTING: [PipelinePhase.COMPLETE, PipelinePhase.VALIDATION_FAILED],
    PipelinePhase.COMPLETE: [PipelinePhase.IDLE],  # Can start a new task
    PipelinePhase.ERROR: [PipelinePhase.IDLE, PipelinePhase.ESCALATED],
    PipelinePhase.ESCALATED: [PipelinePhase.IDLE],  # User must intervene
}


# ============================================================================
# GUARD CONDITIONS - What must be true to transition
# ============================================================================

@dataclass
class TransitionGuard:
    """A guard condition for a state transition."""
    from_phase: PipelinePhase
    to_phase: PipelinePhase
    required_artifacts: List[str]
    condition_description: str


TRANSITION_GUARDS: List[TransitionGuard] = [
    TransitionGuard(
        from_phase=PipelinePhase.PLAN_REVIEW,
        to_phase=PipelinePhase.CODING,
        required_artifacts=["plan_manifest", "task_list", "folder_map"],
        condition_description="Plan must be complete with tasks and folder map"
    ),
    TransitionGuard(
        from_phase=PipelinePhase.CODING,
        to_phase=PipelinePhase.VALIDATING,
        required_artifacts=["file_change_set"],
        condition_description="Coder must produce file changes"
    ),
    TransitionGuard(
        from_phase=PipelinePhase.VALIDATING,
        to_phase=PipelinePhase.EXECUTION_READY,
        required_artifacts=["validation_report"],
        condition_description="Validation report must exist and show PASS"
    ),
    TransitionGuard(
        from_phase=PipelinePhase.VALIDATION_FAILED,
        to_phase=PipelinePhase.FIXING,
        required_artifacts=["validation_report"],
        condition_description="Validation report must exist to inform Fixer"
    ),
    TransitionGuard(
        from_phase=PipelinePhase.FIXING,
        to_phase=PipelinePhase.VALIDATING,
        required_artifacts=["fix_patch"],
        condition_description="Fixer must produce a patch before re-validation"
    ),
]


# ============================================================================
# STATE MACHINE ENFORCER
# ============================================================================

class StateMachineError(Exception):
    """Raised when state machine rules are violated."""
    pass


class PipelineStateMachine:
    """
    Hard state machine enforcer for the ShipS* pipeline.
    
    This is LOGIC, not intelligence. It enforces invariants
    that NO agent can violate.
    
    INVARIANTS:
    1. No skipping Validator after Coder
    2. No Coder after Fixer without re-validation
    3. No execution if Validator fails
    4. No Fixer without Validation Report
    """
    
    def __init__(self, max_fix_attempts: int = 3):
        self.current_phase = PipelinePhase.IDLE
        self.previous_phase: Optional[PipelinePhase] = None
        self.fix_attempts = 0
        self.max_fix_attempts = max_fix_attempts
        self.history: List[Dict[str, Any]] = []
        self.artifacts: Dict[str, Any] = {}
    
    def get_phase(self) -> PipelinePhase:
        """Get current pipeline phase."""
        return self.current_phase
    
    def can_transition(self, to_phase: PipelinePhase) -> tuple[bool, str]:
        """
        Check if a transition is valid.
        
        Returns:
            Tuple of (can_transition, reason)
        """
        # Check if transition is in valid transitions table
        valid_targets = VALID_TRANSITIONS.get(self.current_phase, [])
        if to_phase not in valid_targets:
            return False, f"Cannot transition from {self.current_phase.value} to {to_phase.value}"
        
        # Check guard conditions
        for guard in TRANSITION_GUARDS:
            if guard.from_phase == self.current_phase and guard.to_phase == to_phase:
                missing = [a for a in guard.required_artifacts if a not in self.artifacts]
                if missing:
                    return False, f"Missing required artifacts: {missing}"
        
        # Special invariants
        if to_phase == PipelinePhase.EXECUTION_READY:
            # INVARIANT: Cannot execute without passing validation
            validation_report = self.artifacts.get("validation_report", {})
            if validation_report.get("status") != "pass":
                return False, "Cannot proceed to execution without passing validation"
        
        if to_phase == PipelinePhase.FIXING:
            # INVARIANT: Cannot fix without validation failure
            if self.current_phase != PipelinePhase.VALIDATION_FAILED:
                return False, "Cannot invoke Fixer without validation failure"
            
            if self.fix_attempts >= self.max_fix_attempts:
                return False, f"Max fix attempts ({self.max_fix_attempts}) exceeded"
        
        return True, "OK"
    
    def transition(self, to_phase: PipelinePhase) -> None:
        """
        Execute a state transition.
        
        Raises:
            StateMachineError if transition is invalid
        """
        can, reason = self.can_transition(to_phase)
        if not can:
            raise StateMachineError(
                f"ILLEGAL TRANSITION: {self.current_phase.value} → {to_phase.value}. "
                f"Reason: {reason}"
            )
        
        # Track fix attempts
        if to_phase == PipelinePhase.FIXING:
            self.fix_attempts += 1
        
        # Reset fix counter on successful validation
        if to_phase == PipelinePhase.EXECUTION_READY:
            self.fix_attempts = 0
        
        # Record history
        self.history.append({
            "from": self.current_phase.value,
            "to": to_phase.value,
            "timestamp": datetime.utcnow().isoformat(),
            "fix_attempts": self.fix_attempts
        })
        
        self.previous_phase = self.current_phase
        self.current_phase = to_phase
    
    def register_artifact(self, artifact_id: str, artifact: Any) -> None:
        """Register an artifact for guard condition checking."""
        self.artifacts[artifact_id] = artifact
    
    def get_allowed_transitions(self) -> List[PipelinePhase]:
        """Get list of phases we can transition to from current phase."""
        allowed = []
        for phase in VALID_TRANSITIONS.get(self.current_phase, []):
            can, _ = self.can_transition(phase)
            if can:
                allowed.append(phase)
        return allowed
    
    def reset(self) -> None:
        """Reset the state machine to idle."""
        self.current_phase = PipelinePhase.IDLE
        self.previous_phase = None
        self.fix_attempts = 0
        self.artifacts = {}
        # Keep history for audit
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Get the transition history for audit."""
        return self.history


# ============================================================================
# EXECUTION GUARD - Prevents execution without validation
# ============================================================================

class ExecutionGuard:
    """
    Enforces the boundary between planning/coding and execution.
    
    RULES:
    1. No execution if Validator has not passed
    2. No shell commands from agents
    3. All execution must go through FastAPI endpoints
    """
    
    @staticmethod
    def can_execute(state_machine: PipelineStateMachine) -> tuple[bool, str]:
        """Check if we can proceed to execution."""
        # Must be in execution-ready phase
        if state_machine.current_phase != PipelinePhase.EXECUTION_READY:
            return False, f"Not ready for execution. Current phase: {state_machine.current_phase.value}"
        
        # Must have validation report with pass status
        validation_report = state_machine.artifacts.get("validation_report", {})
        if not validation_report:
            return False, "No validation report found"
        
        if validation_report.get("status") != "pass":
            return False, f"Validation status is {validation_report.get('status')}, not pass"
        
        return True, "OK"
    
    @staticmethod
    def get_execution_manifest(state_machine: PipelineStateMachine) -> Dict[str, Any]:
        """
        Get the execution manifest (what to execute).
        
        Only valid if ExecutionGuard.can_execute() returns True.
        """
        can, reason = ExecutionGuard.can_execute(state_machine)
        if not can:
            raise StateMachineError(f"Cannot get execution manifest: {reason}")
        
        return {
            "file_change_set": state_machine.artifacts.get("file_change_set"),
            "validation_report_id": state_machine.artifacts.get("validation_report", {}).get("id"),
            "approved_at": datetime.utcnow().isoformat(),
            "fix_attempts_used": state_machine.fix_attempts
        }
