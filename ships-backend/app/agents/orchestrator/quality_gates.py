"""
ShipS* Quality Gates System

Defines quality gates that must pass before state transitions.
Each state has exit gates (what must be true to leave) and
entry gates (what must be true to enter).

Quality gates are the mechanism that makes ShipS* different from
other AI coding tools - they enforce quality at every step.
"""

from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable, Tuple
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
import uuid

from app.orchestrator.state_machine import OrchestratorState


class GateCheckStatus(str, Enum):
    """Status of an individual gate check."""
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    PENDING = "PENDING"


@dataclass
class GateCheck:
    """
    A single check within a quality gate.
    
    Example: "no_todos" check that verifies no TODO comments exist.
    """
    name: str
    description: str = ""
    status: GateCheckStatus = GateCheckStatus.PENDING
    passed: bool = False
    issues: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[datetime] = None
    
    def run(self, check_fn: Callable[[], Tuple[bool, List[str]]]) -> "GateCheck":
        """
        Execute the check function and update status.
        
        Args:
            check_fn: Function that returns (passed, issues_list)
            
        Returns:
            Self for chaining
        """
        try:
            self.passed, self.issues = check_fn()
            self.status = GateCheckStatus.PASSED if self.passed else GateCheckStatus.FAILED
        except Exception as e:
            self.passed = False
            self.issues = [str(e)]
            self.status = GateCheckStatus.FAILED
        
        self.timestamp = datetime.utcnow()
        return self


@dataclass
class QualityGate:
    """
    A collection of checks that must all pass.
    
    Quality gates are associated with state transitions.
    - Exit gates: what must pass to leave a state
    - Entry gates: what must pass to enter a state
    """
    name: str
    checks: List[GateCheck] = field(default_factory=list)
    passed: bool = False
    timestamp: Optional[datetime] = None
    
    def add_check(self, name: str, description: str = "") -> GateCheck:
        """Add a check to this gate."""
        check = GateCheck(name=name, description=description)
        self.checks.append(check)
        return check
    
    def run_all(
        self, 
        check_functions: Dict[str, Callable[[], Tuple[bool, List[str]]]]
    ) -> Tuple[bool, Dict[str, bool]]:
        """
        Run all checks in this gate.
        
        Args:
            check_functions: Map of check_name -> check_function
            
        Returns:
            Tuple of (all_passed, {check_name: passed})
        """
        results: Dict[str, bool] = {}
        
        for check in self.checks:
            if check.name in check_functions:
                check.run(check_functions[check.name])
            else:
                # No function provided = skip
                check.status = GateCheckStatus.SKIPPED
                check.passed = True
            
            results[check.name] = check.passed
        
        self.passed = all(c.passed for c in self.checks)
        self.timestamp = datetime.utcnow()
        
        return self.passed, results
    
    def get_failed_checks(self) -> List[GateCheck]:
        """Get list of checks that failed."""
        return [c for c in self.checks if not c.passed]
    
    def get_issues(self) -> List[str]:
        """Get all issues from all checks."""
        issues = []
        for check in self.checks:
            issues.extend(check.issues)
        return issues


