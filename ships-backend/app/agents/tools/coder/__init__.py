"""
ShipS* Coder Tools

LangChain tools for the Coder agent using @tool decorator.
Organized into modules for maintainability.

Modules:
- context: Secure project path management
- file_operations: Read, write, list files
- code_analysis: Diffs, language detection, risk assessment
"""

# Re-export context functions for use by other modules
from .context import (
    set_project_root,
    get_project_root,
    validate_project_path,
    is_path_safe,
)

# Import tools from modules
from .file_operations import (
    write_file_to_disk,
    read_file_from_disk,
    list_directory,
    FILE_OPERATION_TOOLS,
)

from .code_analysis import (
    detect_language,
    generate_file_diff,
    assess_change_risk,
    analyze_task,
    check_imports,
    create_file_change,
    build_commit_message,
    CODE_ANALYSIS_TOOLS,
)

# Combined export of all tools for the Coder agent
# File operations are listed FIRST as they are the primary tools
CODER_TOOLS = [
    # Primary file operations
    write_file_to_disk,
    read_file_from_disk,
    list_directory,
    # Code analysis
    analyze_task,
    generate_file_diff,
    detect_language,
    assess_change_risk,
    create_file_change,
    build_commit_message,
    check_imports,
]

__all__ = [
    # Context
    "set_project_root",
    "get_project_root",
    "validate_project_path",
    "is_path_safe",
    # File operations
    "write_file_to_disk",
    "read_file_from_disk", 
    "list_directory",
    # Code analysis
    "detect_language",
    "generate_file_diff",
    "assess_change_risk",
    "analyze_task",
    "check_imports",
    "create_file_change",
    "build_commit_message",
    # Tool lists
    "CODER_TOOLS",
    "FILE_OPERATION_TOOLS",
    "CODE_ANALYSIS_TOOLS",
]
