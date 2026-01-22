from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

# ==============================================================================
# ENUMS
# ==============================================================================

class ValidationStatus(str, Enum):
    """
    Status of the validation phase.
    Controls the strict state machine routing between Coder -> Validator -> Fixer.
    """
    PENDING = "pending"               # Initial state or after code changes (Must run Validator)
    PASSED = "passed"                 # Validation successful (Proceed to Complete)
    FAILED_RECOVERABLE = "failed_recoverable" # Lint errors, weak test failures (Proceed to Fixer)
    FAILED_CRITICAL = "failed_critical"       # Crash, syntax error, missing files (Escalate to Orchestrator)
    SKIPPED = "skipped"               # Explicitly skipped (e.g. Chat mode or low-stakes edit)
    # Legacy fallback mapping
    FAIL = "failed_recoverable" 
    PASS = "passed"

class FailureLayer(str, Enum):
    NONE = "none"
    STRUCTURAL = "structural"
    COMPLETENESS = "completeness"
    DEPENDENCY = "dependency"
    SCOPE = "scope"
    TYPESCRIPT = "typescript"
    BUILD = "build"
    UNKNOWN = "unknown"

class RecommendedAction(str, Enum):
    PROCEED = "proceed"
    FIX = "fix"
    REPLAN = "replan"
    ASK_USER = "ask_user"

class ViolationSeverity(str, Enum):
    CRITICAL = "critical"  # Must fix immediately (blocks build/run)
    MAJOR = "major"       # Should fix (broken feature)
    MINOR = "minor"       # Nice to fix (style/lint)
    INFO = "info"         # Observation only

class ValidationLayerName(str, Enum):
    STRUCTURAL = "structural"
    COMPLETENESS = "completeness"
    DEPENDENCY = "dependency"
    SCOPE = "scope"
    TYPESCRIPT = "typescript"
    BUILD = "build"

# ==============================================================================
# MODELS
# ==============================================================================

class Violation(BaseModel):
    """Represents a single validation issue."""
    rule: str
    message: str
    file_path: Optional[str] = None
    severity: ViolationSeverity = ViolationSeverity.MAJOR
    layer: FailureLayer = FailureLayer.UNKNOWN
    details: Optional[str] = None
    fix_hint: Optional[str] = None
    line_number: Optional[int] = None
    
    # For build errors
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    command: Optional[str] = None

class BuildViolation(Violation):
    """Specific violation for build failures."""
    layer: FailureLayer = FailureLayer.BUILD
    command: str = ""

class LayerResult(BaseModel):
    """Result of a single validation layer."""
    layer: ValidationLayerName
    passed: bool
    checks_run: int = 0
    violations: List[Violation] = Field(default_factory=list)
    duration_ms: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ValidationReport(BaseModel):
    """Comprehensive report of a validation run."""
    status: ValidationStatus
    failure_layer: FailureLayer = FailureLayer.NONE
    recommended_action: RecommendedAction = RecommendedAction.PROCEED
    
    total_violations: int = 0
    total_checks_run: int = 0
    
    layer_results: Dict[str, LayerResult] = Field(default_factory=dict)
    
    # Traceability
    task_id: str = ""
    plan_id: Optional[str] = None
    changeset_id: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: int = 0
    confidence: float = 1.0
    
    # New fields for Fixer handoff
    fixer_instructions: str = ""
    priority_violations: List[Any] = Field(default_factory=list) # List[Violation] or IDs
    
    def add_violation(self, violation: Violation):
        self.total_violations += 1
        # Also added to layer result during processing

class ValidatorConfig(BaseModel):
    """Configuration for Validator."""
    run_structural: bool = True
    run_completeness: bool = True
    run_dependency: bool = True
    run_scope: bool = True
    run_build: bool = True
    strict_mode: bool = True

class ValidatorInput(BaseModel):
    """Input for Validator."""
    file_change_set: Dict[str, Any]
    folder_map: Dict[str, Any]
    task: Optional[Dict[str, Any]] = None
    
# Placeholder Exception types referenced in __init__ just in case
class StructuralViolation(Exception): pass
class CompletenessViolation(Exception): pass
class DependencyViolation(Exception): pass
class ScopeViolation(Exception): pass