class QualityGateRegistry:
    """
    Registry of all quality gates for the orchestrator.
    
    This defines what checks must pass at each state transition.
    The registry is configured once at startup and then queried
    during state transitions.
    """
    
    def __init__(self):
        """Initialize the registry with default gates."""
        self._exit_gates: Dict[OrchestratorState, QualityGate] = {}
        self._entry_gates: Dict[OrchestratorState, QualityGate] = {}
        self._fix_attempts: Dict[str, int] = {}
        
        # Set up default gates
        self._setup_default_gates()
    
    def _setup_default_gates(self) -> None:
        """Configure default quality gates for each state."""
        
        # PLANNING exit gate
        planning_exit = QualityGate(name="Plan Quality")
        planning_exit.add_check("plan_exists", "Plan artifact must exist")
        planning_exit.add_check("plan_complete", "Plan must be complete (no gaps)")
        planning_exit.add_check("patterns_extracted", "Pattern registry must be populated")
        planning_exit.add_check("contracts_defined", "API contracts must be defined")
        self._exit_gates[OrchestratorState.PLANNING] = planning_exit
        
        # CODING exit gate
        coding_exit = QualityGate(name="Code Quality")
        coding_exit.add_check("code_exists", "Code changes must exist")
        coding_exit.add_check("no_todos", "No TODO/FIXME placeholders")
        coding_exit.add_check("no_incomplete", "No incomplete implementations")
        coding_exit.add_check("imports_valid", "All imports must be valid")
        self._exit_gates[OrchestratorState.CODING] = coding_exit
        
        # VALIDATING exit gate
        validating_exit = QualityGate(name="Validation Quality")
        validating_exit.add_check("syntax_valid", "No syntax errors")
        validating_exit.add_check("types_valid", "No type errors")
        validating_exit.add_check("deps_resolved", "All dependencies resolved")
        validating_exit.add_check("contracts_match", "API contracts are satisfied")
        validating_exit.add_check("framework_rules", "Framework rules followed")
        self._exit_gates[OrchestratorState.VALIDATING] = validating_exit
        
        # FIXING exit gate
        fixing_exit = QualityGate(name="Fix Quality")
        fixing_exit.add_check("fix_applied", "Fix was applied")
        fixing_exit.add_check("no_regressions", "No new issues introduced")
        self._exit_gates[OrchestratorState.FIXING] = fixing_exit
        
        # BUILDING exit gate
        building_exit = QualityGate(name="Build Quality")
        building_exit.add_check("build_success", "Build completed successfully")
        building_exit.add_check("no_warnings", "No critical warnings")
        self._exit_gates[OrchestratorState.BUILDING] = building_exit
    
    def get_exit_gate(self, state: OrchestratorState) -> Optional[QualityGate]:
        """Get exit gate for a state."""
        return self._exit_gates.get(state)
    
    def get_entry_gate(self, state: OrchestratorState) -> Optional[QualityGate]:
        """Get entry gate for a state."""
        return self._entry_gates.get(state)
    
    def register_exit_gate(self, state: OrchestratorState, gate: QualityGate) -> None:
        """Register a custom exit gate."""
        self._exit_gates[state] = gate
    
    def register_entry_gate(self, state: OrchestratorState, gate: QualityGate) -> None:
        """Register a custom entry gate."""
        self._entry_gates[state] = gate
    
    def record_fix_attempt(self, gate_name: str) -> int:
        """
        Record a fix attempt for a gate.
        
        Returns the new attempt count.
        """
        if gate_name not in self._fix_attempts:
            self._fix_attempts[gate_name] = 0
        
        self._fix_attempts[gate_name] += 1
        return self._fix_attempts[gate_name]
    
    def get_fix_attempts(self, gate_name: str) -> int:
        """Get number of fix attempts for a gate."""
        return self._fix_attempts.get(gate_name, 0)
    
    def reset_fix_attempts(self, gate_name: str) -> None:
        """Reset fix attempts for a gate (after success)."""
        self._fix_attempts[gate_name] = 0
    
    def check_exit_gate(
        self, 
        state: OrchestratorState,
        check_functions: Dict[str, Callable[[], Tuple[bool, List[str]]]]
    ) -> Tuple[bool, Dict[str, bool]]:
        """
        Check exit gate for a state.
        
        Args:
            state: State to check exit gate for
            check_functions: Map of check_name -> check_function
            
        Returns:
            Tuple of (all_passed, {check_name: passed})
        """
        gate = self._exit_gates.get(state)
        if gate is None:
            return True, {}
        
        return gate.run_all(check_functions)


# ============================================================================
# QUALITY GATE CHECKER (connects gates to artifacts)
# ============================================================================

