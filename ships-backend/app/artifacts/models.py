"""
ShipS* Artifact System - Pydantic Models

This module defines the data models for all artifacts used by the LangGraph agents.
These artifacts enable agent coordination, quality enforcement, and auditability.

Architecture:
- Layer 1: Planning Artifacts (user-provided)
- Layer 2: Runtime Artifacts (agent-managed)
- Layer 3: Audit Artifacts (system-generated)
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator
import uuid


# =============================================================================
# ENUMS
# =============================================================================

class GateStatus(str, Enum):
    """Status of a quality gate check."""
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class PitfallStatus(str, Enum):
    """Status of a pitfall check."""
    CHECKED = "CHECKED"
    CAUGHT = "CAUGHT"
    CLEAN = "CLEAN"
    SKIPPED = "SKIPPED"


class FileStatus(str, Enum):
    """Status of a file in the project."""
    STABLE = "stable"
    IN_PROGRESS = "in_progress"
    NEEDS_REVIEW = "needs_review"


class AgentType(str, Enum):
    """Types of agents in the system."""
    ORCHESTRATOR = "orchestrator"
    PLANNER = "planner"
    CODER = "coder"
    FIXER = "fixer"
    CONTEXT_SELECTOR = "context_selector"
    PATTERN_DETECTOR = "pattern_detector"
    VALIDATOR = "validator"
    DEPENDENCY_RESOLVER = "dependency_resolver"
    CONTRACT_VALIDATOR = "contract_validator"
    FRAMEWORK_VALIDATOR = "framework_validator"
    INTEGRATION_AGENT = "integration_agent"


# =============================================================================
# LAYER 2: RUNTIME ARTIFACTS - Pattern Registry
# =============================================================================

class NamingConventions(BaseModel):
    """Detected naming conventions from the codebase."""
    variables: str = Field(default="camelCase", description="Variable naming style")
    functions: str = Field(default="camelCase", description="Function naming style")
    components: str = Field(default="PascalCase", description="Component naming style")
    files: str = Field(default="kebab-case", description="File naming style")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Detection confidence")


class AsyncPatterns(BaseModel):
    """Detected async patterns from the codebase."""
    preferred: Literal["async/await", ".then()", "callbacks"] = Field(
        default="async/await", 
        description="Preferred async pattern"
    )
    error_handling: str = Field(
        default="try/catch on all async", 
        description="Error handling approach"
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class StateManagementPattern(BaseModel):
    """Detected state management patterns."""
    approach: str = Field(default="", description="State management approach (e.g., React Context, Redux)")
    location: str = Field(default="", description="Directory where state management code lives")
    pattern_example: str = Field(default="", description="Example code snippet")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ImportAliases(BaseModel):
    """Import path aliases configured in the project."""
    aliases: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of alias to actual path (e.g., '@/components' -> 'src/components')"
    )


class PatternRegistry(BaseModel):
    """
    Runtime artifact storing detected patterns from the existing codebase.
    
    Purpose: Ensures agents generate code consistent with existing patterns.
    Created by: Pattern Detector
    Updated by: Pattern Detector, Planner
    """
    version: str = Field(default="1.0.0", description="Schema version")
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    naming_conventions: NamingConventions = Field(default_factory=NamingConventions)
    async_patterns: AsyncPatterns = Field(default_factory=AsyncPatterns)
    state_management: StateManagementPattern = Field(default_factory=StateManagementPattern)
    
    error_handling_pattern: str = Field(
        default="", 
        description="Error handling pattern (e.g., try/catch with toast)"
    )
    error_handling_example: str = Field(default="", description="Example code")
    
    api_client_location: str = Field(default="", description="Path to API client file")
    api_base_url_pattern: str = Field(default="", description="How base URL is configured")
    api_authentication: str = Field(default="", description="Auth pattern (e.g., Bearer token)")
    
    import_aliases: ImportAliases = Field(default_factory=ImportAliases)
    
    class Config:
        json_schema_extra = {
            "example": {
                "naming_conventions": {
                    "variables": "camelCase",
                    "functions": "camelCase",
                    "components": "PascalCase",
                    "files": "kebab-case",
                    "confidence": 0.95
                }
            }
        }


# =============================================================================
# LAYER 2: RUNTIME ARTIFACTS - Contract Definitions
# =============================================================================

class RequestSchema(BaseModel):
    """Schema for an API request."""
    body: Optional[Dict[str, Any]] = Field(default=None, description="Request body schema")
    params: Optional[Dict[str, str]] = Field(default=None, description="URL parameters")
    query: Optional[Dict[str, str]] = Field(default=None, description="Query parameters")
    headers: Optional[Dict[str, str]] = Field(default=None, description="Required headers")


class ResponseSchema(BaseModel):
    """Schema for an API response."""
    status: int = Field(..., description="HTTP status code")
    body: Dict[str, Any] = Field(default_factory=dict, description="Response body schema")


class ContractEndpoint(BaseModel):
    """A single API endpoint contract."""
    endpoint: str = Field(..., description="HTTP method + path (e.g., 'POST /api/users')")
    description: str = Field(default="", description="What this endpoint does")
    request: RequestSchema = Field(default_factory=RequestSchema)
    success_response: ResponseSchema = Field(..., description="Success response schema")
    error_responses: List[ResponseSchema] = Field(
        default_factory=list, 
        description="Possible error responses"
    )
    validation_rules: List[str] = Field(
        default_factory=list, 
        description="Business validation rules"
    )
    
    @field_validator('endpoint')
    @classmethod
    def validate_endpoint_format(cls, v: str) -> str:
        """Ensure endpoint follows 'METHOD /path' format."""
        parts = v.split(' ', 1)
        if len(parts) != 2:
            raise ValueError("Endpoint must be in format 'METHOD /path'")
        method = parts[0].upper()
        if method not in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']:
            raise ValueError(f"Invalid HTTP method: {method}")
        return v


class ContractDefinitions(BaseModel):
    """
    Runtime artifact defining API contracts between frontend and backend.
    
    Purpose: Single source of truth for API shapes to prevent mismatches.
    Created by: Planner
    Enforced by: Contract Validator
    """
    version: str = Field(default="1.0.0")
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    contracts: List[ContractEndpoint] = Field(default_factory=list)
    
    def get_contract(self, endpoint: str) -> Optional[ContractEndpoint]:
        """Find a contract by endpoint string."""
        for contract in self.contracts:
            if contract.endpoint == endpoint:
                return contract
        return None
    
    def add_contract(self, contract: ContractEndpoint) -> None:
        """Add or update a contract."""
        existing = self.get_contract(contract.endpoint)
        if existing:
            self.contracts.remove(existing)
        self.contracts.append(contract)
        self.last_updated = datetime.utcnow()


# =============================================================================
# LAYER 2: RUNTIME ARTIFACTS - Quality Gate Results
# =============================================================================

class GateCheck(BaseModel):
    """A single check within a quality gate."""
    name: str = Field(..., description="Name of the check")
    passed: bool = Field(..., description="Whether the check passed")
    issues: List[str] = Field(default_factory=list, description="Issues found (if any)")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional details")


class FixAttempt(BaseModel):
    """Record of an attempt to fix a quality gate failure."""
    attempt_number: int = Field(..., ge=1)
    agent: AgentType = Field(...)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    result: Literal["SUCCESS", "FAILED", "PARTIAL"] = Field(...)
    changes_made: str = Field(default="", description="Description of changes")


class QualityGate(BaseModel):
    """A single quality gate with its checks and results."""
    gate_name: str = Field(..., description="Name of the gate (e.g., 'Plan Quality', 'Code Quality')")
    status: GateStatus = Field(default=GateStatus.PENDING)
    timestamp: Optional[datetime] = Field(default=None)
    checks: List[GateCheck] = Field(default_factory=list)
    fix_attempts: List[FixAttempt] = Field(default_factory=list)
    
    def run_checks(self, checks: List[GateCheck]) -> None:
        """Update gate with check results."""
        self.checks = checks
        self.timestamp = datetime.utcnow()
        self.status = GateStatus.PASSED if all(c.passed for c in checks) else GateStatus.FAILED


class QualityGateResults(BaseModel):
    """
    Runtime artifact tracking quality gate pass/fail status.
    
    Purpose: Enforce quality standards and prevent bad code from proceeding.
    Created by: Orchestrator
    Updated by: All agents
    """
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_description: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    gates: List[QualityGate] = Field(default_factory=list)
    current_gate: Optional[str] = Field(default=None, description="Currently active gate")
    can_proceed: bool = Field(default=False, description="Whether execution can continue")
    
    def add_gate(self, gate_name: str) -> QualityGate:
        """Add a new quality gate."""
        gate = QualityGate(gate_name=gate_name)
        self.gates.append(gate)
        self.current_gate = gate_name
        self.last_updated = datetime.utcnow()
        return gate
    
    def get_gate(self, gate_name: str) -> Optional[QualityGate]:
        """Get a gate by name."""
        for gate in self.gates:
            if gate.gate_name == gate_name:
                return gate
        return None
    
    def update_proceed_status(self) -> bool:
        """Check if all gates pass and update can_proceed."""
        self.can_proceed = all(
            gate.status == GateStatus.PASSED 
            for gate in self.gates 
            if gate.status != GateStatus.PENDING
        )
        return self.can_proceed


# =============================================================================
# LAYER 2: RUNTIME ARTIFACTS - Agent Conversation Log
# =============================================================================

class AgentLogEntry(BaseModel):
    """A single entry in the agent conversation log."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent: AgentType = Field(..., description="Which agent performed the action")
    action: str = Field(..., description="Action type (e.g., 'received_request', 'generated_code')")
    input_summary: Optional[str] = Field(default=None, description="Summary of input")
    output_summary: Optional[str] = Field(default=None, description="Summary of output")
    reasoning: Optional[str] = Field(default=None, description="Why this action was taken")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional details")
    duration_ms: Optional[int] = Field(default=None, description="How long the action took")


