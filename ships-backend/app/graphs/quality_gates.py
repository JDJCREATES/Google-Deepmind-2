"""
Quality Gates System for Agent Orchestration
============================================

Implements quality gates that enforce state transition rules.
Prevents agents from proceeding until quality criteria are met.

Design Philosophy:
- Prevention > Detection > Repair
- Deterministic gate checks (no LLM needed)
- Self-healing through automatic fixer invocation
- Max 3 fix attempts before escalation

Based on: original design docs/CLAUDE-ORCHESTRATOR-PLAN.md
"""

from typing import Dict, List, Any, Optional, Callable, Literal
from dataclasses import dataclass
from datetime import datetime
import hashlib
from app.core.logger import get_logger

logger = get_logger("quality_gates")


@dataclass
class GateCheck:
    """Individual quality check within a gate."""
    name: str
    description: str
    check_fn: Callable[[Dict[str, Any]], bool]
    error_message: str
    

@dataclass
class GateResult:
    """Result of a quality gate check."""
    gate_name: str
    passed: bool
    checks_passed: List[str]
    checks_failed: List[str]
    error_details: Dict[str, str]
    timestamp: str
    
    def get_failed_checks(self) -> List[str]:
        """Get list of failed check names."""
        return self.checks_failed


class QualityGate:
    """
    Quality gate that must pass before state transitions.
    
    Each gate has multiple checks. ALL checks must pass for gate to pass.
    """
    
    def __init__(self, name: str, description: str, checks: List[GateCheck]):
        self.name = name
        self.description = description
        self.checks = checks
        
    def evaluate(self, state: Dict[str, Any]) -> GateResult:
        """
        Evaluate all checks in this gate.
        
        Args:
            state: Current agent graph state
            
        Returns:
            GateResult with pass/fail status and details
        """
        checks_passed = []
        checks_failed = []
        error_details = {}
        
        for check in self.checks:
            try:
                result = check.check_fn(state)
                if result:
                    checks_passed.append(check.name)
                    logger.debug(f"[GATE:{self.name}] ✅ {check.name}")
                else:
                    checks_failed.append(check.name)
                    error_details[check.name] = check.error_message
                    logger.warning(f"[GATE:{self.name}] ❌ {check.name}: {check.error_message}")
            except Exception as e:
                checks_failed.append(check.name)
                error_details[check.name] = f"Check error: {str(e)}"
                logger.error(f"[GATE:{self.name}] ⚠️ {check.name} threw exception: {e}")
        
        passed = len(checks_failed) == 0
        
        result = GateResult(
            gate_name=self.name,
            passed=passed,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            error_details=error_details,
            timestamp=datetime.now().isoformat()
        )
        
        if passed:
            logger.info(f"[GATE:{self.name}] ✅ PASSED - All {len(checks_passed)} checks passed")
        else:
            logger.warning(f"[GATE:{self.name}] ❌ FAILED - {len(checks_failed)}/{len(self.checks)} checks failed")
        
        return result
    
    @staticmethod
    def always_pass() -> 'QualityGate':
        """Gate that always passes (for states with no requirements)."""
        return QualityGate(
            name="AlwaysPass",
            description="No quality requirements",
            checks=[]
        )


# ============================================================================
# GATE CHECK FUNCTIONS
# ============================================================================

def check_plan_exists(state: Dict[str, Any]) -> bool:
    """Check if a plan artifact exists."""
    artifacts = state.get("artifacts", {})
    # Check for both 'plan' (legacy) and 'plan_manifest' (new)
    plan = artifacts.get("plan") or artifacts.get("plan_manifest")
    return plan is not None and len(plan) > 0