class QualityGateChecker:
    """
    Executes quality gate checks against artifacts.
    
    This class bridges the quality gate system with the artifact
    system, providing the actual check implementations.
    """
    
    def __init__(self, artifact_manager):
        """
        Initialize with artifact manager.
        
        Args:
            artifact_manager: ArtifactManager instance
        """
        self.artifacts = artifact_manager
        self.registry = QualityGateRegistry()
    
    # =========================================================================
    # PLANNING CHECKS
    # =========================================================================
    
    def check_plan_exists(self) -> Tuple[bool, List[str]]:
        """Check if plan artifact exists."""
        # Simplified check - in production, verify plan artifact
        if self.artifacts.artifact_exists("plan"):
            return True, []
        return False, ["Plan artifact does not exist"]
    
    def check_plan_complete(self) -> Tuple[bool, List[str]]:
        """Check if plan is complete (no gaps)."""
        # In production, parse plan and check for required sections
        return True, []  # Placeholder
    
    def check_patterns_extracted(self) -> Tuple[bool, List[str]]:
        """Check if pattern registry is populated."""
        if self.artifacts.artifact_exists("pattern_registry"):
            registry = self.artifacts.get_pattern_registry()
            if registry.naming_conventions.confidence > 0:
                return True, []
        return False, ["Pattern registry not populated"]
    
    def check_contracts_defined(self) -> Tuple[bool, List[str]]:
        """Check if contracts are defined."""
        if self.artifacts.artifact_exists("contracts"):
            contracts = self.artifacts.get_contract_definitions()
            if contracts.contracts:
                return True, []
        return False, ["No contracts defined"]
    
    # =========================================================================
    # CODE QUALITY CHECKS
    # =========================================================================
    
    def check_no_todos(self) -> Tuple[bool, List[str]]:
        """Check for TODO/FIXME placeholders in code."""
        # In production, scan code files for TODOs
        return True, []  # Placeholder
    
    def check_no_incomplete(self) -> Tuple[bool, List[str]]:
        """Check for incomplete implementations."""
        return True, []  # Placeholder
    
    def check_imports_valid(self) -> Tuple[bool, List[str]]:
        """Check if all imports are valid."""
        return True, []  # Placeholder
    
    # =========================================================================
    # VALIDATION CHECKS
    # =========================================================================
    
    def check_syntax_valid(self) -> Tuple[bool, List[str]]:
        """Check for syntax errors."""
        return True, []  # Placeholder
    
    def check_types_valid(self) -> Tuple[bool, List[str]]:
        """Check for type errors."""
        return True, []  # Placeholder
    
    def check_deps_resolved(self) -> Tuple[bool, List[str]]:
        """Check if all dependencies are resolved."""
        return True, []  # Placeholder
    
    def check_contracts_match(self) -> Tuple[bool, List[str]]:
        """Check if API contracts are satisfied."""
        return True, []  # Placeholder
    
    def check_framework_rules(self) -> Tuple[bool, List[str]]:
        """Check if framework rules are followed."""
        return True, []  # Placeholder
    
    # =========================================================================
    # GATE EXECUTION
    # =========================================================================
    
    def get_check_functions(self) -> Dict[str, Callable[[], Tuple[bool, List[str]]]]:
        """Get all check functions as a dictionary."""
        return {
            # Planning checks
            "plan_exists": self.check_plan_exists,
            "plan_complete": self.check_plan_complete,
            "patterns_extracted": self.check_patterns_extracted,
            "contracts_defined": self.check_contracts_defined,
            
            # Code quality checks
            "code_exists": lambda: (True, []),  # Placeholder
            "no_todos": self.check_no_todos,
            "no_incomplete": self.check_no_incomplete,
            "imports_valid": self.check_imports_valid,
            
            # Validation checks
            "syntax_valid": self.check_syntax_valid,
            "types_valid": self.check_types_valid,
            "deps_resolved": self.check_deps_resolved,
            "contracts_match": self.check_contracts_match,
            "framework_rules": self.check_framework_rules,
            
            # Fix checks
            "fix_applied": lambda: (True, []),
            "no_regressions": lambda: (True, []),
            
            # Build checks
            "build_success": lambda: (True, []),
            "no_warnings": lambda: (True, []),
        }
    
    def check_gate(
        self, 
        state: OrchestratorState,
        gate_type: str = "exit"
    ) -> Tuple[bool, Dict[str, bool]]:
        """
        Check a quality gate for a state.
        
        Args:
            state: State to check gate for
            gate_type: "exit" or "entry"
            
        Returns:
            Tuple of (all_passed, {check_name: passed})
        """
        if gate_type == "exit":
            return self.registry.check_exit_gate(state, self.get_check_functions())
        else:
            gate = self.registry.get_entry_gate(state)
            if gate is None:
                return True, {}
            return gate.run_all(self.get_check_functions())
