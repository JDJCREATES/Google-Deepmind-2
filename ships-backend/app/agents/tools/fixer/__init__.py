"""
ShipS* Fixer Tools

LangChain tools for the Fixer agent.
Organized into modules for maintainability.

Modules:
- strategies: Fix strategies for each validation layer
- fixer_tools: @tool decorated functions for LangGraph
"""

# Export fix strategies
from app.agents.tools.fixer.strategies import (
    FixStrategy,
    StructuralFixer,
    CompletenessFixer,
    DependencyFixer,
    ScopeFixer,
    FixerConfig,
)

# Export @tool decorated functions
from app.agents.tools.fixer.fixer_tools import (
    triage_violations,
    generate_todo_fix,
    generate_empty_function_fix,
    create_fix_patch,
    create_replan_request,
    run_preflight_checks,
)

# Import write_file_to_disk from coder tools (now modular)
from app.agents.tools.coder import write_file_to_disk

# Combined export of all tools for the Fixer agent
FIXER_TOOLS = [
    triage_violations,
    generate_todo_fix,
    generate_empty_function_fix,
    create_fix_patch,
    create_replan_request,
    run_preflight_checks,
    write_file_to_disk,  # Fixer can now write fixes to disk
]

__all__ = [
    # Strategies
    "FixStrategy",
    "StructuralFixer",
    "CompletenessFixer",
    "DependencyFixer",
    "ScopeFixer",
    "FixerConfig",
    
    # Tool functions
    "triage_violations",
    "generate_todo_fix",
    "generate_empty_function_fix",
    "create_fix_patch",
    "create_replan_request",
    "run_preflight_checks",
    
    # Re-exports
    "write_file_to_disk",
    
    # Tool list
    "FIXER_TOOLS",
]
