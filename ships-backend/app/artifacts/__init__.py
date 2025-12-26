"""
ShipS* Artifact System

This package provides the artifact infrastructure for agent coordination,
quality enforcement, and auditability.

Exports:
    - All artifact models (PatternRegistry, ContractDefinitions, etc.)
    - ArtifactManager service
    - Convenience functions
"""

from app.artifacts.models import (
    # Enums
    GateStatus,
    PitfallStatus,
    FileStatus,
    AgentType,
    
    # Pattern Registry
    NamingConventions,
    AsyncPatterns,
    StateManagementPattern,
    ImportAliases,
    PatternRegistry,
    
    # Contract Definitions
    RequestSchema,
    ResponseSchema,
    ContractEndpoint,
    ContractDefinitions,
    
    # Quality Gates
    GateCheck,
    FixAttempt,
    QualityGate,
    QualityGateResults,
    
    # Agent Log
    AgentLogEntry,
    AgentConversationLog,
    
    # Context Map
    RelevantFile,
    ContextMap,
    
    # Dependency Graph
    DependencyNode,
    DependencyEdge,
    DependencyGraph,
    
    # Fix History
    FixRecord,
    FixHistory,
    
    # Pitfall Matrix
    PitfallCheck,
    PitfallCoverageMatrix,
)

from app.artifacts.artifact_manager import (
    ArtifactPaths,
    ArtifactManager,
    get_artifact_manager,
)


__all__ = [
    # Enums
    "GateStatus",
    "PitfallStatus",
    "FileStatus",
    "AgentType",
    
    # Pattern Registry
    "NamingConventions",
    "AsyncPatterns",
    "StateManagementPattern",
    "ImportAliases",
    "PatternRegistry",
    
    # Contract Definitions
    "RequestSchema",
    "ResponseSchema",
    "ContractEndpoint",
    "ContractDefinitions",
    
    # Quality Gates
    "GateCheck",
    "FixAttempt",
    "QualityGate",
    "QualityGateResults",
    
    # Agent Log
    "AgentLogEntry",
    "AgentConversationLog",
    
    # Context Map
    "RelevantFile",
    "ContextMap",
    
    # Dependency Graph
    "DependencyNode",
    "DependencyEdge",
    "DependencyGraph",
    
    # Fix History
    "FixRecord",
    "FixHistory",
    
    # Pitfall Matrix
    "PitfallCheck",
    "PitfallCoverageMatrix",
    
    # Manager
    "ArtifactPaths",
    "ArtifactManager",
    "get_artifact_manager",
]
