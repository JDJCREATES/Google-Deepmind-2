"""
ShipS* Validator Sub-Agent Package

The Validator is the GATE - it answers one question only:
"Is the system safe to proceed?"

It does NOT negotiate. It does NOT suggest. It PASSES or FAILS.
"""

from app.agents.sub_agents.validator.validator import Validator
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
from app.agents.sub_agents.validator.layers import (
    ValidationLayer,
    StructuralLayer,
    CompletenessLayer,
    DependencyLayer,
    ScopeLayer,
)

__all__ = [
    # Main agent
    "Validator",
    
    # Config
    "ValidatorConfig",
    "ValidatorInput",
    
    # Layers
    "ValidationLayer",
    "StructuralLayer",
    "CompletenessLayer",
    "DependencyLayer",
    "ScopeLayer",
    
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
