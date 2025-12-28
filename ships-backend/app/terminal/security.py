"""
Terminal Security Module

Command validation and whitelisting for safe terminal execution.
This is the security gate - all commands must pass validation.
"""

import re
import os
from pathlib import Path
from typing import Tuple, Optional, List
import logging

from .models import AllowedCommand

logger = logging.getLogger("ships.terminal")


# ============================================================================
# WHITELISTED COMMANDS
# ============================================================================

ALLOWED_COMMANDS: List[AllowedCommand] = [
    AllowedCommand(prefix="npm", description="Node package manager", max_timeout=300, requires_approval=False),
    AllowedCommand(prefix="npx", description="NPM package runner", max_timeout=300, requires_approval=False),
    AllowedCommand(prefix="yarn", description="Yarn package manager", max_timeout=300, requires_approval=False),
    AllowedCommand(prefix="pnpm", description="PNPM package manager", max_timeout=300, requires_approval=False),
    AllowedCommand(prefix="git", description="Git version control", max_timeout=60, requires_approval=False),
    AllowedCommand(prefix="python", description="Python interpreter", max_timeout=60, requires_approval=True),
    AllowedCommand(prefix="py", description="Python interpreter (Windows)", max_timeout=60, requires_approval=True),
    AllowedCommand(prefix="pip", description="Python package manager", max_timeout=300, requires_approval=True),
    AllowedCommand(prefix="node", description="Node.js runtime", max_timeout=60, requires_approval=True),
]


# ============================================================================
# BLOCKED PATTERNS
# ============================================================================

BLOCKED_PATTERNS: List[re.Pattern] = [
    re.compile(r"rm\s+-rf", re.IGNORECASE),           # Recursive delete
    re.compile(r"rm\s+--force", re.IGNORECASE),       # Force delete
    re.compile(r"del\s+/[fqs]", re.IGNORECASE),       # Windows force delete
    re.compile(r"rmdir\s+/s", re.IGNORECASE),         # Windows recursive delete
    re.compile(r"format\s+", re.IGNORECASE),          # Disk format
    re.compile(r"mkfs\s+", re.IGNORECASE),            # Make filesystem
    re.compile(r"\|\s*sh", re.IGNORECASE),            # Pipe to shell
    re.compile(r"\|\s*bash", re.IGNORECASE),          # Pipe to bash
    re.compile(r"\|\s*cmd", re.IGNORECASE),           # Pipe to cmd
    re.compile(r";\s*rm", re.IGNORECASE),             # Command chain to rm
    re.compile(r"&&\s*rm", re.IGNORECASE),            # Command chain to rm
    re.compile(r"sudo\s+", re.IGNORECASE),            # Privilege escalation
    re.compile(r"chmod\s+", re.IGNORECASE),           # Permission changes
    re.compile(r"chown\s+", re.IGNORECASE),           # Ownership changes
    re.compile(r"curl.*\|\s*sh", re.IGNORECASE),      # Curl pipe to shell
    re.compile(r"wget.*\|\s*sh", re.IGNORECASE),      # Wget pipe to shell
    re.compile(r"eval\s+", re.IGNORECASE),            # Eval execution
    re.compile(r"`.*`"),                              # Backtick execution
    re.compile(r"\$\("),                              # Subshell execution
    re.compile(r">\s*/etc/", re.IGNORECASE),          # Write to /etc
    re.compile(r">\s*~/.bashrc", re.IGNORECASE),      # Write to bashrc
    re.compile(r">\s*~/.profile", re.IGNORECASE),     # Write to profile
]

BLOCKED_SUBCOMMANDS: dict = {
    "npm": ["exec", "x"],  # npm exec can run arbitrary code
    "git": ["filter-branch", "gc", "prune"],  # Destructive git commands
}


# ============================================================================
# FORBIDDEN PATHS
# ============================================================================

FORBIDDEN_PATHS = [
    "c:\\windows",
    "c:\\program files",
    "c:\\programdata",
    "/system",
    "/usr/bin",
    "/bin",
    "/etc",
    "/var",
]


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def is_path_safe(project_path: str) -> Tuple[bool, str]:
    """
    Validate that a path is safe for command execution.
    
    Returns:
        Tuple of (is_safe, error_message)
    """
    if not project_path:
        return False, "No project path provided"
    
    resolved = Path(project_path).resolve()
    
    if not resolved.exists():
        return False, f"Path does not exist: {project_path}"
    
    if not resolved.is_dir():
        return False, f"Path is not a directory: {project_path}"
    
    # Check forbidden paths
    normalized = str(resolved).lower().replace("\\", "/")
    for forbidden in FORBIDDEN_PATHS:
        if normalized.startswith(forbidden.replace("\\", "/")):
            return False, f"Cannot execute commands in system directory: {forbidden}"
    
    # Check it's not the backend directory
    backend_dir = Path(__file__).resolve().parent.parent.parent
    if str(resolved).startswith(str(backend_dir)):
        return False, "Cannot execute commands in the backend directory"
    
    return True, ""


def get_allowed_command_config(command: str) -> Optional[AllowedCommand]:
    """Get the config for an allowed command prefix."""
    cmd_base = command.strip().split()[0].lower()
    for ac in ALLOWED_COMMANDS:
        if ac.prefix == cmd_base:
            return ac
    return None


def validate_command(command: str, cwd: str) -> Tuple[bool, str, Optional[str]]:
    """
    Validate a command for safe execution.
    
    Returns:
        Tuple of (is_valid, error_message, sanitized_command)
    """
    trimmed = command.strip()
    
    if not trimmed:
        return False, "Empty command", None
    
    # Validate working directory
    path_safe, path_error = is_path_safe(cwd)
    if not path_safe:
        return False, path_error, None
    
    # Parse command
    parts = trimmed.split()
    cmd_base = parts[0].lower()
    sub_command = parts[1].lower() if len(parts) > 1 else None
    
    # Check whitelist
    allowed_config = get_allowed_command_config(trimmed)
    if not allowed_config:
        allowed_list = ", ".join(ac.prefix for ac in ALLOWED_COMMANDS)
        return False, f"Command '{cmd_base}' is not allowed. Whitelist: {allowed_list}", None
    
    # Check blocked subcommands
    blocked_subs = BLOCKED_SUBCOMMANDS.get(cmd_base, [])
    if sub_command and sub_command in blocked_subs:
        return False, f"Subcommand '{cmd_base} {sub_command}' is blocked for security", None
    
    # Check blocked patterns
    for pattern in BLOCKED_PATTERNS:
        if pattern.search(trimmed):
            return False, "Command contains blocked pattern", None
    
    # Check path traversal
    if ".." in trimmed:
        return False, "Path traversal (..) is not allowed", None
    
    logger.info(f"[SECURITY] ✅ Command validated: {trimmed[:50]}...")
    return True, "", trimmed
