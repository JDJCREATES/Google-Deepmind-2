"""
ShipS* Sub-Agents Package

Contains specialized agents for specific tasks:
- Planner: Converts intent to actionable plan artifacts
- Coder: Converts tasks to code changes
- Validator: The gate - pass/fail before execution
- Fixer: Repairs validation failures with minimal changes

Note: Uses lazy imports to avoid circular dependencies with tools modules.
Import agents directly from their submodules when needed:
  from app.agents.sub_agents.fixer.fixer import Fixer
  from app.agents.sub_agents.coder.coder import Coder
"""

# Import models directly - these are pure Pydantic and have no circular deps
from app.agents.sub_agents.planner.models import (
    PlanManifest,
    TaskList,
    Task,
    FolderMap,
    APIContracts,
    DependencyPlan,
    ValidationChecklist,
    RiskReport,
)

from app.agents.sub_agents.coder.models import (
    FileChangeSet,
    FileChange,
    TestBundle,
    CommitIntent,
    ImplementationReport,
    PreflightCheck,
    CoderOutput,
)

from app.agents.sub_agents.validator.models import (
    ValidationReport,
    ValidationStatus,
    FailureLayer,
    RecommendedAction,
    Violation,
)

from app.agents.sub_agents.fixer.models import (
    FixPlan,
    FixPatch,
    FixReport,
    FixerOutput,
    ReplanRequest,
)


def __getattr__(name):
    """Lazy import agents to avoid circular dependency with tools."""
    if name == "Planner":
        from app.agents.sub_agents.planner.planner import Planner
        return Planner
    elif name == "Coder":
        from app.agents.sub_agents.coder.coder import Coder
        return Coder
    elif name == "Validator":
        from app.agents.sub_agents.validator.validator import Validator
        return Validator
    elif name == "Fixer":
        from app.agents.sub_agents.fixer.fixer import Fixer
        return Fixer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Agents (lazy loaded)
    "Planner",
    "Coder",
    "Validator",
    "Fixer",
    
    # Planner models
    "PlanManifest",
    "TaskList",
    "Task",
    "FolderMap",
    "APIContracts",
    "DependencyPlan",
    "ValidationChecklist",
    "RiskReport",
    
    # Coder models
    "FileChangeSet",
    "FileChange",
    "TestBundle",
    "CommitIntent",
    "ImplementationReport",
    "PreflightCheck",
    "CoderOutput",
    
    # Validator models
    "ValidationReport",
    "ValidationStatus",
    "FailureLayer",
    "RecommendedAction",
    "Violation",
    
    # Fixer models
    "FixPlan",
    "FixPatch",
    "FixReport",
    "FixerOutput",
    "ReplanRequest",
]
