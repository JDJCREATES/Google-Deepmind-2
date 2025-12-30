"""
ShipS* Planner Artifact Models

Comprehensive Pydantic models for all Planner output artifacts:
1. PlanManifest - Top-level descriptor
2. TaskList - Ordered, prioritized tasks
3. FolderMap - Directory/file structure
4. APIContracts - Endpoint definitions
5. DependencyPlan - Packages, commands, env vars
6. ValidationChecklist - Test targets, assertions
7. RiskReport - Blockers, external approvals

All artifacts carry metadata for traceability and versioning.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
from pydantic import BaseModel, Field
import uuid


# ============================================================================
# ENUMS
# ============================================================================

class TaskComplexity(str, Enum):
    """Estimated task complexity for sizing."""
    TINY = "tiny"       # < 30 min
    SMALL = "small"     # 30 min - 2 hours
    MEDIUM = "medium"   # 2-4 hours
    LARGE = "large"     # 4-8 hours (should be decomposed)


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskPriority(str, Enum):
    """Task priority for ordering."""
    CRITICAL = "critical"   # Must be done first
    HIGH = "high"           # Important
    MEDIUM = "medium"       # Normal
    LOW = "low"             # Can be deferred


class RiskLevel(str, Enum):
    """Risk level for items."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FileRole(str, Enum):
    """Role of a file in the folder structure."""
    SOURCE = "source"               # Main source code
    COMPONENT = "component"         # UI component
    SERVICE = "service"             # Business logic service
    API = "api"                     # API route/handler
    MODEL = "model"                 # Data model
    UTILITY = "utility"             # Utility/helper
    CONFIG = "config"               # Configuration
    TEST = "test"                   # Test file
    STYLE = "style"                 # Styles
    ASSET = "asset"                 # Static asset
    DOCUMENTATION = "documentation" # Documentation