class AgentConversationLog(BaseModel):
    """
    Runtime artifact recording all agent actions and decisions.
    
    Purpose: Transparency and debugging - users can see exactly what agents did.
    Created by: Orchestrator
    Updated by: All agents (append-only)
    """
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_description: str = Field(default="")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    entries: List[AgentLogEntry] = Field(default_factory=list)
    
    def log(
        self, 
        agent: AgentType, 
        action: str, 
        input_summary: Optional[str] = None,
        output_summary: Optional[str] = None,
        reasoning: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None
    ) -> AgentLogEntry:
        """Add a new log entry."""
        entry = AgentLogEntry(
            agent=agent,
            action=action,
            input_summary=input_summary,
            output_summary=output_summary,
            reasoning=reasoning,
            details=details,
            duration_ms=duration_ms
        )
        self.entries.append(entry)
        return entry
    
    def get_entries_by_agent(self, agent: AgentType) -> List[AgentLogEntry]:
        """Filter entries by agent type."""
        return [e for e in self.entries if e.agent == agent]


# =============================================================================
# LAYER 2: RUNTIME ARTIFACTS - Context Map
# =============================================================================

class RelevantFile(BaseModel):
    """A file relevant to the current task."""
    path: str = Field(..., description="Relative path to the file")
    reason: str = Field(..., description="Why this file is relevant")
    priority: int = Field(default=1, ge=1, le=3, description="1=highest priority")
    lines_of_interest: Optional[List[int]] = Field(
        default=None, 
        description="Specific line ranges of interest"
    )
    content_hash: Optional[str] = Field(default=None, description="Hash for change detection")


