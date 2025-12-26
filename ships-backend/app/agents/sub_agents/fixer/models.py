"""
ShipS* Fixer Artifact Models

The Fixer produces the smallest safe, auditable remediation that moves
the system toward a Validator: pass state while strictly honoring 
Planner artifacts, policy constraints, and traceability requirements.

Key Artifacts:
1. FixPlan - Proposed remediation strategy
2. FixPatch - FileChangeSet with violations addressed
3. FixReport - Post-attempt result
4. FixAttemptLog - Audit trail for compliance

Core Principles:
- Artifact-first fixes (no ephemeral "apply and hope")
- Never re-authorize architecture changes
- Minimize scope (smallest change that passes validation)
- Full explainability and traceability
- Safety first (no secrets, no banned packages)
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
from pydantic import BaseModel, Field
import uuid


# ============================================================================
# ENUMS
# ============================================================================

class FixScope(str, Enum):
    """Scope of the fix - determines whether Fixer can handle it."""
    LOCAL = "local"              # Small code/test patch within plan
    ARCHITECTURAL = "architectural"  # Requires folder map/plan changes
    POLICY_BLOCKED = "policy_blocked"  # Requires security/user review


class FixApproach(str, Enum):
    """Repair strategy approach."""
    PATCH_FILE = "patch_file"            # Direct code patch
    ADD_MOCK = "add_mock"                # Add mock implementation
    ADD_DEPENDENCY = "add_dependency"     # Add missing package
    ADD_TESTS = "add_tests"              # Add/update tests
    FIX_IMPORT = "fix_import"            # Fix import path
    ADD_EXPORT = "add_export"            # Add missing export
    REMOVE_TODO = "remove_todo"          # Implement TODO
    RECONFIGURE = "reconfigure"          # Config changes
    GUARD_CLAUSE = "guard_clause"        # Add safety guard


class FixRisk(str, Enum):
    """Estimated risk of the fix."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FixResult(str, Enum):
    """Result of applying a fix."""
    APPLIED = "applied"                    # Successfully applied
    REJECTED = "rejected"                  # Rejected by policy/user
    FAILED_TO_APPLY = "failed_to_apply"   # Technical failure
    PARTIAL_APPLY = "partial_apply"       # Some patches applied
    PENDING_APPROVAL = "pending_approval"  # Awaiting user approval


class ApprovalType(str, Enum):
    """Type of approval required."""
    NONE = "none"
    USER = "user"
    SECURITY = "security"
    OPERATOR = "operator"


# ============================================================================
# FIX PLAN
# ============================================================================

class ViolationFix(BaseModel):
    """How a specific violation will be addressed."""
    violation_id: str
    violation_message: str
    fix_approach: FixApproach
    fix_description: str
    affected_files: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    requires_mock: bool = False
    creates_followup_task: bool = False


class FixPlan(BaseModel):
    """
    Proposed remediation strategy for validation failures.
    
    This is the Fixer's proposal before any changes are made.
    """
    # Identity
    id: str = Field(default_factory=lambda: f"fixplan_{uuid.uuid4().hex[:12]}")
    
    # Traceability
    origin_validation_report_id: str
    plan_id: Optional[str] = None
    task_id: Optional[str] = None
    intent_spec_id: Optional[str] = None
    
    # Summary
    summary: str = Field(..., description="One sentence summary")
    failure_layer: str = Field(..., description="Layer being addressed")
    
    # Strategy
    approach: FixApproach
    violation_fixes: List[ViolationFix] = Field(default_factory=list)
    
    # Risk assessment
    estimated_risk: FixRisk = FixRisk.LOW
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    
    # Approval
    required_approvals: List[ApprovalType] = Field(default_factory=list)
    auto_apply_allowed: bool = True
    
    # Expected outputs
    expected_outputs: List[str] = Field(
        default_factory=list,
        description="Artifact IDs that will be produced"
    )
    
    # Escalation
    requires_replan: bool = False
    replan_reason: Optional[str] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    fixer_version: str = "1.0.0"
    schema_version: str = "1.0.0"
    
    def needs_approval(self) -> bool:
        """Check if this plan needs user approval."""
        return (
            len(self.required_approvals) > 0 or
            self.estimated_risk in [FixRisk.MEDIUM, FixRisk.HIGH] or
            self.confidence < 0.85
        )


# ============================================================================
# FIX PATCH (FileChangeSet for fixes)
# ============================================================================

class FixChange(BaseModel):
    """Single file change in a fix patch."""
    path: str
    operation: Literal["add", "modify", "delete"]
    original_content: Optional[str] = None
    new_content: Optional[str] = None
    unified_diff: Optional[str] = None
    
    # Traceability
    violation_ids: List[str] = Field(
        default_factory=list,
        description="Violations this change addresses"
    )
    reason: str = Field(..., description="Why this change")
    
    # Stats
    lines_added: int = 0
    lines_removed: int = 0


class FixPatch(BaseModel):
    """
    The exact set of file modifications proposed to fix violations.
    
    Atomic, commit-sized patch with full traceability.
    """
    # Identity
    id: str = Field(default_factory=lambda: f"fixpatch_{uuid.uuid4().hex[:12]}")
    fix_plan_id: str
    
    # Changes
    changes: List[FixChange] = Field(default_factory=list)
    
    # Summary
    summary: str = ""
    total_files: int = 0
    total_lines_added: int = 0
    total_lines_removed: int = 0
    
    # Preflight checks
    preflight_passed: bool = False
    lint_passed: bool = True
    imports_resolved: bool = True
    dependency_conflicts: List[str] = Field(default_factory=list)
    license_issues: List[str] = Field(default_factory=list)
    
    # Commit metadata
    commit_message: str = ""
    rollback_command: str = ""
    
    def add_change(self, change: FixChange) -> None:
        """Add a change and update stats."""
        self.changes.append(change)
        self.total_files += 1
        self.total_lines_added += change.lines_added
        self.total_lines_removed += change.lines_removed


