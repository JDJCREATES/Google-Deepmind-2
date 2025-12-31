"""
ShipS* Validator Sub-Agent Package

The Validator is the GATE - it answers one question only:
"Is the system safe to proceed?"

It does NOT negotiate. It does NOT suggest. It PASSES or FAILS.

Note: Layers are now in central location: app/agents/tools/validator/
Import them directly from there if needed.
"""

# Import models FIRST (no dependencies on other modules)
from app.agents.sub_agents.validator.models import (
    # Core artifacts
    ValidationReport,
    Violation,
    LayerResult,
    ValidatorInput,
    ValidatorConfig,
    
    # Violation types
    StructuralViolation,
    CompletenessViolation,
    DependencyViolation,
    ScopeViolation,
    
    # Enums
    ValidationStatus,
    FailureLayer,
    RecommendedAction,
    ViolationSeverity,
)

# Import Validator (depends on models and uses layers from tools internally)
from app.agents.sub_agents.validator.validator import Validator

__all__ = [
    # Main agent
    "Validator",
    
    # Config
    "ValidatorConfig",
    "ValidatorInput",
    
    # Artifacts
    "ValidationReport",
    "Violation",
    "LayerResult",
    
    # Violation types
    "StructuralViolation",
    "CompletenessViolation",
    "DependencyViolation",
    "ScopeViolation",
    
    # Enums
    "ValidationStatus",
    "FailureLayer",
    "RecommendedAction",
    "ViolationSeverity",
]
