"""
ShipS* Planner Tools

LangChain tools for the Planner agent using @tool decorator.
Organized into modules for maintainability.

Modules:
- planner_tools: Artifact assembly, validation, confidence estimation
"""

# Export tools from modules
from app.agents.tools.planner.planner_tools import PlannerTools

# Import file tools from coder tools (modular)
from app.agents.tools.coder import (
    write_file_to_disk, 
    list_directory, 
    create_directory,
)
from app.agents.tools.coder.terminal_operations import run_terminal_command

# Combined export of all tools for the Planner agent
# Tools re-exported from coder for project scaffolding
PLANNER_TOOLS = [
    list_directory,          # Check if project exists
    run_terminal_command,    # npx create-vite, npm install (first time only)
    create_directory,        # Create folder structure from plan
    write_file_to_disk,      # Write plan artifacts
]

__all__ = [
    # Tool class
    "PlannerTools",
    
    # Exported tools
    "PLANNER_TOOLS",
    
    # Re-exports from coder
    "list_directory",
    "run_terminal_command",
    "create_directory",
    "write_file_to_disk",
]