class ContextMap(BaseModel):
    """
    Runtime artifact tracking which files are relevant for the current task.
    
    Purpose: Prevent token waste by giving agents only relevant context.
    Created by: Context Selector
    Updated by: Context Selector (per task)
    """
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    current_task: str = Field(..., description="Description of the current task")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    relevant_files: List[RelevantFile] = Field(default_factory=list)
    excluded_files_count: int = Field(default=0, description="Number of files excluded")
    token_estimate: int = Field(default=0, description="Estimated tokens for included files")
    
    def add_file(self, path: str, reason: str, priority: int = 1) -> RelevantFile:
        """Add a relevant file to the context."""
        file = RelevantFile(path=path, reason=reason, priority=priority)
        self.relevant_files.append(file)
        return file
    
    def get_files_by_priority(self, priority: int) -> List[RelevantFile]:
        """Get files with a specific priority level."""
        return [f for f in self.relevant_files if f.priority == priority]


# =============================================================================
# LAYER 2: RUNTIME ARTIFACTS - Dependency Graph
# =============================================================================

class DependencyNode(BaseModel):
    """A node in the dependency graph representing a file/module."""
    id: str = Field(..., description="File path or module identifier")
    node_type: Literal["component", "utility", "type", "style", "test", "config"] = Field(...)
    exports: List[str] = Field(default_factory=list, description="What this module exports")


class DependencyEdge(BaseModel):
    """An edge in the dependency graph representing an import relationship."""
    from_node: str = Field(..., description="Source file path")
    to_node: str = Field(..., description="Target file path")
    imports: List[str] = Field(default_factory=list, description="What is imported")