def check_plan_complete(state: Dict[str, Any]) -> bool:
    """Check if plan has all required sections AND has actual tasks."""
    artifacts = state.get("artifacts", {})
    
    # NEW: Check task_list for actual tasks (CRITICAL)
    task_list = artifacts.get("task_list", {})
    tasks = task_list.get("tasks", [])
    
    # CRITICAL: Plan must have at least 1 task
    if not tasks or len(tasks) == 0:
        logger.warning("[GATE] Plan has ZERO tasks - invalid")
        return False
    
    # Check for folder_map
    folder_map = artifacts.get("folder_map", {})
    if not folder_map.get("entries"):
        logger.warning("[GATE] Plan has no folder structure - invalid")
        return False
    
    logger.info(f"[GATE] Plan validation passed: {len(tasks)} tasks, {len(folder_map.get('entries', []))} files")
    return True


def check_scaffolding_complete(state: Dict[str, Any]) -> bool:
    """Check if scaffolding phase completed OR was validly skipped."""
    artifacts = state.get("artifacts", {})
    
    # Check if scaffolding is complete
    if artifacts.get("scaffolding_complete", False):
        return True
    
    # Check if scaffolding was validly skipped (feature/fix requests)
    if artifacts.get("scaffolding_skipped", False):
        logger.info("[GATE] Scaffolding skipped (feature/fix request)")
        return True
    
    # Check if intent scope doesn't require scaffolding
    intent = artifacts.get("structured_intent", {})
    scope = intent.get("scope", "feature")
    
    if scope in ["feature", "component", "file", "layer"]:
        logger.info(f"[GATE] Scaffolding not needed for scope: {scope}")
        return True
    
    logger.warning("[GATE] Scaffolding required but not complete")
    return False


def check_implementation_started(state: Dict[str, Any]) -> bool:
    """Check if coding has begun."""
    completed_files = state.get("completed_files", [])
    return len(completed_files) > 0


def check_implementation_complete(state: Dict[str, Any]) -> bool:
    """Check if all planned files are implemented."""
    return state.get("implementation_complete", False)


def check_files_written(state: Dict[str, Any]) -> bool:
    """Check if any files were successfully written."""
    completed_files = state.get("completed_files", [])
    return len(completed_files) > 0


def check_validation_passed(state: Dict[str, Any]) -> bool:
    """Check if validation completed successfully."""
    # String literal match to avoid circular import with agent_graph.py
    return state.get("validation_status") == "passed"


def check_validation_failed(state: Dict[str, Any]) -> bool:
    """Check if validation failed (recoverable only)."""
    status = state.get("validation_status")
    return status == "failed_recoverable"


def check_no_critical_errors(state: Dict[str, Any]) -> bool:
    """Check if there are no blocking errors."""
    error_log = state.get("error_log", [])
    
    # No errors at all
    if not error_log:
        return True
    
    # Check for critical error markers
    critical_keywords = ["SyntaxError", "ImportError", "ModuleNotFoundError", "CRITICAL"]
    
    for error in error_log:
        error_str = str(error).lower()
        if any(keyword.lower() in error_str for keyword in critical_keywords):
            return False
    
    return True


def check_fix_attempts_not_exceeded(state: Dict[str, Any]) -> bool:
    """Check if fix attempts are below max limit."""
    fix_attempts = state.get("fix_attempts", 0)
    max_attempts = state.get("max_fix_attempts", 3)
    return fix_attempts < max_attempts


def check_no_loops_detected(state: Dict[str, Any]) -> bool:
    """Check if loop detection has not flagged infinite loops."""
    loop_detection = state.get("loop_detection", {})
    return not loop_detection.get("loop_detected", False)


def check_project_path_exists(state: Dict[str, Any]) -> bool:
    """Check if project path is configured."""
    artifacts = state.get("artifacts", {})
    project_path = artifacts.get("project_path")
    return project_path is not None and project_path != ""


def check_not_waiting(state: Dict[str, Any]) -> bool:
    """Check if agent is not in waiting state."""
    phase = state.get("phase", "")
    return phase != "waiting"


