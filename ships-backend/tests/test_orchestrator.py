"""
Tests for ShipS* Orchestrator

Comprehensive tests for:
- State Machine transitions
- Quality Gates
- Artifact Flow
- Error Recovery
- Main Orchestrator
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.orchestrator import (
    # State Machine
    StateMachine,
    OrchestratorState,
    TransitionReason,
    TransitionError,
    
    # Quality Gates
    QualityGate,
    QualityGateRegistry,
    GateCheck,
    GateCheckStatus,
    
    # Artifact Flow
    ArtifactRegistry,
    ArtifactStatus,
    ArtifactNotFound,
    ArtifactLocked,
    ArtifactStale,
    
    # Error Recovery
    ErrorRecoverySystem,
    ErrorType,
    RecoveryStatus,
)


class TestStateMachine:
    """Tests for the StateMachine."""
    
    def test_initial_state(self):
        """Test initial state is IDLE."""
        sm = StateMachine()
        assert sm.current_state == OrchestratorState.IDLE
    
    def test_valid_transition(self):
        """Test valid transition from IDLE to INTERPRETING."""
        sm = StateMachine()
        transition = sm.transition(
            OrchestratorState.INTERPRETING,
            TransitionReason.USER_REQUEST,
            skip_gates=True
        )
        
        assert sm.current_state == OrchestratorState.INTERPRETING
        assert transition.from_state == OrchestratorState.IDLE
        assert transition.to_state == OrchestratorState.INTERPRETING
    
    def test_invalid_transition(self):
        """Test invalid transition raises error."""
        sm = StateMachine()
        
        with pytest.raises(TransitionError):
            sm.transition(
                OrchestratorState.COMPLETE,  # Can't go from IDLE to COMPLETE
                TransitionReason.USER_REQUEST,
                skip_gates=True
            )
    
    def test_transition_history(self):
        """Test transition history is recorded."""
        sm = StateMachine()
        
        sm.transition(OrchestratorState.INTERPRETING, TransitionReason.USER_REQUEST, skip_gates=True)
        sm.transition(OrchestratorState.PLANNING, TransitionReason.REQUEST_INTERPRETED, skip_gates=True)
        
        history = sm.get_history()
        assert len(history) == 2
        assert history[0].to_state == OrchestratorState.INTERPRETING
        assert history[1].to_state == OrchestratorState.PLANNING
    
    def test_can_transition(self):
        """Test can_transition check."""
        sm = StateMachine()
        
        assert sm.can_transition(OrchestratorState.INTERPRETING)
        assert not sm.can_transition(OrchestratorState.COMPLETE)
    
    def test_force_transition(self):
        """Test force transition bypasses validation."""
        sm = StateMachine()
        
        # Force transition to FAILED (normally not allowed from IDLE)
        sm.force_transition(OrchestratorState.FAILED, "Test failure")
        
        assert sm.current_state == OrchestratorState.FAILED


class TestQualityGates:
    """Tests for the Quality Gates."""
    
    def test_create_gate(self):
        """Test creating a quality gate."""
        gate = QualityGate(name="Test Gate")
        gate.add_check("check1", "First check")
        gate.add_check("check2", "Second check")
        
        assert len(gate.checks) == 2
        assert gate.checks[0].name == "check1"
    
    def test_run_all_pass(self):
        """Test running all checks when all pass."""
        gate = QualityGate(name="Test Gate")
        gate.add_check("check1")
        gate.add_check("check2")
        
        check_fns = {
            "check1": lambda: (True, []),
            "check2": lambda: (True, [])
        }
        
        passed, results = gate.run_all(check_fns)
        
        assert passed is True
        assert results["check1"] is True
        assert results["check2"] is True
    
    def test_run_all_fail(self):
        """Test running all checks when one fails."""
        gate = QualityGate(name="Test Gate")
        gate.add_check("check1")
        gate.add_check("check2")
        
        check_fns = {
            "check1": lambda: (True, []),
            "check2": lambda: (False, ["Found TODO"])
        }
        
        passed, results = gate.run_all(check_fns)
        
        assert passed is False
        assert results["check1"] is True
        assert results["check2"] is False
    
    def test_get_failed_checks(self):
        """Test getting failed checks."""
        gate = QualityGate(name="Test Gate")
        check1 = gate.add_check("check1")
        check2 = gate.add_check("check2")
        
        check1.passed = True
        check2.passed = False
        check2.issues = ["Issue found"]
        
        failed = gate.get_failed_checks()
        
        assert len(failed) == 1
        assert failed[0].name == "check2"
    
    def test_registry_default_gates(self):
        """Test registry has default gates."""
        registry = QualityGateRegistry()
        
        planning_gate = registry.get_exit_gate(OrchestratorState.PLANNING)
        assert planning_gate is not None
        assert planning_gate.name == "Plan Quality"
        
        coding_gate = registry.get_exit_gate(OrchestratorState.CODING)
        assert coding_gate is not None
        assert coding_gate.name == "Code Quality"


class TestArtifactRegistry:
    """Tests for the Artifact Registry."""
    
    def test_register_and_get(self):
        """Test registering and retrieving an artifact."""
        registry = ArtifactRegistry()
        
        registry.register("plan", {"tasks": ["task1"]}, "Planner")
        
        artifact = registry.get("plan")
        assert artifact.artifact_type == "plan"
        assert artifact.data["tasks"] == ["task1"]
        assert artifact.produced_by == "Planner"
        assert artifact.version == 1
    
    def test_versioning(self):
        """Test artifact versioning."""
        registry = ArtifactRegistry()
        
        registry.register("plan", {"v": 1}, "Planner")
        registry.register("plan", {"v": 2}, "Planner")
        registry.register("plan", {"v": 3}, "Planner")
        
        latest = registry.get("plan")
        assert latest.version == 3
        assert latest.data["v"] == 3
        
        v1 = registry.get("plan", version=1)
        assert v1.version == 1
        assert v1.data["v"] == 1
    
    def test_locking(self):
        """Test artifact locking."""
        registry = ArtifactRegistry()
        registry.register("code", {}, "Coder")
        
        registry.lock("code", "Fixer")
        assert registry.is_locked("code")
        
        # Another agent can't lock
        with pytest.raises(ArtifactLocked):
            registry.lock("code", "OtherAgent")
        
        registry.unlock("code", "Fixer")
        assert not registry.is_locked("code")
    
    def test_dependency_invalidation(self):
        """Test dependent artifacts are invalidated."""
        registry = ArtifactRegistry()
        
        # Register plan first
        registry.register("plan", {"v": 1}, "Planner")
        
        # Register code that depends on plan
        registry.register("code_changes", {"v": 1}, "Coder")
        
        # Update plan - code should become stale
        registry.register("plan", {"v": 2}, "Planner")
        
        with pytest.raises(ArtifactStale):
            registry.get("code_changes")
    
    def test_artifact_not_found(self):
        """Test getting non-existent artifact raises error."""
        registry = ArtifactRegistry()
        
        with pytest.raises(ArtifactNotFound):
            registry.get("nonexistent")


class TestErrorRecovery:
    """Tests for the Error Recovery System."""
    
    def test_auto_fixable_retry(self):
        """Test auto-fixable error returns RETRY."""
        recovery = ErrorRecoverySystem()
        
        result = recovery.handle_error(
            ErrorType.VALIDATION_FAILED,
            "test_error_1",
            {"issues": ["TODO found"]}
        )
        
        assert result.status == RecoveryStatus.RETRY
        assert "Fixer" in result.message
    
    def test_max_attempts_escalation(self):
        """Test max attempts triggers escalation."""
        recovery = ErrorRecoverySystem()
        
        # Exhaust attempts
        for _ in range(3):
            recovery.handle_error(
                ErrorType.VALIDATION_FAILED,
                "test_error_2",
                {"issues": ["TODO found"]}
            )
        
        # Next attempt should escalate
        result = recovery.handle_error(
            ErrorType.VALIDATION_FAILED,
            "test_error_2",
            {"issues": ["TODO found"], "explanation": "Still failing"}
        )
        
        assert result.status == RecoveryStatus.ESCALATED
        assert len(result.options) > 0
    
    def test_immediate_escalation(self):
        """Test immediate escalation for ambiguous requests."""
        recovery = ErrorRecoverySystem()
        
        result = recovery.handle_error(
            ErrorType.AMBIGUOUS_REQUEST,
            "test_error_3",
            {"request": "make it better", "ambiguities": ["What?"], "questions": ["What?"]}
        )
        
        assert result.status == RecoveryStatus.ESCALATED
    
    def test_reset_attempts(self):
        """Test resetting attempts after recovery."""
        recovery = ErrorRecoverySystem()
        
        # Record some attempts
        recovery.record_attempt("error_1")
        recovery.record_attempt("error_1")
        
        assert recovery.get_attempts("error_1") == 2
        
        # Reset
        recovery.reset_attempts("error_1")
        
        assert recovery.get_attempts("error_1") == 0


class TestWorkflowIntegration:
    """Integration tests for the complete workflow."""
    
    def test_happy_path_transitions(self):
        """Test happy path state transitions."""
        sm = StateMachine()
        
        # User request -> INTERPRETING
        sm.transition(OrchestratorState.INTERPRETING, 
                     TransitionReason.USER_REQUEST, skip_gates=True)
        
        # Interpreted -> PLANNING
        sm.transition(OrchestratorState.PLANNING,
                     TransitionReason.REQUEST_INTERPRETED, skip_gates=True)
        
        # Plan approved -> CODING
        sm.transition(OrchestratorState.CODING,
                     TransitionReason.PLAN_APPROVED, skip_gates=True)
        
        # Code generated -> VALIDATING
        sm.transition(OrchestratorState.VALIDATING,
                     TransitionReason.CODE_GENERATED, skip_gates=True)
        
        # Validation passed -> BUILDING
        sm.transition(OrchestratorState.BUILDING,
                     TransitionReason.VALIDATION_PASSED, skip_gates=True)
        
        # Build succeeded -> COMPLETE
        sm.transition(OrchestratorState.COMPLETE,
                     TransitionReason.BUILD_SUCCEEDED, skip_gates=True)
        
        assert sm.current_state == OrchestratorState.COMPLETE
        assert len(sm.get_history()) == 6
    
    def test_fix_loop(self):
        """Test validation -> fixing -> validation loop."""
        sm = StateMachine()
        
        # Get to VALIDATING
        sm.transition(OrchestratorState.INTERPRETING, 
                     TransitionReason.USER_REQUEST, skip_gates=True)
        sm.transition(OrchestratorState.PLANNING,
                     TransitionReason.REQUEST_INTERPRETED, skip_gates=True)
        sm.transition(OrchestratorState.CODING,
                     TransitionReason.PLAN_APPROVED, skip_gates=True)
        sm.transition(OrchestratorState.VALIDATING,
                     TransitionReason.CODE_GENERATED, skip_gates=True)
        
        # Validation fails -> FIXING
        sm.transition(OrchestratorState.FIXING,
                     TransitionReason.VALIDATION_FAILED, skip_gates=True)
        
        # Fix applied -> back to VALIDATING
        sm.transition(OrchestratorState.VALIDATING,
                     TransitionReason.FIX_APPLIED, skip_gates=True)
        
        assert sm.current_state == OrchestratorState.VALIDATING


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