class HTTPMethod(str, Enum):
    """HTTP methods for API endpoints."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"


# ============================================================================
# BASE METADATA
# ============================================================================

class ArtifactMetadata(BaseModel):
    """
    Common metadata for all planner artifacts.
    Supports versioning and change tracking per ShipS* framework.
    """
    # Version tracking (mandatory for change management)
    schema_version: str = Field(default="1.0.0")
    planner_version: str = Field(default="1.0.0")
    artifact_version: str = Field(
        default="1.0.0",
        description="Version of this specific artifact (semver)"
    )
    previous_version: Optional[str] = Field(
        default=None,
        description="Previous version if this is an update"
    )
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Change tracking
    change_reason: Optional[str] = Field(
        default=None,
        description="Reason for version change (required for updates)"
    )
    changed_by: str = Field(
        default="planner",
        description="Agent or human that made the change"
    )
    is_human_override: bool = Field(
        default=False,
        description="True if a human forced this change"
    )
    
    # Confidence and traceability
    confidence: float = Field(
        default=1.0, 
        ge=0.0, 
        le=1.0,
        description="Confidence score for inferred items"
    )
    intent_spec_id: Optional[str] = Field(
        default=None,
        description="ID of originating Intent Spec"
    )
    plan_id: Optional[str] = Field(
        default=None,
        description="ID of parent plan manifest"
    )
    decision_notes: List[str] = Field(
        default_factory=list,
        description="Short decision rationale notes"
    )
    
    def increment_version(self, reason: str, changed_by: str = "planner") -> None:
        """Increment version and track the change."""
        import re
        self.previous_version = self.artifact_version
        # Parse semver and increment patch
        match = re.match(r"(\d+)\.(\d+)\.(\d+)", self.artifact_version)
        if match:
            major, minor, patch = map(int, match.groups())
            self.artifact_version = f"{major}.{minor}.{patch + 1}"
        else:
            self.artifact_version = "1.0.1"
        self.change_reason = reason
        self.changed_by = changed_by
        self.updated_at = datetime.utcnow()


class PlanAssumptions(BaseModel):
    """
    Explicit assumptions and defaults for the plan.
    Makes implicit decisions visible and auditable.
    """
    # Framework defaults
    framework: str = Field(
        default="Vite + React + TypeScript",
        description="Default frontend framework"
    )
    language: str = Field(
        default="TypeScript",
        description="Primary programming language"
    )
    styling: str = Field(
        default="TailwindCSS",
        description="CSS framework/approach"
    )
    state_management: str = Field(
        default="Zustand",
        description="State management library"
    )
    
    # Runtime versions
    node_version: str = Field(default="18.x")
    python_version: Optional[str] = Field(default=None)
    
    # Package management
    package_manager: Literal["npm", "pnpm", "yarn", "bun"] = "npm"
    
    # Auth
    default_auth: str = Field(
        default="none",
        description="Default auth model (none, session, jwt, oauth)"
    )
    
    # Automation thresholds
    auto_apply_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Confidence required for auto-apply fixes"
    )
    auto_scaffold: bool = Field(
        default=True,
        description="Allow scaffolding without confirmation"
    )
    
    # Testing
    test_runner: str = Field(default="vitest")
    e2e_runner: Optional[str] = Field(default="playwright")
    coverage_threshold: float = Field(
        default=0.50,
        description="Minimum coverage for critical modules"
    )
    
    # Behavior flags
    allow_assumptions: bool = Field(
        default=True,
        description="Allow Planner to make reasonable assumptions"
    )
    strict_mode: bool = Field(
        default=False,
        description="Require confirmation for every decision"
    )


class PlannerComponentConfig(BaseModel):
    """Configuration for planner components."""
    max_tokens: int = 4000
    temperature: float = 1.0  # Gemini 3 recommended
    enable_web_search: bool = False
    project_root: str = "."
    assumptions: PlanAssumptions = Field(default_factory=PlanAssumptions)



# ============================================================================
# TASK LIST
# ============================================================================

class AcceptanceCriterion(BaseModel):
    """
    Single acceptance criterion for a task.
    Supports Gherkin format (Given/When/Then) for testability.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    
    # Gherkin format (preferred - structured)
    given: Optional[str] = Field(
        default=None,
        description="Given... (precondition)"
    )
    when: Optional[str] = Field(
        default=None,
        description="When... (action)"
    )
    then: Optional[str] = Field(
        default=None,
        description="Then... (expected result)"
    )
    
    # Free-text format (fallback)
    description: str = Field(
        default="",
        description="What must be true (use Gherkin fields when possible)"
    )
    
    # Validation
    is_automated: bool = Field(
        default=True, 
        description="Can be validated automatically"
    )
    validation_command: Optional[str] = Field(
        default=None,
        description="Command to validate (if automated)"
    )
    validator_check_id: Optional[str] = Field(
        default=None,
        description="ID of corresponding validator check"
    )
    
    def to_gherkin(self) -> str:
        """Convert to Gherkin format string."""
        if self.given and self.when and self.then:
            return f"Given {self.given}, When {self.when}, Then {self.then}"
        return self.description


class TaskDependency(BaseModel):
    """Dependency between tasks."""
    task_id: str = Field(..., description="ID of dependency task")
    dependency_type: Literal["blocks", "required_before", "optional"] = "required_before"


class ExpectedOutput(BaseModel):
    """Expected output from a task."""
    file_path: str = Field(..., description="Path to created/modified file")
    action: Literal["create", "modify", "delete"] = "create"
    description: str = Field(default="", description="What will be in the file")