# ============================================================================
# FIX TEST BUNDLE
# ============================================================================

class FixTest(BaseModel):
    """Test created to validate a fix."""
    name: str
    description: str
    test_code: str
    test_file_path: str
    validates_violation_ids: List[str] = Field(default_factory=list)


class FixTestBundle(BaseModel):
    """Tests created or updated to validate the repair."""
    fix_plan_id: str
    tests: List[FixTest] = Field(default_factory=list)
    run_command: str = "npm test"


# ============================================================================
# FIX REPORT
# ============================================================================

class FixReport(BaseModel):
    """
    Post-attempt artifact containing results of fix application.
    """
    # Identity
    id: str = Field(default_factory=lambda: f"fixreport_{uuid.uuid4().hex[:12]}")
    fix_plan_id: str
    fix_patch_id: Optional[str] = None
    
    # Result
    result: FixResult
    applied_by: Literal["system", "user", "operator"] = "system"
    
    # Preflight results
    preflight_checks: Dict[str, bool] = Field(default_factory=dict)
    
    # Validation result
    post_validation_report_id: Optional[str] = None
    validation_passed: bool = False
    
    # Confidence
    final_confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""
    
    # Rollback
    rollback_available: bool = True
    rollback_command: str = ""
    
    # Timestamps
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_ms: int = 0


# ============================================================================
# FIX ATTEMPT LOG (Audit Trail)
# ============================================================================

class AttemptStep(BaseModel):
    """Single step in a fix attempt."""
    step_number: int
    action: str
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None
    success: bool
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class FixAttemptLog(BaseModel):
    """
    Low-level trace of steps taken for audit/postmortem.
    """
    # Identity
    id: str = Field(default_factory=lambda: f"fixlog_{uuid.uuid4().hex[:12]}")
    fix_plan_id: str
    
    # Context
    attempt_number: int = 1
    max_attempts: int = 3
    
    # Steps
    steps: List[AttemptStep] = Field(default_factory=list)
    
    # Queries made
    dependency_resolver_queries: List[str] = Field(default_factory=list)
    pattern_detector_queries: List[str] = Field(default_factory=list)
    
    # Hashes
    context_hashes: Dict[str, str] = Field(default_factory=dict)
    
    # Result
    final_result: Optional[FixResult] = None
    escalated: bool = False
    escalation_reason: Optional[str] = None
    
    def add_step(
        self, 
        action: str, 
        success: bool, 
        error: Optional[str] = None
    ) -> None:
        """Add a step to the log."""
        self.steps.append(AttemptStep(
            step_number=len(self.steps) + 1,
            action=action,
            success=success,
            error=error
        ))


# ============================================================================
# REPLAN REQUEST
# ============================================================================

class ReplanRequest(BaseModel):
    """
    Request for Planner re-evaluation when Fixer cannot proceed.
    
    Created when fix would violate Folder Map, App Blueprint,
    or requires architectural changes.
    """
    id: str = Field(default_factory=lambda: f"replan_{uuid.uuid4().hex[:8]}")
    
    # Context
    origin_validation_report_id: str
    origin_fix_plan_id: str
    original_plan_id: Optional[str] = None
    
    # Problem
    reason: str
    violated_artifact: Literal["folder_map", "app_blueprint", "execution_plan", "scope"]
    violation_details: str
    
    # Suggestion
    suggested_changes: List[str] = Field(default_factory=list)
    
    # Priority
    is_blocking: bool = True
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# FIXER CONFIG
# ============================================================================

class FixerConfig(BaseModel):
    """Configuration for the Fixer agent."""
    
    # Thresholds
    auto_apply_threshold: float = Field(
        default=0.85,
        description="Confidence required for auto-apply"
    )
    escalation_confidence: float = Field(
        default=0.70,
        description="Below this, require human review"
    )
    max_auto_fix_attempts: int = 3
    
    # Policies
    allow_new_dependencies: bool = True
    allow_mock_implementations: bool = True
    allow_auto_apply: bool = True
    
    # Risk
    auto_apply_risk_levels: List[FixRisk] = Field(
        default_factory=lambda: [FixRisk.LOW]
    )
    
    # Limits
    max_files_per_fix: int = 10
    max_lines_per_fix: int = 200


# ============================================================================
# FIXER OUTPUT
# ============================================================================

class FixerOutput(BaseModel):
    """Complete output from the Fixer agent."""
    
    # Status
    success: bool = False
    requires_approval: bool = False
    requires_replan: bool = False
    
    # Artifacts
    fix_plan: Optional[FixPlan] = None
    fix_patch: Optional[FixPatch] = None
    fix_test_bundle: Optional[FixTestBundle] = None
    fix_report: Optional[FixReport] = None
    fix_attempt_log: Optional[FixAttemptLog] = None
    replan_request: Optional[ReplanRequest] = None
    
    # Recommendations
    recommended_action: Literal[
        "apply_patch", "request_user_approval", 
        "request_security_approval", "replan", "abort"
    ] = "apply_patch"
    
    # Confidence
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    
    # Next steps
    next_agent: Literal["validator", "planner", "user"] = "validator"