def check_user_confirmed(state: Dict[str, Any]) -> bool:
    """Check if user provided confirmation when needed."""
    # If there's a pending intent, user should have confirmed
    artifacts = state.get("artifacts", {})
    pending_intent = artifacts.get("pending_new_intent")
    
    if not pending_intent:
        return True  # No confirmation needed
    
    # Check if user sent a confirmation message
    messages = state.get("messages", [])
    if not messages:
        return False
    
    last_msg = messages[-1]
    content = str(last_msg.content).lower() if hasattr(last_msg, 'content') else ""
    
    # Look for confirmation keywords
    return any(keyword in content for keyword in ["add", "replace", "new folder", "yes", "confirm"])


# ============================================================================
# QUALITY GATE DEFINITIONS
# ============================================================================

class QualityGates:
    """Registry of all quality gates in the system."""
    
    # EXIT GATES (must pass to LEAVE a state)
    
    @staticmethod
    def planning_exit_gate() -> QualityGate:
        """Gate to exit PLANNING state."""
        return QualityGate(
            name="PlanningExit",
            description="Requirements to complete planning phase",
            checks=[
                GateCheck(
                    name="plan_exists",
                    description="Plan artifact must exist",
                    check_fn=check_plan_exists,
                    error_message="No plan artifact found. Planner must create a plan."
                ),
                GateCheck(
                    name="plan_complete",
                    description="Plan must have required sections",
                    check_fn=check_plan_complete,
                    error_message="Plan is incomplete. Must have tasks, architecture, or files_to_create."
                ),
                GateCheck(
                    name="scaffolding_complete",
                    description="Project scaffolding must be done",
                    check_fn=check_scaffolding_complete,
                    error_message="Scaffolding incomplete. Planner must set scaffolding_complete flag."
                ),
                GateCheck(
                    name="project_path_valid",
                    description="Project path must be configured",
                    check_fn=check_project_path_exists,
                    error_message="No project path configured."
                )
            ]
        )
    
    @staticmethod
    def coding_exit_gate() -> QualityGate:
        """Gate to exit CODING state."""
        return QualityGate(
            name="CodingExit",
            description="Requirements to complete coding phase",
            checks=[
                GateCheck(
                    name="implementation_complete",
                    description="All planned files must be implemented",
                    check_fn=check_implementation_complete,
                    error_message="Implementation not complete. Coder must finish all files."
                ),
                GateCheck(
                    name="files_written",
                    description="At least one file must be written",
                    check_fn=check_files_written,
                    error_message="No files were written. Coder must produce code."
                ),
                GateCheck(
                    name="not_waiting",
                    description="Coder must not be waiting for locks",
                    check_fn=check_not_waiting,
                    error_message="Coder is waiting for file locks to release."
                )
            ]
        )
    
    @staticmethod
    def validation_exit_gate() -> QualityGate:
        """Gate to exit VALIDATION state."""
        return QualityGate(
            name="ValidationExit",
            description="Requirements to complete validation phase",
            checks=[
                GateCheck(
                    name="validation_passed",
                    description="Validation must pass with no errors",
                    check_fn=check_validation_passed,
                    error_message="Validation failed. Code has errors that need fixing."
                ),
                GateCheck(
                    name="no_critical_errors",
                    description="No critical errors in error log",
                    check_fn=check_no_critical_errors,
                    error_message="Critical errors detected in error log."
                )
            ]
        )
    
    @staticmethod
    def fixing_exit_gate() -> QualityGate:
        """Gate to exit FIXING state."""
        return QualityGate(
            name="FixingExit",
            description="Requirements to complete fixing phase",
            checks=[
                GateCheck(
                    name="fix_attempts_valid",
                    description="Fix attempts must be below max limit",
                    check_fn=check_fix_attempts_not_exceeded,
                    error_message="Max fix attempts exceeded. Need to escalate to user."
                ),
                GateCheck(
                    name="not_waiting",
                    description="Fixer must not be waiting for locks",
                    check_fn=check_not_waiting,
                    error_message="Fixer is waiting for file locks to release."
                )
            ]
        )
    
    # ENTRY GATES (must pass to ENTER a state)
    
    @staticmethod
    def coding_entry_gate() -> QualityGate:
        """Gate to enter CODING state."""
        return QualityGate(
            name="CodingEntry",
            description="Requirements to start coding phase",
            checks=[
                GateCheck(
                    name="plan_exists",
                    description="Must have a plan before coding",
                    check_fn=check_plan_exists,
                    error_message="Cannot code without a plan."
                ),
                GateCheck(
                    name="project_path_valid",
                    description="Project path must be set",
                    check_fn=check_project_path_exists,
                    error_message="Cannot code without project path."
                )
            ]
        )
    
    @staticmethod
    def validation_entry_gate() -> QualityGate:
        """Gate to enter VALIDATION state."""
        return QualityGate(
            name="ValidationEntry",
            description="Requirements to start validation phase",
            checks=[
                GateCheck(
                    name="files_written",
                    description="Must have written files to validate",
                    check_fn=check_files_written,
                    error_message="Cannot validate without any code files."
                )
            ]
        )
    
    @staticmethod
    def fixing_entry_gate() -> QualityGate:
        """Gate to enter FIXING state."""
        return QualityGate(
            name="FixingEntry",
            description="Requirements to start fixing phase",
            checks=[
                GateCheck(
                    name="validation_failed",
                    description="Validation must have failed",
                    check_fn=check_validation_failed,
                    error_message="Cannot fix if validation passed or pending."
                ),
                GateCheck(
                    name="fix_attempts_valid",
                    description="Fix attempts must be below max",
                    check_fn=check_fix_attempts_not_exceeded,
                    error_message="Max fix attempts already exceeded."
                )
            ]
        )


