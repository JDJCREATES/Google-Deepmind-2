"""
ShipS* Artifact Flow Protocol

Implements the artifact handoff protocol between agents with:
- Immutable artifact versioning
- Lock/unlock mechanism for concurrent access
- Dependency tracking and invalidation
- Stale artifact detection

Agents NEVER access files directly - they go through this registry.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import uuid
import json


class ArtifactStatus(str, Enum):
    """Status of an artifact."""
    FRESH = "fresh"
    STALE = "stale"
    LOCKED = "locked"


class ArtifactError(Exception):
    """Base exception for artifact errors."""
    pass


class ArtifactNotFound(ArtifactError):
    """Artifact doesn't exist."""
    pass


class ArtifactLocked(ArtifactError):
    """Artifact is locked by another agent."""
    pass


class ArtifactStale(ArtifactError):
    """Artifact is stale and needs regeneration."""
    pass


class UnauthorizedUnlock(ArtifactError):
    """Agent doesn't own the lock."""
    pass


class MissingArtifact(ArtifactError):
    """Required artifact is missing."""
    pass


class MissingOutput(ArtifactError):
    """Agent didn't produce expected output."""
    pass


@dataclass
class ArtifactVersion:
    """
    A single immutable version of an artifact.
    
    Each time an artifact is updated, a new version is created.
    Old versions are preserved for rollback and auditing.
    """
    artifact_type: str
    version: int
    data: Dict[str, Any]
    produced_by: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    hash: str = ""
    status: ArtifactStatus = ArtifactStatus.FRESH
    
    def __post_init__(self):
        """Compute hash after initialization."""
        if not self.hash:
            self.hash = hashlib.sha256(
                json.dumps(self.data, sort_keys=True, default=str).encode()
            ).hexdigest()[:16]


@dataclass
class ArtifactLock:
    """Lock information for an artifact."""
    artifact_type: str
    locked_by: str
    locked_at: datetime = field(default_factory=datetime.utcnow)


