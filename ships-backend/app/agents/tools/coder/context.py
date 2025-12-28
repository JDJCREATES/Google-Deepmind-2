"""
Project Context Management

Secure project path handling. The LLM never sees or controls these paths.
Set by the system before agents run.
"""

import logging
from pathlib import Path

logger = logging.getLogger("ships.coder")

# ============================================================================
# SECURE PROJECT PATH CONTEXT
# This is set by the system before the coder runs, NEVER by the LLM
# ============================================================================
_project_context = {
    "project_root": None  # None means no project selected
}


def set_project_root(path: str) -> None:
    """Set the project root path (called by system, not LLM)."""
    _project_context["project_root"] = path
    logger.info(f"[CODER] 📁 Project root set to: {path}")


def get_project_root() -> str | None:
    """Get the current project root path."""
    return _project_context.get("project_root")


def validate_project_path() -> tuple[bool, str]:
    """
    Validate that a project path is set and usable.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    project_root = get_project_root()
    
    if not project_root or project_root == "." or project_root == "":
        return False, "No project folder selected. Please use the Electron app to select a project folder first."
    
    resolved = Path(project_root).resolve()
    if not resolved.exists():
        return False, f"Project path does not exist: {project_root}"
    
    if not resolved.is_dir():
        return False, f"Project path is not a directory: {project_root}"
    
    return True, ""


def get_backend_dir() -> Path:
    """Get the ships-backend directory (for safety checks)."""
    return Path(__file__).resolve().parent.parent.parent.parent


def is_path_safe(file_path: str) -> tuple[bool, str]:
    """
    Check if a file path is safe to access.
    
    Prevents:
    - Path traversal attacks
    - Writing to backend directory
    
    Returns:
        Tuple of (is_safe, error_message)
    """
    is_valid, error = validate_project_path()
    if not is_valid:
        return False, error
    
    project_root = get_project_root()
    resolved_root = Path(project_root).resolve()
    resolved_path = (resolved_root / file_path).resolve()
    
    # Check path traversal
    if not str(resolved_path).startswith(str(resolved_root)):
        return False, "Invalid file path - cannot escape project directory"
    
    # Check backend directory
    backend_dir = get_backend_dir()
    if str(resolved_root).startswith(str(backend_dir)):
        return False, "Cannot write to the ShipS* backend. Please select a user project."
    
    return True, ""
