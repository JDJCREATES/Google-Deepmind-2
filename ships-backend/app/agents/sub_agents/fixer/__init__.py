"""
ShipS* Fixer Sub-Agent Package

The Fixer produces the smallest safe, auditable remediation
that moves the system toward Validator: pass.

Note: Strategies are now in central location: app/agents/tools/fixer/
Import them directly from there if needed.

Note: Uses lazy import for Fixer to avoid circular dependency with tools.
"""

# Import models FIRST (no dependencies on other modules)
from app.agents.sub_agents.fixer.models import (
    # Core artifacts
    FixPlan,
    FixPatch,
    FixChange,
    FixTestBundle,
    FixTest,
    FixReport,
    FixAttemptLog,
    ReplanRequest,
    FixerOutput,
    FixerConfig,
    ViolationFix,
    
    # Enums
    FixScope,
    FixApproach,
    FixRisk,
    FixResult,
    ApprovalType,
)


def __getattr__(name):
    """Lazy import Fixer to avoid circular dependency with tools.fixer.strategies."""
    if name == "Fixer":
        from app.agents.sub_agents.fixer.fixer import Fixer
        return Fixer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Main agent (lazy loaded)
    "Fixer",
    
    # Config
    "FixerConfig",
    
    # Artifacts
    "FixPlan",
    "FixPatch",
    "FixChange",
    "FixTestBundle",
    "FixTest",
    "FixReport",
    "FixAttemptLog",
    "ReplanRequest",
    "FixerOutput",
    "ViolationFix",
    
    # Enums
    "FixScope",
    "FixApproach",
    "FixRisk",
    "FixResult",
    "ApprovalType",
]