class Task(BaseModel):
    """Single task in the plan."""
    id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    title: str = Field(..., description="Short task title")
    description: str = Field(..., description="Detailed description")
    
    # Classification
    complexity: TaskComplexity = TaskComplexity.SMALL
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    
    # Dependencies and outputs
    dependencies: List[TaskDependency] = Field(default_factory=list)
    required_artifacts: List[str] = Field(
        default_factory=list,
        description="Artifact IDs needed to execute this task"
    )
    expected_outputs: List[ExpectedOutput] = Field(default_factory=list)
    
    # Acceptance criteria
    acceptance_criteria: List[AcceptanceCriterion] = Field(default_factory=list)
    
    # Blocking status
    is_blocked: bool = Field(default=False)
    blockers: List[str] = Field(
        default_factory=list,
        description="List of blocking issues"
    )
    
    # Parallelization
    is_parallelizable: bool = Field(
        default=True,
        description="Can be worked on concurrently with other tasks"
    )
    
    # Target area
    target_area: Literal["frontend", "backend", "database", "full-stack", "config"] = "full-stack"
    
    # Metadata
    estimated_minutes: int = Field(default=60, description="Estimated time in minutes")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    notes: str = Field(default="", description="Additional notes")


class TaskList(BaseModel):
    """Ordered list of tasks for the plan."""
    metadata: ArtifactMetadata = Field(default_factory=ArtifactMetadata)
    tasks: List[Task] = Field(default_factory=list)
    
    # Summary stats
    total_estimated_minutes: int = Field(default=0)
    blocked_task_count: int = Field(default=0)
    
    def add_task(self, task: Task) -> None:
        """Add a task and update stats."""
        self.tasks.append(task)
        self.total_estimated_minutes += task.estimated_minutes
        if task.is_blocked:
            self.blocked_task_count += 1
    
    def get_ready_tasks(self) -> List[Task]:
        """Get tasks that can be started (no unmet dependencies)."""
        completed_ids = {t.id for t in self.tasks if t.status == TaskStatus.COMPLETED}
        ready = []
        for task in self.tasks:
            if task.status != TaskStatus.PENDING:
                continue
            if task.is_blocked:
                continue
            deps_met = all(
                d.task_id in completed_ids 
                for d in task.dependencies 
                if d.dependency_type != "optional"
            )
            if deps_met:
                ready.append(task)
        return ready
    
    def get_by_priority(self) -> List[Task]:
        """Get tasks ordered by priority."""
        priority_order = {
            TaskPriority.CRITICAL: 0,
            TaskPriority.HIGH: 1,
            TaskPriority.MEDIUM: 2,
            TaskPriority.LOW: 3,
        }
        return sorted(self.tasks, key=lambda t: priority_order.get(t.priority, 2))


# ============================================================================
# FOLDER MAP
# ============================================================================

class FolderEntry(BaseModel):
    """
    Single entry in the folder map.
    Supports immutability protection per ShipS* framework.
    """
    path: str = Field(..., description="Relative path from project root")
    is_directory: bool = Field(default=False)
    description: str = Field(default="", description="One-line purpose")
    role: FileRole = FileRole.SOURCE
    owner_task_id: Optional[str] = Field(
        default=None,
        description="Task that creates/modifies this"
    )
    is_test_oriented: bool = Field(default=False)
    is_existing: bool = Field(
        default=False,
        description="Already exists in codebase"
    )
    action: Literal["create", "modify", "keep", "delete"] = "create"
    
    # Immutability protection (Coder cannot modify if True)
    is_immutable: bool = Field(
        default=False,
        description="Protected from modification by Coder"
    )
    immutable_reason: Optional[str] = Field(
        default=None,
        description="Why this is protected (e.g., 'core config')"
    )


class FolderMap(BaseModel):
    """Canonical folder structure for the project."""
    metadata: ArtifactMetadata = Field(default_factory=ArtifactMetadata)
    project_root: str = Field(default=".", description="Project root path")
    entries: List[FolderEntry] = Field(default_factory=list)
    
    def get_by_role(self, role: FileRole) -> List[FolderEntry]:
        """Get all entries with a specific role."""
        return [e for e in self.entries if e.role == role]
    
    def get_for_task(self, task_id: str) -> List[FolderEntry]:
        """Get all entries owned by a task."""
        return [e for e in self.entries if e.owner_task_id == task_id]


# ============================================================================
# API CONTRACTS
# ============================================================================

