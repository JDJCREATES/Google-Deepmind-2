"""
ShipS* Fixer Sub-Agent Package

The Fixer produces the smallest safe, auditable remediation
that moves the system toward Validator: pass.

Note: Strategies are now in central location: app/agents/tools/fixer/
Import them directly from there if needed.
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

# Import Fixer (depends on models and uses strategies from tools internally)
from app.agents.sub_agents.fixer.fixer import Fixer

__all__ = [
    # Main agent
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
