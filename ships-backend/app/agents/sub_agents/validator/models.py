"""
ShipS* Validator Artifact Models

The Validator is the GATE - it answers one question only:
"Is the system safe to proceed?"

NOT: "Is this elegant?" "Is this optimal?" "Is this finished?"
ONLY: "Can the system move forward without lying?"

Validation Layers (in order - if any fails, validation stops):
1. Structural: Did Coder obey Folder Map?
2. Completeness: Are there TODOs/placeholders?
3. Dependency: Do imports resolve? Hallucinated packages?
4. Scope: Does implementation match App Blueprint?

Output is a hard contract: pass | fail, never "warning-only"
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
from pydantic import BaseModel, Field
import uuid


# ============================================================================
# ENUMS
# ============================================================================

class ValidationStatus(str, Enum):
    """Hard pass/fail status - no grey area."""
    PASS = "pass"
    FAIL = "fail"


class FailureLayer(str, Enum):
    """Which validation layer failed."""
    NONE = "none"
    STRUCTURAL = "structural"
    COMPLETENESS = "completeness"
    DEPENDENCY = "dependency"
    SCOPE = "scope"


class RecommendedAction(str, Enum):
    """What the Orchestrator should do next."""
    PROCEED = "proceed"       # Validation passed - move forward
    FIX = "fix"               # Dispatch Fixer with violations
    REPLAN = "replan"         # Invalidate Planner artifacts, re-run
    ASK_USER = "ask_user"     # Need human clarification
    ABORT = "abort"           # Cannot proceed, fatal issue


class ViolationSeverity(str, Enum):
    """How severe is this violation."""
    CRITICAL = "critical"     # Blocks everything
    MAJOR = "major"           # Must be fixed before proceed
    MINOR = "minor"           # Should be fixed but not blocking


# ============================================================================
# VIOLATION MODELS
# ============================================================================

class Violation(BaseModel):
    """
    A single validation violation.
    
    Each violation is a concrete, actionable issue
    that the Fixer can address.
    """
    id: str = Field(default_factory=lambda: f"violation_{uuid.uuid4().hex[:8]}")
    
    # What layer detected this
    layer: FailureLayer
    
    # What's wrong
    rule: str = Field(..., description="The rule that was violated")
    message: str = Field(..., description="Human-readable explanation")
    
    # Where
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    
    # Severity
    severity: ViolationSeverity = ViolationSeverity.MAJOR
    
    # Fix guidance (for Fixer)
    fix_hint: Optional[str] = None
    expected_behavior: Optional[str] = None
    
    # Traceability
    related_artifact_id: Optional[str] = None


class StructuralViolation(Violation):
    """Files in wrong location or protected directories touched."""
    layer: FailureLayer = FailureLayer.STRUCTURAL
    allowed_path: Optional[str] = None
    actual_path: Optional[str] = None


class CompletenessViolation(Violation):
    """TODOs, placeholders, missing exports, unhandled errors."""
    layer: FailureLayer = FailureLayer.COMPLETENESS
    violation_type: Literal[
        "todo", "placeholder", "missing_export", 
        "unhandled_error", "empty_function", "stub"
    ] = "todo"


class DependencyViolation(Violation):
    """Unresolved imports, hallucinated packages, circular deps."""
    layer: FailureLayer = FailureLayer.DEPENDENCY
    violation_type: Literal[
        "unresolved_import", "hallucinated_package", 
        "missing_declaration", "circular_dependency"
    ] = "unresolved_import"
    package_name: Optional[str] = None


class ScopeViolation(Violation):
    """Implementation doesn't match blueprint, exceeded scope."""
    layer: FailureLayer = FailureLayer.SCOPE
    violation_type: Literal[
        "blueprint_mismatch", "scope_exceeded", 
        "assumption_violated", "non_goal_touched"
    ] = "scope_exceeded"
    expected: Optional[str] = None
    actual: Optional[str] = None


# ============================================================================
# VALIDATION REPORT
# ============================================================================

class LayerResult(BaseModel):
    """Result of a single validation layer."""
    layer: FailureLayer
    passed: bool
    violations: List[Violation] = Field(default_factory=list)
    duration_ms: int = 0
    checks_run: int = 0
    checks_passed: int = 0