class FieldSchema(BaseModel):
    """Schema for a single field."""
    name: str
    type: str = Field(default="string", description="JSON type or custom type")
    required: bool = True
    description: str = ""
    example: Optional[Any] = None
    validation_rules: List[str] = Field(default_factory=list)


class PayloadSchema(BaseModel):
    """Schema for request/response payload."""
    content_type: str = "application/json"
    fields: List[FieldSchema] = Field(default_factory=list)
    example: Optional[Dict[str, Any]] = None


class APIEndpoint(BaseModel):
    """Single API endpoint contract."""
    id: str = Field(default_factory=lambda: f"api_{uuid.uuid4().hex[:8]}")
    path: str = Field(..., description="URL path (e.g., /api/users)")
    method: HTTPMethod = HTTPMethod.GET
    description: str = ""
    
    # Auth
    requires_auth: bool = False
    auth_type: Optional[str] = None  # "bearer", "api_key", etc.
    
    # Request
    request_schema: Optional[PayloadSchema] = None
    query_params: List[FieldSchema] = Field(default_factory=list)
    path_params: List[FieldSchema] = Field(default_factory=list)
    
    # Response
    success_status: int = 200
    success_response: Optional[PayloadSchema] = None
    error_responses: Dict[int, str] = Field(
        default_factory=dict,
        description="Status code -> error description"
    )
    
    # Metadata
    owner_task_id: Optional[str] = None
    confidence: float = 1.0


class APIContracts(BaseModel):
    """Collection of API endpoint contracts."""
    metadata: ArtifactMetadata = Field(default_factory=ArtifactMetadata)
    base_url: str = Field(default="/api", description="API base URL")
    endpoints: List[APIEndpoint] = Field(default_factory=list)
    
    # Shared schemas
    shared_types: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Reusable type definitions"
    )


# ============================================================================
# DEPENDENCY PLAN
# ============================================================================

class PackageDependency(BaseModel):
    """Single package dependency."""
    name: str
    version: str = Field(default="latest", description="Semver or 'latest'")
    is_dev: bool = Field(default=False, description="Dev dependency only")
    purpose: str = Field(default="", description="Why this package is needed")
    risk_level: RiskLevel = RiskLevel.LOW
    confidence: float = 1.0


class EnvironmentVariable(BaseModel):
    """Required environment variable."""
    name: str
    description: str = ""
    is_secret: bool = Field(default=False, description="Contains sensitive data")
    default_value: Optional[str] = Field(
        default=None,
        description="Default (never include actual secrets)"
    )
    required: bool = True


class RunCommand(BaseModel):
    """Command for dev/build/test workflow."""
    name: str = Field(..., description="Command name (e.g., 'dev', 'build')")
    command: str = Field(..., description="Actual command to run")
    description: str = ""
    working_directory: str = "."
    environment: Dict[str, str] = Field(default_factory=dict)


class DependencyPlan(BaseModel):
    """Complete dependency and environment plan."""
    metadata: ArtifactMetadata = Field(default_factory=ArtifactMetadata)
    
    # Package manager
    package_manager: Literal["npm", "pnpm", "yarn", "pip", "poetry"] = "npm"
    
    # Dependencies
    runtime_dependencies: List[PackageDependency] = Field(default_factory=list)
    dev_dependencies: List[PackageDependency] = Field(default_factory=list)
    
    # Native binaries
    required_binaries: List[str] = Field(
        default_factory=list,
        description="Native binaries needed (e.g., 'node', 'python')"
    )
    
    # Environment
    environment_variables: List[EnvironmentVariable] = Field(default_factory=list)
    
    # Commands
    commands: List[RunCommand] = Field(default_factory=list)
    
    # Runtime requirements
    node_version: Optional[str] = None
    python_version: Optional[str] = None


# ============================================================================
# VALIDATION CHECKLIST
# ============================================================================