class DependencyGraph(BaseModel):
    """
    Runtime artifact mapping all imports and dependencies.
    
    Purpose: Detect breaking changes and circular dependencies.
    Created by: Dependency Resolver
    Updated by: Dependency Resolver (on file changes)
    """
    version: str = Field(default="1.0.0")
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    nodes: List[DependencyNode] = Field(default_factory=list)
    edges: List[DependencyEdge] = Field(default_factory=list)
    circular_dependencies: List[List[str]] = Field(
        default_factory=list, 
        description="Detected circular dependency chains"
    )
    orphaned_files: List[str] = Field(
        default_factory=list, 
        description="Files with no imports or exports"
    )
    
    def add_node(self, id: str, node_type: str, exports: List[str] = None) -> DependencyNode:
        """Add a node to the graph."""
        node = DependencyNode(id=id, node_type=node_type, exports=exports or [])
        self.nodes.append(node)
        return node
    
    def add_edge(self, from_node: str, to_node: str, imports: List[str]) -> DependencyEdge:
        """Add an edge to the graph."""
        edge = DependencyEdge(from_node=from_node, to_node=to_node, imports=imports)
        self.edges.append(edge)
        return edge
    
    def get_dependents(self, node_id: str) -> List[str]:
        """Get all files that import the given node."""
        return [e.from_node for e in self.edges if e.to_node == node_id]
    
    def get_dependencies(self, node_id: str) -> List[str]:
        """Get all files that the given node imports."""
        return [e.to_node for e in self.edges if e.from_node == node_id]


# =============================================================================
# LAYER 2: RUNTIME ARTIFACTS - Fix History
# =============================================================================

class FixRecord(BaseModel):
    """Record of a fix applied by the Fixer agent."""
    fix_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    trigger: str = Field(..., description="What triggered the fix (e.g., 'Validator found TODO')")
    file_path: str = Field(..., description="File that was fixed")
    line_number: Optional[int] = Field(default=None)
    original_code: str = Field(default="", description="Code before fix")
    fixed_code: str = Field(default="", description="Code after fix")
    reasoning: str = Field(default="", description="Why this fix was applied")
    validation_result: Literal["PASSED", "FAILED", "PENDING"] = Field(default="PENDING")


class FixHistory(BaseModel):
    """
    Runtime artifact recording all fixes applied by the Fixer agent.
    
    Purpose: Learn from fixes and provide context for future fixes.
    Created by: Fixer
    Updated by: Fixer (append-only)
    """
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    fixes: List[FixRecord] = Field(default_factory=list)
    
    def add_fix(
        self,
        trigger: str,
        file_path: str,
        original_code: str,
        fixed_code: str,
        reasoning: str,
        line_number: Optional[int] = None
    ) -> FixRecord:
        """Record a new fix."""
        fix = FixRecord(
            trigger=trigger,
            file_path=file_path,
            line_number=line_number,
            original_code=original_code,
            fixed_code=fixed_code,
            reasoning=reasoning
        )
        self.fixes.append(fix)
        return fix
    
    def get_fixes_for_file(self, file_path: str) -> List[FixRecord]:
        """Get all fixes applied to a specific file."""
        return [f for f in self.fixes if f.file_path == file_path]


# =============================================================================
# LAYER 2: RUNTIME ARTIFACTS - Pitfall Coverage Matrix
# =============================================================================

class PitfallCheck(BaseModel):
    """A single pitfall check result."""
    pitfall_id: str = Field(..., description="Pitfall ID (e.g., '1.1', '6.1')")
    name: str = Field(..., description="Pitfall name")
    status: PitfallStatus = Field(...)
    agent: Optional[AgentType] = Field(default=None, description="Agent that performed the check")
    details: Optional[Dict[str, Any]] = Field(default=None)
    fixed_by: Optional[AgentType] = Field(default=None)
    skip_reason: Optional[str] = Field(default=None, description="Why it was skipped")


class PitfallCoverageMatrix(BaseModel):
    """
    Runtime artifact tracking which pitfalls were checked and caught.
    
    Purpose: Confidence metric showing validation thoroughness.
    Created by: Orchestrator
    Updated by: All validators
    """
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    coverage: List[PitfallCheck] = Field(default_factory=list)
    
    @property
    def summary(self) -> Dict[str, Any]:
        """Calculate coverage summary."""
        total = len(self.coverage)
        checked = sum(1 for p in self.coverage if p.status in [PitfallStatus.CHECKED, PitfallStatus.CAUGHT, PitfallStatus.CLEAN])
        caught = sum(1 for p in self.coverage if p.status == PitfallStatus.CAUGHT)
        clean = sum(1 for p in self.coverage if p.status == PitfallStatus.CLEAN)
        skipped = sum(1 for p in self.coverage if p.status == PitfallStatus.SKIPPED)
        
        return {
            "total_pitfalls": total,
            "checked": checked,
            "caught": caught,
            "clean": clean,
            "skipped": skipped,
            "coverage_percent": (checked / total * 100) if total > 0 else 0
        }
    
    def add_check(
        self,
        pitfall_id: str,
        name: str,
        status: PitfallStatus,
        agent: Optional[AgentType] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> PitfallCheck:
        """Add a pitfall check result."""
        check = PitfallCheck(
            pitfall_id=pitfall_id,
            name=name,
            status=status,
            agent=agent,
            details=details
        )
        self.coverage.append(check)
        self.last_updated = datetime.utcnow()
        return check