class ValidationReport(BaseModel):
    """
    The Validator's output artifact - a HARD CONTRACT.
    
    This is what the Orchestrator must treat as binding.
    There is NO "warning-only" mode.
    """
    # Identity
    id: str = Field(default_factory=lambda: f"validation_{uuid.uuid4().hex[:12]}")
    
    # Hard status: pass or fail, nothing else
    status: ValidationStatus
    
    # Which layer failed (if any)
    failure_layer: FailureLayer = FailureLayer.NONE
    
    # All violations found
    violations: List[Violation] = Field(default_factory=list)
    
    # Layer-by-layer results
    layer_results: Dict[str, LayerResult] = Field(default_factory=dict)
    
    # Confidence: how certain the Validator is
    confidence: float = Field(
        default=1.0, 
        ge=0.0, 
        le=1.0,
        description="Validator certainty level"
    )
    
    # What should happen next (BINDING)
    recommended_action: RecommendedAction
    
    # For the Fixer (if action = fix)
    fixer_instructions: Optional[str] = None
    priority_violations: List[str] = Field(
        default_factory=list,
        description="Violation IDs to fix first"
    )
    
    # Metadata
    task_id: str = ""
    plan_id: Optional[str] = None
    changeset_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: int = 0
    
    # Stats
    total_checks_run: int = 0
    total_violations: int = 0
    critical_count: int = 0
    major_count: int = 0
    minor_count: int = 0
    
    def add_violation(self, violation: Violation) -> None:
        """Add a violation and update stats."""
        self.violations.append(violation)
        self.total_violations += 1
        
        if violation.severity == ViolationSeverity.CRITICAL:
            self.critical_count += 1
        elif violation.severity == ViolationSeverity.MAJOR:
            self.major_count += 1
        else:
            self.minor_count += 1
    
    def get_violations_by_layer(self, layer: FailureLayer) -> List[Violation]:
        """Get all violations for a specific layer."""
        return [v for v in self.violations if v.layer == layer]
    
    def get_fix_manifest(self) -> Dict[str, Any]:
        """Get a manifest for the Fixer agent."""
        return {
            "violations": [v.model_dump() for v in self.violations],
            "priority_violations": self.priority_violations,
            "instructions": self.fixer_instructions,
            "failure_layer": self.failure_layer.value
        }


# ============================================================================
# VALIDATOR CONFIG
# ============================================================================

class ValidatorConfig(BaseModel):
    """Configuration for the Validator agent."""
    
    # Layer toggles
    run_structural: bool = True
    run_completeness: bool = True
    run_dependency: bool = True
    run_scope: bool = True
    
    # Strictness
    fail_on_todo: bool = True
    fail_on_placeholder: bool = True
    fail_on_hallucinated_import: bool = True
    
    # Patterns to detect
    todo_patterns: List[str] = Field(default_factory=lambda: [
        "TODO", "FIXME", "HACK", "XXX", "TEMP", "TBD"
    ])
    placeholder_patterns: List[str] = Field(default_factory=lambda: [
        "placeholder", "implement me", "not implemented",
        "pass  # TODO", "raise NotImplementedError"
    ])
    
    # Protected directories (cannot be modified)
    protected_paths: List[str] = Field(default_factory=lambda: [
        ".git/", "node_modules/", "__pycache__/", ".env"
    ])
    
    # Thresholds
    max_violations_before_abort: int = 50
    confidence_threshold: float = 0.8


# ============================================================================
# VALIDATOR INPUT
# ============================================================================

class ValidatorInput(BaseModel):
    """
    What the Validator receives from the Orchestrator.
    
    The Validator lives in artifact reality, not conversational context.
    It does NOT consume: raw user intent, chat history, orchestrator reasoning.
    """
    # Required: Coder output
    file_change_set: Dict[str, Any]
    
    # Required: Planner artifacts
    folder_map: Dict[str, Any]
    task_list: Optional[Dict[str, Any]] = None
    
    # Optional: App context
    app_blueprint: Optional[Dict[str, Any]] = None
    dependency_plan: Optional[Dict[str, Any]] = None
    
    # Optional: For scope validation
    current_task: Optional[Dict[str, Any]] = None
    
    # Traceability
    task_id: str = ""
    plan_id: Optional[str] = None