class ValidationCheck(BaseModel):
    """Single validation check."""
    id: str = Field(default_factory=lambda: f"check_{uuid.uuid4().hex[:8]}")
    name: str
    description: str = ""
    
    # Check type
    check_type: Literal["unit", "integration", "runtime", "manual"] = "unit"
    
    # Target
    target_file: Optional[str] = None
    target_function: Optional[str] = None
    target_endpoint: Optional[str] = None
    
    # Assertion
    assertion: str = Field(..., description="What must be true")
    command: Optional[str] = Field(
        default=None,
        description="Command to run this check"
    )
    
    # Status
    is_automated: bool = True
    owner_task_id: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM


class ValidationChecklist(BaseModel):
    """Complete validation and test plan."""
    metadata: ArtifactMetadata = Field(default_factory=ArtifactMetadata)
    
    # Checks
    unit_checks: List[ValidationCheck] = Field(default_factory=list)
    integration_checks: List[ValidationCheck] = Field(default_factory=list)
    runtime_checks: List[ValidationCheck] = Field(default_factory=list)
    manual_checks: List[ValidationCheck] = Field(default_factory=list)
    
    # Coverage targets
    min_unit_test_coverage: float = Field(default=0.7, ge=0.0, le=1.0)
    min_integration_coverage: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Critical runtime sanity checks
    smoke_tests: List[str] = Field(
        default_factory=list,
        description="Quick sanity checks (e.g., 'app boots without 500s')"
    )


# ============================================================================
# RISK REPORT
# ============================================================================

class RiskItem(BaseModel):
    """Single risk or blocker."""
    id: str = Field(default_factory=lambda: f"risk_{uuid.uuid4().hex[:8]}")
    title: str
    description: str = ""
    
    # Classification
    risk_level: RiskLevel = RiskLevel.MEDIUM
    category: Literal[
        "technical", "dependency", "security", 
        "external", "license", "unknown"
    ] = "technical"
    
    # Status
    requires_human_input: bool = False
    requires_external_approval: bool = False
    is_resolved: bool = False
    
    # Mitigation
    mitigation: str = Field(default="", description="How to address this")
    affected_tasks: List[str] = Field(
        default_factory=list,
        description="Task IDs affected by this risk"
    )
    
    # Questions (if needs clarification)
    clarifying_questions: List[str] = Field(default_factory=list)


class RiskReport(BaseModel):
    """Complete risk and blocker report."""
    metadata: ArtifactMetadata = Field(default_factory=ArtifactMetadata)
    risks: List[RiskItem] = Field(default_factory=list)
    
    # Summary
    has_blockers: bool = Field(default=False)
    blocker_count: int = Field(default=0)
    high_risk_count: int = Field(default=0)
    
    def add_risk(self, risk: RiskItem) -> None:
        """Add a risk and update counts."""
        self.risks.append(risk)
        if risk.requires_human_input or risk.requires_external_approval:
            self.has_blockers = True
            self.blocker_count += 1
        if risk.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            self.high_risk_count += 1


# ============================================================================
# PLAN MANIFEST (TOP-LEVEL)
# ============================================================================

class ArtifactReference(BaseModel):
    """Reference to a produced artifact."""
    artifact_type: str
    artifact_id: str
    status: Literal["complete", "partial", "blocked"] = "complete"


