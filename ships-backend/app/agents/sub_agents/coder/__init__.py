"""
ShipS* Coder Sub-Agent Package

The Coder converts Planner tasks into minimal, reviewable code changes.

Note: Tools are in the central location: app/agents/tools/coder/
This __init__.py only exports the Coder agent and its models.
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

__all__ = [
    # Main agent
    "Coder",
    
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
