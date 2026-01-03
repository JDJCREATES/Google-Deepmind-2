"""
ShipS* Orchestrator Package

The central intelligence of the ShipS* system providing:
- Quality Gates: Enforce quality at every step
- Error Recovery: Smart retries and escalation
- State Sync: Coordinate data between agents and disk

NOTE: The complex StateMachine and ArtifactRegistry have been simplified.
- LangGraph handles state transitions through conditional edges
- ArtifactManager (app/artifacts/) handles disk persistence
- state["artifacts"] is the in-memory source of truth

For disk-synced artifacts that the frontend can edit, use ArtifactManager.
"""

# Simplified state management (audit logging only)
from .state_machine import (
    # New simplified components
    Phase,
    TransitionLogger,
    StateTransition,
    TransitionReason,
    TransitionError,
    StateContext,
    # Backward-compatible aliases (deprecated)
    StateMachine,
    OrchestratorState,
)

# Quality gates (kept - valuable for enforcement)
from .quality_gates import (
    QualityGate,
    QualityGateRegistry,
    QualityGateChecker,
    GateCheck,
    GateCheckStatus,
)

# Simplified artifact helpers (work with LangGraph state)
from .artifact_flow import (
    # New helper functions
    ensure_artifacts_exist,
    get_artifact,
    get_artifact_or_raise,
    set_artifact,
    merge_artifacts,
    get_required_artifacts_for_phase,
    check_phase_requirements,
    ARTIFACT_DEPENDENCIES,
    # Result types
    AgentInvocationResult,
    # Exception classes
    ArtifactError,
    ArtifactNotFound,
    ArtifactLocked,
    ArtifactStale,
    MissingArtifact,
    MissingOutput,
    # Backward-compatible (deprecated)
    ArtifactRegistry,
    ArtifactVersion,
    ArtifactStatus,
    ArtifactLock,
    AgentInvoker,
)

# Error recovery (kept - valuable for production resilience)
from .error_recovery import (
    ErrorRecoverySystem,
    ErrorType,
    RecoveryStrategy,
    RecoveryStatus,
    RecoveryResult,
    UserOption,
)

# Main orchestrator (simplified to router + reasoning)
from .orchestrator import (
    ShipSOrchestrator,
    TaskResult,
)

# Backwards compatibility alias
MasterOrchestrator = ShipSOrchestrator


__all__ = [
    # Phase Literals
    "Phase",
    
    # State Logging (simplified)
    "TransitionLogger",
    "StateTransition",
    "TransitionReason",
    "TransitionError",
    "StateContext",
    
    # Backward-compatible (deprecated)
    "StateMachine",
    "OrchestratorState",
    
    # Quality Gates
    "QualityGate",
    "QualityGateRegistry",
    "QualityGateChecker",
    "GateCheck",
    "GateCheckStatus",
    
    # Artifact Helpers (new)
    "ensure_artifacts_exist",
    "get_artifact",
    "get_artifact_or_raise",
    "set_artifact",
    "merge_artifacts",
    "get_required_artifacts_for_phase",
    "check_phase_requirements",
    "ARTIFACT_DEPENDENCIES",
    
    # Artifact Types
    "AgentInvocationResult",
    "ArtifactError",
    "ArtifactNotFound",
    "ArtifactLocked",
    "ArtifactStale",
    "MissingArtifact",
    "MissingOutput",
    
    # Backward-compatible (deprecated)
    "ArtifactRegistry",
    "ArtifactVersion",
    "ArtifactStatus",
    "ArtifactLock",
    "AgentInvoker",
    
    # Error Recovery
    "ErrorRecoverySystem",
    "ErrorType",
    "RecoveryStrategy",
    "RecoveryStatus",
    "RecoveryResult",
    "UserOption",
    
    # Main Orchestrator
    "ShipSOrchestrator",
    "MasterOrchestrator",
    "TaskResult",
]
