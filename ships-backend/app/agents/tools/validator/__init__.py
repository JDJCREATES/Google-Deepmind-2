"""
ShipS* Validator Tools

LangChain tools for the Validator agent.
Organized into modules for maintainability.

Modules:
- layers: The 4 validation layers (Structural, Completeness, Dependency, Scope)
- validation_tools: @tool decorated functions for LangGraph
"""

# Export validation layers
from app.agents.tools.validator.layers import (
    ValidationLayer,
    StructuralLayer,
    CompletenessLayer,
    DependencyLayer,
    ScopeLayer,
    TypeScriptLayer,
    LanguageCheckerLayer,
)

# Export @tool decorated functions
from app.agents.tools.validator.validation_tools import (
    validate_structural,
    validate_completeness,
    validate_dependencies,
    validate_scope,
    create_validation_report,
    verify_visually,
)

# Combined export of all tools for the Validator agent
VALIDATOR_TOOLS = [
    validate_structural,
    validate_completeness,
    validate_dependencies,
    validate_scope,
    create_validation_report,
    verify_visually,
]

__all__ = [
    # Layers
    "ValidationLayer",
    "StructuralLayer",
    "CompletenessLayer",
    "DependencyLayer",
    "ScopeLayer",
    "TypeScriptLayer",
    
    # Tool functions
    "validate_structural",
    "validate_completeness",
    "validate_dependencies",
    "validate_scope",
    "create_validation_report",
    "verify_visually",
    
    # Tool list
    "VALIDATOR_TOOLS",
]
