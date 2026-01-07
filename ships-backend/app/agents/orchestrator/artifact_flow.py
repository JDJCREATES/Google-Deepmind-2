"""
ShipS* Artifact Flow Protocol (Simplified)

This module provides:
1. Exception classes for artifact errors (kept - useful for error handling)
2. Simple helper functions for working with LangGraph state.artifacts
3. Backward-compatible ArtifactRegistry class (deprecated, delegates to helpers)

The complex ArtifactRegistry has been simplified because LangGraph's
state["artifacts"] dict already provides the core functionality.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json


# ============================================================================
# EXCEPTION CLASSES (Kept - useful for error handling)
# ============================================================================

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


# ============================================================================
# SIMPLE HELPER FUNCTIONS (Work with LangGraph state)
# ============================================================================

def ensure_artifacts_exist(state: Dict[str, Any], required: List[str]) -> Tuple[bool, List[str]]:
    """
    Check that required artifacts exist in state.
    
    Use this in gate checks before phase transitions.
    
    Args:
        state: LangGraph state dict with 'artifacts' key
        required: List of required artifact names
        
    Returns:
        Tuple of (all_exist, missing_list)
    """
    artifacts = state.get("artifacts", {})
    missing = [name for name in required if name not in artifacts]
    return (len(missing) == 0, missing)


def get_artifact(state: Dict[str, Any], name: str, default: Any = None) -> Any:
    """
    Get artifact from state safely.
    
    Args:
        state: LangGraph state dict
        name: Artifact name
        default: Default value if not found
        
    Returns:
        Artifact data or default
    """
    return state.get("artifacts", {}).get(name, default)


def get_artifact_or_raise(state: Dict[str, Any], name: str) -> Any:
    """
    Get artifact from state, raise if missing.
    
    Args:
        state: LangGraph state dict
        name: Artifact name
        
    Returns:
        Artifact data
        
    Raises:
        MissingArtifact: If artifact not found
    """
    artifacts = state.get("artifacts", {})
    if name not in artifacts:
        raise MissingArtifact(f"Required artifact '{name}' not found in state")
    return artifacts[name]


def set_artifact(state: Dict[str, Any], name: str, data: Any) -> Dict[str, Any]:
    """
    Set artifact in state (returns updated artifacts dict for state update).
    
    Usage in LangGraph node:
        return {"artifacts": set_artifact(state, "plan", plan_data)}
    
    Args:
        state: LangGraph state dict
        name: Artifact name
        data: Artifact data
        
    Returns:
        Updated artifacts dict
    """
    artifacts = state.get("artifacts", {}).copy()
    artifacts[name] = data
    return artifacts


def merge_artifacts(state: Dict[str, Any], new_artifacts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge new artifacts into state artifacts.
    
    Args:
        state: LangGraph state dict
        new_artifacts: Dict of new artifacts to add
        
    Returns:
        Merged artifacts dict
    """
    artifacts = state.get("artifacts", {}).copy()
    artifacts.update(new_artifacts)
    return artifacts


# ============================================================================
# ARTIFACT DEPENDENCY GRAPH (Kept - useful for validation)
# ============================================================================

ARTIFACT_DEPENDENCIES: Dict[str, List[str]] = {
    "plan": ["structured_intent"],
    "code_changes": ["plan"],
    "validation_report": ["code_changes"],
    "build_log": ["code_changes"],
    "fix_report": ["code_changes", "validation_report"],
}


def get_required_artifacts_for_phase(phase: str) -> List[str]:
    """
    Get artifacts required to enter a phase.
    
    Use this in quality gate checks.
    
    Args:
        phase: Target phase name
        
    Returns:
        List of required artifact names
    """
    PHASE_REQUIREMENTS = {
        "planning": [],  # Just needs user request
        "coding": ["plan"],
        "validating": ["code_changes"],
        "fixing": ["code_changes", "validation_report"],
        "building": ["code_changes"],
        "complete": ["build_log"],
    }
    return PHASE_REQUIREMENTS.get(phase, [])


def check_phase_requirements(state: Dict[str, Any], phase: str) -> Tuple[bool, List[str]]:
    """
    Check if state has all artifacts required for a phase.
    
    Args:
        state: LangGraph state dict
        phase: Target phase
        
    Returns:
        Tuple of (ready, missing_artifacts)
    """
    required = get_required_artifacts_for_phase(phase)
    return ensure_artifacts_exist(state, required)


# ============================================================================
# AGENT INVOCATION RESULT (Kept - used by multiple components)
# ============================================================================

@dataclass
class AgentInvocationResult:
    """Result of invoking an agent."""
    success: bool
    artifacts: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: Optional[int] = None


# ============================================================================
# BACKWARD COMPATIBILITY (Deprecated)
# ============================================================================

class ArtifactStatus(str, Enum):
    """DEPRECATED: Status of an artifact."""
    FRESH = "fresh"
    STALE = "stale"
    LOCKED = "locked"