# ============================================================================
# GATE EVALUATOR
# ============================================================================

class GateEvaluator:
    """
    Evaluates quality gates and determines state transitions.
    
    This is the enforcement mechanism that prevents bad transitions.
    """
    
    def __init__(self):
        self.gates = QualityGates()
        
    def can_exit_state(self, state: Dict[str, Any], current_phase: str) -> GateResult:
        """
        Check if current state can be exited.
        
        Args:
            state: Current agent graph state
            current_phase: Current phase (planning, coding, validating, fixing)
            
        Returns:
            GateResult with pass/fail status
        """
        gate_map = {
            "planning": self.gates.planning_exit_gate,
            "coding": self.gates.coding_exit_gate,
            "validating": self.gates.validation_exit_gate,
            "fixing": self.gates.fixing_exit_gate,
        }
        
        gate_fn = gate_map.get(current_phase)
        if not gate_fn:
            # No exit gate for this phase
            return GateResult(
                gate_name=f"{current_phase}_exit",
                passed=True,
                checks_passed=[],
                checks_failed=[],
                error_details={},
                timestamp=datetime.now().isoformat()
            )
        
        gate = gate_fn()
        return gate.evaluate(state)
    
    def can_enter_state(self, state: Dict[str, Any], target_phase: str) -> GateResult:
        """
        Check if target state can be entered.
        
        Args:
            state: Current agent graph state
            target_phase: Target phase to enter
            
        Returns:
            GateResult with pass/fail status
        """
        gate_map = {
            "coding": self.gates.coding_entry_gate,
            "validating": self.gates.validation_entry_gate,
            "fixing": self.gates.fixing_entry_gate,
        }
        
        gate_fn = gate_map.get(target_phase)
        if not gate_fn:
            # No entry gate for this phase
            return GateResult(
                gate_name=f"{target_phase}_entry",
                passed=True,
                checks_passed=[],
                checks_failed=[],
                error_details={},
                timestamp=datetime.now().isoformat()
            )
        
        gate = gate_fn()
        return gate.evaluate(state)