class ArtifactRegistry:
    """
    Single source of truth for all artifacts.
    
    This registry provides:
    - Immutable versioning: Every artifact version is preserved
    - Locking: Prevents concurrent modification
    - Dependency tracking: Knows what invalidates what
    - Stale detection: Flags artifacts whose dependencies changed
    
    Usage:
        registry = ArtifactRegistry()
        registry.register("plan", {"tasks": [...]}, "Planner")
        plan = registry.get("plan")
    """
    
    # Artifact dependency graph
    # Key depends on values (if value changes, key becomes stale)
    DEPENDENCIES: Dict[str, List[str]] = {
        "plan": ["app_blueprint", "structured_intent"],
        "code_changes": ["plan", "pattern_registry", "contract_definitions", "context_map"],
        "validation_report": ["code_changes"],
        "dependency_graph": ["code_changes"],
        "integration_check": ["code_changes", "dependency_graph"],
        "build_log": ["code_changes", "validation_report"],
        "fix_report": ["code_changes", "validation_report"],
    }
    
    def __init__(self):
        """Initialize empty registry."""
        self._artifacts: Dict[str, ArtifactVersion] = {}
        self._versions: Dict[str, List[ArtifactVersion]] = {}
        self._locks: Dict[str, ArtifactLock] = {}
    
    def has(self, artifact_type: str) -> bool:
        """Check if artifact exists."""
        return artifact_type in self._artifacts
    
    def register(
        self, 
        artifact_type: str, 
        data: Dict[str, Any], 
        produced_by: str
    ) -> ArtifactVersion:
        """
        Register a new artifact version.
        
        Creates a new immutable version. Does not modify existing versions.
        
        Args:
            artifact_type: Type of artifact (e.g., "plan", "code_changes")
            data: Artifact data
            produced_by: Name of agent that created this
            
        Returns:
            The new ArtifactVersion
        """
        # Initialize version list if needed
        if artifact_type not in self._versions:
            self._versions[artifact_type] = []
        
        # Calculate version number
        version = len(self._versions[artifact_type]) + 1
        
        # Create new version
        artifact = ArtifactVersion(
            artifact_type=artifact_type,
            version=version,
            data=data,
            produced_by=produced_by
        )
        
        # Store
        self._artifacts[artifact_type] = artifact
        self._versions[artifact_type].append(artifact)
        
        # Invalidate dependents
        self._invalidate_dependents(artifact_type)
        
        return artifact
    
    def get(
        self, 
        artifact_type: str, 
        version: Optional[int] = None
    ) -> ArtifactVersion:
        """
        Retrieve artifact by type.
        
        Args:
            artifact_type: Type of artifact
            version: Specific version (None = latest)
            
        Returns:
            ArtifactVersion
            
        Raises:
            ArtifactNotFound: If artifact doesn't exist
            ArtifactStale: If artifact is stale
        """
        if artifact_type not in self._artifacts:
            raise ArtifactNotFound(f"Artifact '{artifact_type}' does not exist")
        
        if version is None:
            artifact = self._artifacts[artifact_type]
        else:
            versions = self._versions.get(artifact_type, [])
            if version < 1 or version > len(versions):
                raise ArtifactNotFound(f"Version {version} of '{artifact_type}' not found")
            artifact = versions[version - 1]
        
        # Check if stale
        if artifact.status == ArtifactStatus.STALE:
            raise ArtifactStale(f"Artifact '{artifact_type}' is stale, regenerate first")
        
        return artifact
    
    def get_data(self, artifact_type: str) -> Dict[str, Any]:
        """Get just the data from an artifact."""
        return self.get(artifact_type).data
    
    def lock(self, artifact_type: str, agent_name: str) -> None:
        """
        Lock artifact for modification.
        
        Prevents concurrent modification race conditions.
        
        Args:
            artifact_type: Type to lock
            agent_name: Agent requesting lock
            
        Raises:
            ArtifactLocked: If already locked by another agent
        """
        if artifact_type in self._locks:
            lock = self._locks[artifact_type]
            if lock.locked_by != agent_name:
                raise ArtifactLocked(
                    f"'{artifact_type}' is locked by {lock.locked_by}"
                )
        
        self._locks[artifact_type] = ArtifactLock(
            artifact_type=artifact_type,
            locked_by=agent_name
        )
    
    def unlock(self, artifact_type: str, agent_name: str) -> None:
        """
        Release lock after modification.
        
        Args:
            artifact_type: Type to unlock
            agent_name: Agent releasing lock
            
        Raises:
            UnauthorizedUnlock: If agent doesn't own the lock
        """
        lock = self._locks.get(artifact_type)
        
        if lock is None:
            return  # Not locked, nothing to do
        
        if lock.locked_by != agent_name:
            raise UnauthorizedUnlock(
                f"'{agent_name}' doesn't own lock on '{artifact_type}' (owned by {lock.locked_by})"
            )
        
        del self._locks[artifact_type]
    
    def is_locked(self, artifact_type: str) -> bool:
        """Check if artifact is locked."""
        return artifact_type in self._locks
    
    def get_dependencies(self, artifact_type: str) -> List[str]:
        """Get artifacts that this artifact depends on."""
        return self.DEPENDENCIES.get(artifact_type, [])
    
    def get_dependents(self, artifact_type: str) -> List[str]:
        """Get artifacts that depend on this artifact."""
        dependents = []
        for dep_type, deps in self.DEPENDENCIES.items():
            if artifact_type in deps:
                dependents.append(dep_type)
        return dependents
    
    def _invalidate_dependents(self, artifact_type: str) -> None:
        """
        Mark dependent artifacts as stale.
        
        Called when an artifact is updated. Cascades to all dependents.
        """
        dependents = self.get_dependents(artifact_type)
        
        for dep in dependents:
            if dep in self._artifacts:
                self._artifacts[dep].status = ArtifactStatus.STALE
                # Cascade
                self._invalidate_dependents(dep)
    
    def invalidate(self, artifact_type: str) -> None:
        """Manually invalidate an artifact."""
        if artifact_type in self._artifacts:
            self._artifacts[artifact_type].status = ArtifactStatus.STALE
            self._invalidate_dependents(artifact_type)
    
    def get_version_count(self, artifact_type: str) -> int:
        """Get number of versions for an artifact."""
        return len(self._versions.get(artifact_type, []))
    
    def get_all_versions(self, artifact_type: str) -> List[ArtifactVersion]:
        """Get all versions of an artifact."""
        return self._versions.get(artifact_type, []).copy()
    
    def rollback(self, artifact_type: str, version: int) -> ArtifactVersion:
        """
        Rollback to a previous version.
        
        Creates a new version with the old data.
        
        Args:
            artifact_type: Type to rollback
            version: Version to rollback to
            
        Returns:
            New ArtifactVersion
        """
        old_version = self.get(artifact_type, version)
        return self.register(
            artifact_type,
            old_version.data,
            "Rollback"
        )
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all artifacts."""
        summary = {}
        for artifact_type, artifact in self._artifacts.items():
            summary[artifact_type] = {
                "version": artifact.version,
                "produced_by": artifact.produced_by,
                "status": artifact.status.value,
                "locked": self.is_locked(artifact_type),
                "timestamp": artifact.timestamp.isoformat()
            }
        return summary


# ============================================================================
# AGENT INVOCATION PROTOCOL
# ============================================================================

@dataclass
class AgentInvocationResult:
    """Result of invoking an agent."""
    success: bool
    artifacts: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class AgentInvoker:
    """
    Handles agent invocation with strict artifact contracts.
    
    This class ensures:
    - All required artifacts exist and are fresh
    - Output artifacts are locked during execution
    - Results are properly registered
    """
    
    def __init__(self, artifact_registry: ArtifactRegistry):
        """
        Initialize with artifact registry.
        
        Args:
            artifact_registry: ArtifactRegistry instance
        """
        self.artifacts = artifact_registry
        self._agent_registry: Dict[str, Any] = {}
    
    def register_agent(self, name: str, agent: Any) -> None:
        """Register an agent for invocation."""
        self._agent_registry[name] = agent
    
    async def invoke(
        self,
        agent_name: str,
        required_artifacts: List[str],
        expected_outputs: List[str],
        parameters: Optional[Dict[str, Any]] = None
    ) -> AgentInvocationResult:
        """
        Invoke an agent with artifact contracts.
        
        This method:
        1. Validates all input artifacts exist and are fresh
        2. Locks artifacts this agent will modify
        3. Fetches input artifacts
        4. Runs the agent
        5. Validates outputs match expectations
        6. Registers new artifact versions
        7. Unlocks artifacts
        
        Args:
            agent_name: Name of agent to invoke
            required_artifacts: Artifacts the agent needs as input
            expected_outputs: Artifacts the agent should produce
            parameters: Additional parameters
            
        Returns:
            AgentInvocationResult
        """
        parameters = parameters or {}
        locked_types: List[str] = []
        
        try:
            # 1. Validate all input artifacts exist and are fresh
            for artifact_type in required_artifacts:
                if not self.artifacts.has(artifact_type):
                    raise MissingArtifact(f"Agent '{agent_name}' requires '{artifact_type}'")
                
                artifact = self.artifacts.get(artifact_type)
                if artifact.status == ArtifactStatus.STALE:
                    raise ArtifactStale(f"'{artifact_type}' is stale, regenerate first")
            
            # 2. Lock artifacts this agent will modify
            for artifact_type in expected_outputs:
                self.artifacts.lock(artifact_type, agent_name)
                locked_types.append(artifact_type)
            
            # 3. Fetch input artifacts
            agent_inputs = {
                "artifacts": {
                    atype: self.artifacts.get_data(atype)
                    for atype in required_artifacts
                    if self.artifacts.has(atype)
                },
                "parameters": parameters
            }
            
            # 4. Run agent
            agent = self._agent_registry.get(agent_name)
            if agent is None:
                raise ValueError(f"Agent '{agent_name}' not registered")
            
            result = await agent.invoke(agent_inputs)
            
            # 5. Validate outputs
            produced_artifacts = result.get("artifacts", {})
            for artifact_type in expected_outputs:
                if artifact_type not in produced_artifacts:
                    raise MissingOutput(f"Agent '{agent_name}' didn't produce '{artifact_type}'")
            
            # 6. Register new versions
            for artifact_type, data in produced_artifacts.items():
                self.artifacts.register(artifact_type, data, agent_name)
            
            # 7. Unlock
            for artifact_type in locked_types:
                self.artifacts.unlock(artifact_type, agent_name)
            
            return AgentInvocationResult(
                success=True,
                artifacts=produced_artifacts
            )
            
        except Exception as e:
            # Unlock on failure
            for artifact_type in locked_types:
                try:
                    self.artifacts.unlock(artifact_type, agent_name)
                except:
                    pass
            
            return AgentInvocationResult(
                success=False,
                error=str(e)
            )