class PlanManifest(BaseModel):
    """
    Top-level Plan descriptor.
    
    This is the single artifact that describes the complete plan,
    referencing all other produced artifacts.
    """
    # Identity
    id: str = Field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:12]}")
    version: str = Field(
        default="1.0.0",
        description="Plan version (semver, incremented on replan)"
    )
    
    # Metadata (includes change tracking)
    metadata: ArtifactMetadata = Field(default_factory=ArtifactMetadata)
    
    # Origin
    intent_spec_id: str = Field(..., description="ID of source Intent Spec")
    
    # Summary
    summary: str = Field(..., description="One-line plan summary")
    detailed_description: str = Field(default="")
    
    # Explicit assumptions
    assumptions: PlanAssumptions = Field(default_factory=PlanAssumptions)
    
    # Minimal Vertical Slice (MVS) - smallest end-to-end demo
    mvs_steps: List[str] = Field(
        default_factory=list,
        description="Steps to produce MVS (e.g., 'npm install', 'npm run dev')"
    )
    mvs_expected_files: List[str] = Field(
        default_factory=list,
        description="Files that must exist for MVS to work"
    )
    mvs_verification: Optional[str] = Field(
        default=None,
        description="How to verify MVS works (e.g., 'open http://localhost:3000')"
    )
    
    # Produced artifacts
    artifacts: List[ArtifactReference] = Field(default_factory=list)
    
    # Status
    is_complete: bool = Field(default=True)
    is_blocked: bool = Field(default=False)
    blocking_reasons: List[str] = Field(default_factory=list)
    
    # Recommendations
    recommended_next_agent: Literal[
        "coder", "validator", "fixer", "planner"
    ] = "coder"
    top_priority_tasks: List[str] = Field(
        default_factory=list,
        description="Task IDs to execute first"
    )
    
    # Stats
    total_tasks: int = 0
    estimated_total_minutes: int = 0
    blocked_tasks: int = 0
    
    # Clarification (if blocked)
    clarifying_questions: List[str] = Field(default_factory=list)
    
    def increment_version(self, reason: str) -> None:
        """Increment plan version and track change."""
        import re
        match = re.match(r"(\d+)\.(\d+)\.(\d+)", self.version)
        if match:
            major, minor, patch = map(int, match.groups())
            self.version = f"{major}.{minor}.{patch + 1}"
        else:
            self.version = "1.0.1"
        self.metadata.increment_version(reason, "planner")


# ============================================================================
# REPO PROFILE (Discovery Artifact)
# ============================================================================

class RepoPattern(BaseModel):
    """Detected pattern in existing codebase."""
    pattern_type: Literal[
        "naming", "async", "state", "styling", 
        "testing", "structure", "imports"
    ]
    value: str = Field(..., description="Detected pattern value")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    examples: List[str] = Field(
        default_factory=list,
        description="Example file paths demonstrating this pattern"
    )


class ReuseCandidate(BaseModel):
    """File or component identified for potential reuse."""
    path: str
    reusability: Literal["reuse", "adapt", "replace"] = "reuse"
    description: str = ""
    reason: str = Field(
        default="",
        description="Why this classification was made"
    )


class ConflictItem(BaseModel):
    """Conflict between existing repo and plan constraints."""
    category: Literal[
        "framework", "version", "pattern", "structure", "dependency"
    ]
    existing_value: str
    planned_value: str
    severity: Literal["low", "medium", "high"] = "medium"
    resolution: Optional[str] = None


class RepoProfile(BaseModel):
    """
    Discovery artifact for existing codebases.
    
    Produced during 'Check Existing' phase to capture:
    - Current versions and tools
    - Detected patterns and conventions
    - Reuse candidates
    - Conflicts with plan
    """
    metadata: ArtifactMetadata = Field(default_factory=ArtifactMetadata)
    
    # Versions and tools
    node_version: Optional[str] = None
    python_version: Optional[str] = None
    package_manager: Optional[str] = None
    framework: Optional[str] = None
    test_runner: Optional[str] = None
    linter: Optional[str] = None
    
    # Detected patterns
    patterns: List[RepoPattern] = Field(default_factory=list)
    
    # Reuse analysis
    reuse_candidates: List[ReuseCandidate] = Field(default_factory=list)
    
    # Conflicts with plan
    conflicts: List[ConflictItem] = Field(default_factory=list)
    
    # Summary
    is_empty_project: bool = Field(default=False)
    has_conflicts: bool = Field(default=False)
    suggested_approach: Literal[
        "scaffold", "extend", "adapt", "replace"
    ] = "scaffold"
    
    def get_patterns_by_type(self, pattern_type: str) -> List[RepoPattern]:
        """Get all patterns of a specific type."""
        return [p for p in self.patterns if p.pattern_type == pattern_type]
    
    def get_reusable_files(self) -> List[str]:
        """Get paths of files marked as reusable."""
        return [c.path for c in self.reuse_candidates if c.reusability == "reuse"]

