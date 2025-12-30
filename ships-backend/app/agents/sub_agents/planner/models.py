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
    """Common metadata for all planner artifacts."""
    schema_version: str = Field(default="1.0.0")
    planner_version: str = Field(default="1.0.0")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
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
    decision_notes: List[str] = Field(
        default_factory=list,
        description="Short decision rationale notes"
    )


class PlannerComponentConfig(BaseModel):
    """Configuration for planner components."""
    max_tokens: int = 4000
    temperature: float = 0.0
    enable_web_search: bool = False
    project_root: str = "."



# ============================================================================
# TASK LIST
# ============================================================================

class AcceptanceCriterion(BaseModel):
    """Single acceptance criterion for a task."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = Field(..., description="What must be true")
    is_automated: bool = Field(
        default=True, 
        description="Can be validated automatically"
    )
    validation_command: Optional[str] = Field(
        default=None,
        description="Command to validate (if automated)"
    )


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
    """Single entry in the folder map."""
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
    version: str = Field(default="1")
    
    # Metadata
    metadata: ArtifactMetadata = Field(default_factory=ArtifactMetadata)
    
    # Origin
    intent_spec_id: str = Field(..., description="ID of source Intent Spec")
    
    # Summary
    summary: str = Field(..., description="One-line plan summary")
    detailed_description: str = Field(default="")
    
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