@dataclass
class ArtifactVersion:
    """DEPRECATED: Single version of an artifact."""
    artifact_type: str
    version: int
    data: Dict[str, Any]
    produced_by: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    hash: str = ""
    status: ArtifactStatus = ArtifactStatus.FRESH
    
    def __post_init__(self):
        if not self.hash:
            self.hash = hashlib.sha256(
                json.dumps(self.data, sort_keys=True, default=str).encode()
            ).hexdigest()[:16]


@dataclass
class ArtifactLock:
    """DEPRECATED: Lock information."""
    artifact_type: str
    locked_by: str
    locked_at: datetime = field(default_factory=datetime.utcnow)


class ArtifactRegistry:
    """
    DEPRECATED: Use state['artifacts'] dict directly.
    
    This class is kept for backward compatibility with existing code.
    New code should use the helper functions above.
    """
    
    DEPENDENCIES = ARTIFACT_DEPENDENCIES
    
    def __init__(self):
        self._artifacts: Dict[str, Any] = {}
        self._versions: Dict[str, List[ArtifactVersion]] = {}
        self._locks: Dict[str, ArtifactLock] = {}
    
    def has(self, artifact_type: str) -> bool:
        return artifact_type in self._artifacts
    
    def register(self, artifact_type: str, data: Dict[str, Any], produced_by: str) -> ArtifactVersion:
        if artifact_type not in self._versions:
            self._versions[artifact_type] = []
        
        version = len(self._versions[artifact_type]) + 1
        artifact = ArtifactVersion(
            artifact_type=artifact_type,
            version=version,
            data=data,
            produced_by=produced_by
        )
        
        self._artifacts[artifact_type] = artifact
        self._versions[artifact_type].append(artifact)
        return artifact
    
    def get(self, artifact_type: str, version: Optional[int] = None) -> ArtifactVersion:
        if artifact_type not in self._artifacts:
            raise ArtifactNotFound(f"Artifact '{artifact_type}' does not exist")
        
        if version is None:
            return self._artifacts[artifact_type]
        
        versions = self._versions.get(artifact_type, [])
        if version < 1 or version > len(versions):
            raise ArtifactNotFound(f"Version {version} not found")
        return versions[version - 1]
    
    def get_data(self, artifact_type: str) -> Dict[str, Any]:
        return self.get(artifact_type).data
    
    def lock(self, artifact_type: str, agent_name: str) -> None:
        if artifact_type in self._locks:
            lock = self._locks[artifact_type]
            if lock.locked_by != agent_name:
                raise ArtifactLocked(f"'{artifact_type}' locked by {lock.locked_by}")
        self._locks[artifact_type] = ArtifactLock(artifact_type, agent_name)
    
    def unlock(self, artifact_type: str, agent_name: str) -> None:
        lock = self._locks.get(artifact_type)
        if lock and lock.locked_by != agent_name:
            raise UnauthorizedUnlock(f"Don't own lock on '{artifact_type}'")
        if artifact_type in self._locks:
            del self._locks[artifact_type]
    
    def is_locked(self, artifact_type: str) -> bool:
        return artifact_type in self._locks
    
    def get_dependencies(self, artifact_type: str) -> List[str]:
        return self.DEPENDENCIES.get(artifact_type, [])
    
    def get_dependents(self, artifact_type: str) -> List[str]:
        return [k for k, v in self.DEPENDENCIES.items() if artifact_type in v]
    
    def get_summary(self) -> Dict[str, Any]:
        return {
            atype: {
                "version": a.version if isinstance(a, ArtifactVersion) else 1,
                "produced_by": a.produced_by if isinstance(a, ArtifactVersion) else "unknown",
                "locked": self.is_locked(atype)
            }
            for atype, a in self._artifacts.items()
        }


class AgentInvoker:
    """
    DEPRECATED: Use LangGraph nodes directly.
    
    Kept for backward compatibility.
    """
    
    def __init__(self, artifact_registry: ArtifactRegistry = None):
        self.artifacts = artifact_registry or ArtifactRegistry()
        self._agent_registry: Dict[str, Any] = {}
    
    def register_agent(self, name: str, agent: Any) -> None:
        self._agent_registry[name] = agent
    
    async def invoke(
        self,
        agent_name: str,
        required_artifacts: List[str],
        expected_outputs: List[str],
        parameters: Optional[Dict[str, Any]] = None
    ) -> AgentInvocationResult:
        """Invoke an agent with artifact contracts."""
        parameters = parameters or {}
        
        try:
            # Validate inputs
            for atype in required_artifacts:
                if not self.artifacts.has(atype):
                    raise MissingArtifact(f"Requires '{atype}'")
            
            # Build inputs
            agent_inputs = {
                "artifacts": {
                    atype: self.artifacts.get_data(atype)
                    for atype in required_artifacts
                    if self.artifacts.has(atype)
                },
                "parameters": parameters
            }
            
            # Run agent
            agent = self._agent_registry.get(agent_name)
            if not agent:
                raise ValueError(f"Agent '{agent_name}' not registered")
            
            result = await agent.invoke(agent_inputs)
            
            # Register outputs
            produced = result.get("artifacts", {})
            for atype, data in produced.items():
                self.artifacts.register(atype, data, agent_name)
            
            return AgentInvocationResult(success=True, artifacts=produced)
            
        except Exception as e:
            return AgentInvocationResult(success=False, error=str(e))
