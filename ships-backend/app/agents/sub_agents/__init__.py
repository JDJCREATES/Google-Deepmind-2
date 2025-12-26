"""
ShipS* Sub-Agents Package

Contains specialized agents for specific tasks:
- Planner: Converts intent to actionable plan artifacts
- Coder: Converts tasks to code changes
"""

from app.agents.sub_agents.planner import (
    Planner,
    PlanManifest,
    TaskList,
    Task,
    FolderMap,
    APIContracts,
    DependencyPlan,
    ValidationChecklist,
    RiskReport,
)

from app.agents.sub_agents.coder import (
    Coder,
    FileChangeSet,
    FileChange,
    TestBundle,
    CommitIntent,
    ImplementationReport,
    PreflightCheck,
    CoderOutput,
)

__all__ = [
    # Planner
    "Planner",
    "PlanManifest",
    "TaskList",
    "Task",
    "FolderMap",
    "APIContracts",
    "DependencyPlan",
    "ValidationChecklist",
    "RiskReport",
    
    # Coder
    "Coder",
    "FileChangeSet",
    "FileChange",
    "TestBundle",
    "CommitIntent",
    "ImplementationReport",
    "PreflightCheck",
    "CoderOutput",
]
