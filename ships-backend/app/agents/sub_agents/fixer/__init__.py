"""
ShipS* Fixer Sub-Agent Package

The Fixer produces the smallest safe, auditable remediation
that moves the system toward Validator: pass.
"""

from app.agents.sub_agents.fixer.fixer import Fixer
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
from app.agents.sub_agents.fixer.strategies import (
    FixStrategy,
    StructuralFixer,
    CompletenessFixer,
    DependencyFixer,
    ScopeFixer,
)

__all__ = [
    # Main agent
    "Fixer",
    
    # Config
    "FixerConfig",
    
    # Strategies
    "FixStrategy",
    "StructuralFixer",
    "CompletenessFixer",
    "DependencyFixer",
    "ScopeFixer",
    
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
