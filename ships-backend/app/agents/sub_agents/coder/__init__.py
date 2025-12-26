"""
ShipS* Coder Sub-Agent Package

The Coder converts Planner tasks into minimal, reviewable code changes.
"""

from app.agents.sub_agents.coder.coder import Coder
from app.agents.sub_agents.coder.models import (
    # Core artifacts
    FileChangeSet,
    FileChange,
    FileDiff,
    TestBundle,
    TestCase,
    CommitIntent,
    ImplementationReport,
    PreflightCheck,
    FollowUpTasks,
    FollowUpTask,
    CoderOutput,
    CoderMetadata,
    
    # Enums
    FileOperation,
    ChangeRisk,
    CheckStatus,
    TestType,
    SemanticVersionBump,
    
    # Supporting types
    CheckResult,
    InferredItem,
    EdgeCase,
    TestAssertion,
)
from app.agents.sub_agents.coder.components import (
    CoderComponentConfig,
    TaskInterpreter,
    ContextConsumer,
    StyleEnforcer,
    ImplementationSynthesizer,
    DependencyVerifier,
    TestAuthor,
    PreflightChecker,
)
from app.agents.sub_agents.coder.tools import (
    CodeTools,
    DiffGenerator,
    CommitBuilder,
    ReportBuilder,
)

__all__ = [
    # Main agent
    "Coder",
    
    # Config
    "CoderComponentConfig",
    
    # Tools
    "CodeTools",
    "DiffGenerator",
    "CommitBuilder",
    "ReportBuilder",
    
    # Components
    "TaskInterpreter",
    "ContextConsumer",
    "StyleEnforcer",
    "ImplementationSynthesizer",
    "DependencyVerifier",
    "TestAuthor",
    "PreflightChecker",
    
    # Artifacts
    "FileChangeSet",
    "FileChange",
    "FileDiff",
    "TestBundle",
    "TestCase",
    "CommitIntent",
    "ImplementationReport",
    "PreflightCheck",
    "FollowUpTasks",
    "FollowUpTask",
    "CoderOutput",
    "CoderMetadata",
    
    # Enums
    "FileOperation",
    "ChangeRisk",
    "CheckStatus",
    "TestType",
    "SemanticVersionBump",
    
    # Supporting types
    "CheckResult",
    "InferredItem",
    "EdgeCase",
    "TestAssertion",
]
