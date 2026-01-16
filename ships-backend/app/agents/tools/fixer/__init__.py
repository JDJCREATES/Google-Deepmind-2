"""
ShipS* Fixer Tools

LangChain tools for the Fixer agent.
Organized into modules for maintainability.

Modules:
- strategies: Fix strategies for each validation layer
- fixer_tools: @tool decorated functions for LangGraph

Integrates with Collective Intelligence for proven fix patterns.
"""

# IMPORTANT: Import strategies FIRST to avoid circular import with sub_agents
# The strategies module only imports from models, not from fixer.py
from app.agents.tools.fixer.strategies import (
    FixStrategy,
    StructuralFixer,
    CompletenessFixer,
    DependencyFixer,
    ScopeFixer,
    FixerConfig,
)

# Then import tool functions (these import strategies internally)
from app.agents.tools.fixer.fixer_tools import (
    triage_violations,
    generate_todo_fix,
    generate_empty_function_fix,
    create_fix_patch,
    create_replan_request,
    run_preflight_checks,
    # Collective Intelligence tools
    get_fix_suggestions,
    report_fix_outcome,
    set_fixer_knowledge,
)

# Import write_file_to_disk from coder tools (now modular)
from app.agents.tools.coder import (
    write_file_to_disk,
    read_file_from_disk,
    apply_source_edits,   # For targeted line-by-line edits
    insert_content,       # For inserting new content
    run_terminal_command,
)

# Combined export of all tools for the Fixer agent
# EMPOWERED: Fixer now has full access to read, write, edit, and run commands
FIXER_TOOLS = [
    # Core file operations - FULL ACCESS like Coder
    read_file_from_disk,      # Read files to understand what needs fixing
    write_file_to_disk,       # Write/overwrite files
    apply_source_edits,       # Make targeted edits (preferred for modifications)
    insert_content,           # Insert new content at specific locations
    run_terminal_command,     # Run npm build, tsc, tests to verify fixes
    
    # Specialized fixer tools (optional use)
    triage_violations,
    generate_todo_fix,
    generate_empty_function_fix,
    create_fix_patch,
    run_preflight_checks,
    
    # Collective Intelligence
    get_fix_suggestions,
    report_fix_outcome,
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
    
    # Collective Intelligence
    "get_fix_suggestions",
    "report_fix_outcome",
    "set_fixer_knowledge",
    
    # Core file operations (re-exported from coder)
    "read_file_from_disk",
    "write_file_to_disk",
    "apply_source_edits",
    "insert_content",
    "run_terminal_command",
    
    # Tool list
    "FIXER_TOOLS",
]
