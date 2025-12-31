"""
ShipS* Agent Tools Package

Contains tools organized by agent:
- planner/: Tools for planning and task creation
- coder/: Tools for code generation and diffs
- validator/: Tools for validation layers
- fixer/: Tools for fixing validation failures

All tools use the @tool decorator from langchain_core
and are designed for use with langgraph.prebuilt.create_react_agent.

NOTE: Tools are imported lazily to avoid circular imports.
Import from submodules directly, e.g.:
  from app.agents.tools.coder import CODER_TOOLS
  from app.agents.tools.planner import PLANNER_TOOLS
"""

# Don't import at module level to avoid circular imports
# Import directly from submodules when needed.
