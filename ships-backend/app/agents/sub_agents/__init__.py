"""
ShipS* Sub-Agents Package

Contains specialized agents for specific tasks:
- Planner: Converts intent to actionable plan artifacts
- Coder: Converts tasks to code changes
- Validator: The gate - pass/fail before execution
- Fixer: Repairs validation failures with minimal changes
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

from app.agents.sub_agents.validator import (
    Validator,
    ValidationReport,
    ValidationStatus,
    FailureLayer,
    RecommendedAction,
    Violation,
)

from app.agents.sub_agents.fixer import (
    Fixer,
    FixPlan,
    FixPatch,
    FixReport,
    FixerOutput,
    ReplanRequest,
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
    
    # Validator
    "Validator",
    "ValidationReport",
    "ValidationStatus",
    "FailureLayer",
    "RecommendedAction",
    "Violation",
    
    # Fixer
    "Fixer",
    "FixPlan",
    "FixPatch",
    "FixReport",
    "FixerOutput",
    "ReplanRequest",
]
