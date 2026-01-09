"""
ShipS* Coder Artifact Models

Comprehensive Pydantic models for all Coder output artifacts:
1. FileChangeSet - Atomic list of file modifications with diffs
2. TestBundle - Generated tests for task acceptance criteria
3. CommitIntent - Commit metadata and rollback guidance
4. ImplementationReport - Rationale, confidence, edge cases
5. PreflightCheck - Static analysis results
6. FollowUpTasks - Optional spike tasks if incomplete

All artifacts carry metadata for traceability and versioning.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
from pydantic import BaseModel, Field
import uuid
import hashlib


# ============================================================================
# ENUMS
# ============================================================================

class FileOperation(str, Enum):
    """Type of file operation."""
    ADD = "add"          # New file
    MODIFY = "modify"    # Modify existing
    DELETE = "delete"    # Delete file
    RENAME = "rename"    # Rename file


class ChangeRisk(str, Enum):
    """Risk level of a change."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CheckStatus(str, Enum):
    """Status of a preflight check."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNING = "warning"


class TestType(str, Enum):
    """Type of test."""
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    SMOKE = "smoke"


# ============================================================================
# BASE METADATA
# ============================================================================

class CoderMetadata(BaseModel):
    """Common metadata for all coder artifacts."""
    schema_version: str = Field(default="1.0.0")
    coder_version: str = Field(default="1.0.0")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    task_id: str = Field(..., description="ID of source task")
    plan_id: Optional[str] = Field(default=None, description="ID of source plan")
    confidence: float = Field(
        default=1.0, 
        ge=0.0, 
        le=1.0,
        description="Confidence in the output"
    )
    decision_notes: List[str] = Field(
        default_factory=list,
        description="Short decision rationale notes"
    )


class CoderComponentConfig(BaseModel):
    """Configuration for coder components."""
    max_tokens: int = 100000
    temperature: float = 0.0
    enable_web_search: bool = False
    project_root: str = "."
    diff_context_lines: int = 3
    test_framework: str = "jest"



# ============================================================================
# FILE CHANGE SET
# ============================================================================

class FileDiff(BaseModel):
    """Unified diff for a file modification."""
    original_content: Optional[str] = Field(
        default=None,
        description="Original file content (for modify/delete)"
    )
    new_content: Optional[str] = Field(
        default=None,
        description="New file content (for add/modify)"
    )
    unified_diff: Optional[str] = Field(
        default=None,
        description="Unified diff format"
    )
    
    def compute_hash(self) -> str:
        """Compute hash of the change."""
        content = (self.new_content or "") + (self.original_content or "")
        return hashlib.sha256(content.encode()).hexdigest()[:12]


class FileChange(BaseModel):
    """Single file change in the changeset."""
    id: str = Field(default_factory=lambda: f"change_{uuid.uuid4().hex[:8]}")
    path: str = Field(..., description="Relative file path")
    operation: FileOperation = Field(..., description="Type of change")
    
    # Content
    diff: FileDiff = Field(default_factory=FileDiff)
    
    # Metadata
    summary_line: str = Field(
        default="",
        description="One-line summary of change"
    )
    reason: str = Field(
        default="",
        description="Why this change (tied to acceptance criteria)"
    )
    acceptance_criteria_ids: List[str] = Field(
        default_factory=list,
        description="Acceptance criteria this change satisfies"
    )
    
    # Risk
    risk: ChangeRisk = ChangeRisk.LOW
    risk_reason: str = Field(default="")
    
    # Language detection
    language: Optional[str] = Field(
        default=None,
        description="Detected programming language"
    )
    
    # Stats
    lines_added: int = 0
    lines_removed: int = 0


class FileChangeSet(BaseModel):
    """
    Atomic set of file changes for a single commit.
    
    This is the primary output of the Coder - a minimal,
    reviewable set of changes that implement a task.
    """
    # Identity
    id: str = Field(default_factory=lambda: f"changeset_{uuid.uuid4().hex[:12]}")
    
    # Metadata
    metadata: CoderMetadata
    
    # Changes
    changes: List[FileChange] = Field(default_factory=list)
    
    # Summary
    summary: str = Field(default="", description="One-paragraph summary")
    total_files_changed: int = 0
    total_lines_added: int = 0
    total_lines_removed: int = 0
    
    # Flags
    is_atomic: bool = Field(
        default=True,
        description="Can be applied as single commit"
    )
    is_parallelizable: bool = Field(
        default=False,
        description="Can be applied in parallel with others"
    )
    requires_human_review: bool = Field(
        default=False,
        description="Needs manual review before apply"
    )
    
    # Rollback
    rollback_command: str = Field(
        default="",
        description="Command to rollback this changeset"
    )
    
    def add_change(self, change: FileChange) -> None:
        """Add a change and update stats."""
        self.changes.append(change)
        self.total_files_changed += 1
        self.total_lines_added += change.lines_added
        self.total_lines_removed += change.lines_removed
    
    def compute_hash(self) -> str:
        """Compute hash of entire changeset."""
        hashes = [c.diff.compute_hash() for c in self.changes]
        combined = "".join(sorted(hashes))
        return hashlib.sha256(combined.encode()).hexdigest()[:16]


# ============================================================================
# TEST BUNDLE
# ============================================================================

class TestAssertion(BaseModel):
    """Single test assertion."""
    description: str
    expected: str
    is_deterministic: bool = True


class TestCase(BaseModel):
    """Single test case."""
    id: str = Field(default_factory=lambda: f"test_{uuid.uuid4().hex[:8]}")
    name: str
    description: str = ""
    test_type: TestType = TestType.UNIT
    
    # Target
    target_file: Optional[str] = None
    target_function: Optional[str] = None
    target_endpoint: Optional[str] = None
    
    # Test content
    test_code: str = Field(..., description="The actual test code")
    test_file_path: str = Field(..., description="Where to write the test")
    
    # Assertions
    assertions: List[TestAssertion] = Field(default_factory=list)
    
    # Run info
    run_command: str = Field(
        default="",
        description="Command to run this specific test"
    )
    
    # Coverage
    covers_acceptance_criteria: List[str] = Field(default_factory=list)


class TestBundle(BaseModel):
    """
    Collection of tests generated for a task.
    
    Maps to the Validation Checklist from the Planner.
    """
    # Metadata
    metadata: CoderMetadata
    
    # Tests
    tests: List[TestCase] = Field(default_factory=list)
    
    # Run info
    run_all_command: str = Field(
        default="npm test",
        description="Command to run all tests"
    )
    test_framework: str = Field(
        default="jest",
        description="Test framework used"
    )
    
    # Coverage
    expected_coverage: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0
    )
    
    # Flags
    includes_mocks: bool = False
    includes_fixtures: bool = False


# ============================================================================
# COMMIT INTENT
# ============================================================================

class SemanticVersionBump(str, Enum):
    """Semantic version bump type."""
    NONE = "none"
    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"


class CommitIntent(BaseModel):
    """
    Metadata for the intended commit.
    
    Provides commit message, authorship, and rollback guidance.
    """
    # Identity
    id: str = Field(default_factory=lambda: f"commit_{uuid.uuid4().hex[:8]}")
    
    # Commit message
    message: str = Field(..., description="Commit message")
    message_body: str = Field(
        default="",
        description="Extended commit message body"
    )
    
    # Authorship
    author: str = Field(default="ShipS* Coder Agent")
    author_email: str = Field(default="coder@ships.ai")
    
    # References
    task_id: str
    plan_id: Optional[str] = None
    changeset_id: str
    
    # Versioning
    version_bump: SemanticVersionBump = SemanticVersionBump.NONE
    version_bump_reason: str = ""
    
    # Auto-apply
    is_safe_to_auto_apply: bool = Field(
        default=False,
        description="Can be applied without human review"
    )
    auto_apply_reason: str = ""
    
    # Rollback
    rollback_command: str = Field(
        default="git revert HEAD",
        description="Command to rollback"
    )
    rollback_files: List[str] = Field(
        default_factory=list,
        description="Files to revert"
    )
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# IMPLEMENTATION REPORT
# ============================================================================

class InferredItem(BaseModel):
    """An item that was inferred during implementation."""
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = Field(default="", description="How it was inferred")
    requires_confirmation: bool = False


class EdgeCase(BaseModel):
    """An edge case identified during implementation."""
    description: str
    handling: str = Field(default="", description="How it's handled")
    is_covered_by_test: bool = False
    follow_up_required: bool = False


class ImplementationReport(BaseModel):
    """
    Detailed report of the implementation.
    
    Explains what was changed, why, and any edge cases.
    """
    # Identity
    id: str = Field(default_factory=lambda: f"report_{uuid.uuid4().hex[:8]}")
    
    # Metadata
    metadata: CoderMetadata
    
    # Summary
    summary: str = Field(
        ...,
        description="One-paragraph rationale of changes"
    )
    
    # What was done
    changes_made: List[str] = Field(
        default_factory=list,
        description="List of high-level changes"
    )
    
    # Acceptance criteria coverage
    acceptance_criteria_coverage: Dict[str, bool] = Field(
        default_factory=dict,
        description="Which criteria are satisfied"
    )
    
    # Inferred items
    inferred_items: List[InferredItem] = Field(default_factory=list)
    
    # Edge cases
    edge_cases: List[EdgeCase] = Field(default_factory=list)
    
    # Dependencies
    new_dependencies: List[str] = Field(default_factory=list)
    dependency_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0
    )
    dependency_justification: str = ""
    
    # Risk assessment
    overall_risk: ChangeRisk = ChangeRisk.LOW
    risk_factors: List[str] = Field(default_factory=list)
    
    # Confidence
    overall_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0
    )
    confidence_reasons: List[str] = Field(default_factory=list)


# ============================================================================
# PREFLIGHT CHECK
# ============================================================================

class CheckResult(BaseModel):
    """Result of a single preflight check."""
    name: str
    status: CheckStatus
    message: str = ""
    details: Optional[str] = None
    fix_suggestion: Optional[str] = None


class PreflightCheck(BaseModel):
    """
    Static analysis results before applying changes.
    
    Fast checks that don't require building.
    """
    # Identity
    id: str = Field(default_factory=lambda: f"preflight_{uuid.uuid4().hex[:8]}")
    
    # Overall status
    passed: bool = True
    
    # Individual checks
    checks: List[CheckResult] = Field(default_factory=list)
    
    # Summary
    total_passed: int = 0
    total_failed: int = 0
    total_warnings: int = 0
    
    # Blocking
    has_blockers: bool = False
    blocker_reasons: List[str] = Field(default_factory=list)
    
    # Security
    security_issues: List[str] = Field(default_factory=list)
    license_issues: List[str] = Field(default_factory=list)
    
    def add_check(self, result: CheckResult) -> None:
        """Add a check result and update stats."""
        self.checks.append(result)
        if result.status == CheckStatus.PASSED:
            self.total_passed += 1
        elif result.status == CheckStatus.FAILED:
            self.total_failed += 1
            self.passed = False
        elif result.status == CheckStatus.WARNING:
            self.total_warnings += 1


# ============================================================================
# FOLLOW-UP TASKS
# ============================================================================

class FollowUpTask(BaseModel):
    """A follow-up task created when full implementation isn't possible."""
    id: str = Field(default_factory=lambda: f"followup_{uuid.uuid4().hex[:8]}")
    title: str
    description: str
    reason: str = Field(
        ...,
        description="Why this wasn't completed in current task"
    )
    acceptance_criteria: List[str] = Field(default_factory=list)
    estimated_complexity: str = Field(default="small")
    is_spike: bool = Field(
        default=False,
        description="Is this a research/spike task"
    )
    blocking_parent: bool = Field(
        default=False,
        description="Does this block the parent task"
    )


class FollowUpTasks(BaseModel):
    """Collection of follow-up tasks."""
    tasks: List[FollowUpTask] = Field(default_factory=list)
    reason_for_incomplete: str = ""
    parent_task_id: str = ""


# ============================================================================
# CODER OUTPUT (COMBINED)
# ============================================================================

class CoderOutput(BaseModel):
    """
    Complete output from the Coder agent.
    
    Contains all artifacts produced for a single task.
    """
    # Status
    success: bool = True
    is_blocking: bool = False
    blocking_reasons: List[str] = Field(default_factory=list)
    
    # Artifacts
    file_change_set: Optional[FileChangeSet] = None
    test_bundle: Optional[TestBundle] = None
    commit_intent: Optional[CommitIntent] = None
    implementation_report: Optional[ImplementationReport] = None
    preflight_check: Optional[PreflightCheck] = None
    follow_up_tasks: Optional[FollowUpTasks] = None
    
    # Recommendations
    recommended_next_agent: Literal[
        "validator", "fixer", "planner", "coder"
    ] = "validator"
    
    # Metrics
    total_lines_changed: int = 0
    total_files_changed: int = 0
    total_tests_added: int = 0
