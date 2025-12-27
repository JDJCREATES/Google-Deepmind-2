"""
ShipS* Orchestrator Package

The central intelligence of the ShipS* system providing:
- State Machine: Deterministic state transitions
- Quality Gates: Enforce quality at every step
- Artifact Flow: Coordinate data between agents
- Error Recovery: Smart retries and escalation
"""

from app.orchestrator.state_machine import (
    StateMachine,
    OrchestratorState,
    TransitionReason,
    StateTransition,
    TransitionError,
    StateContext,
)

from app.orchestrator.quality_gates import (
    QualityGate,
    QualityGateRegistry,
    QualityGateChecker,
    GateCheck,
    GateCheckStatus,
)

from app.orchestrator.artifact_flow import (
    ArtifactRegistry,
    ArtifactVersion,
    ArtifactStatus,
    ArtifactLock,
    AgentInvoker,
    AgentInvocationResult,
    ArtifactError,
    ArtifactNotFound,
    ArtifactLocked,
    ArtifactStale,
    MissingArtifact,
    MissingOutput,
)

from app.orchestrator.error_recovery import (
    ErrorRecoverySystem,
    ErrorType,
    RecoveryStrategy,
    RecoveryStatus,
    RecoveryResult,
    UserOption,
)

from app.orchestrator.orchestrator import (
    ShipSOrchestrator,
    TaskResult,
)


__all__ = [
    # State Machine
    "StateMachine",
    "OrchestratorState",
    "TransitionReason",
    "StateTransition",
    "TransitionError",
    "StateContext",
    
    # Quality Gates
    "QualityGate",
    "QualityGateRegistry",
    "QualityGateChecker",
    "GateCheck",
    "GateCheckStatus",
    
    # Artifact Flow
    "ArtifactRegistry",
    "ArtifactVersion",
    "ArtifactStatus",
    "ArtifactLock",
    "AgentInvoker",
    "AgentInvocationResult",
    "ArtifactError",
    "ArtifactNotFound",
    "ArtifactLocked",
    "ArtifactStale",
    "MissingArtifact",
    "MissingOutput",
    
    # Error Recovery
    "ErrorRecoverySystem",
    "ErrorType",
    "RecoveryStrategy",
    "RecoveryStatus",
    "RecoveryResult",
    "UserOption",
    
    # Main Orchestrator
    "ShipSOrchestrator",
    "TaskResult",
]
