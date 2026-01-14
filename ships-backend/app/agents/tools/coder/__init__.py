"""
ShipS* Coder Tools

LangChain tools for the Coder agent using @tool decorator.
Organized into modules for maintainability.

Modules:
- context: Secure project path management
- file_operations: Read, write, list files
- code_analysis: Diffs, language detection, risk assessment
- terminal_operations: Run commands (npm, git, etc.)
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
    write_files_batch,
    read_file_from_disk,
    list_directory,
    create_directory,
    create_directories,
    view_source_code,
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

from .terminal_operations import (
    run_terminal_command,
    get_allowed_terminal_commands,
    TERMINAL_TOOLS,
)

from .edit_operations import (
    apply_source_edits,
    insert_content,
    EDIT_TOOLS,
)

from .file_tree import scan_project_tree, get_file_tree, get_artifact

from .artifact_tools import (
    update_task_status,
    update_folder_map_status,
    add_implementation_note,
    ARTIFACT_TOOLS,
)

from .search_tools import (
    search_codebase,
    query_call_graph,
    get_file_dependencies,
    SEARCH_TOOLS,
)

# Combined export of all tools for the Coder agent
# Edit tools listed FIRST as they are preferred for modifications
# NOTE: Terminal commands removed - Validator handles build/test
CODER_TOOLS = [
    # Edit operations (preferred for modifying existing files - saves tokens!)
    apply_source_edits,
    insert_content,
    # Primary file operations
    view_source_code,
    write_file_to_disk,
    write_files_batch,  # PREFERRED for multiple files - reduces iterations
    read_file_from_disk,
    list_directory,
    get_file_tree,      # Prefers .ships/ artifact, falls back to scan
    get_artifact,        # Read any artifact from .ships/
    # Artifact updates (LLM-editable artifacts)
    update_task_status,
    update_folder_map_status,
    add_implementation_note,
    # Search & Navigation (new!)
    search_codebase,
    query_call_graph,
    get_file_dependencies,
    # Code analysis (minimal - most is done in prompt)
    generate_file_diff,
    detect_language,
]

__all__ = [
    # Context
    "set_project_root",
    "get_project_root",
    "validate_project_path",
    "is_path_safe",
    # Edit operations (preferred for modifications)
    "apply_source_edits",
    "insert_content",
    # File operations
    "write_file_to_disk",
    "write_files_batch",
    "read_file_from_disk", 
    "list_directory",
    "create_directory",
    "create_directories",
    "view_source_code",
    "scan_project_tree",
    "get_file_tree",
    "get_artifact",
    # Search & Navigation
    "search_codebase",
    "query_call_graph",
    "get_file_dependencies",
    # Terminal operations
    "run_terminal_command",
    "get_allowed_terminal_commands",
    # Code analysis
    "detect_language",
    "generate_file_diff",
    "assess_change_risk",
    "analyze_task",
    "check_imports",
    "create_file_change",
    "build_commit_message",
    # Tool lists
    "FILE_OPERATION_TOOLS",
    "CODE_ANALYSIS_TOOLS",
    "TERMINAL_TOOLS",
    "EDIT_TOOLS",
    "SEARCH_TOOLS",
    "CODER_TOOLS",
]
