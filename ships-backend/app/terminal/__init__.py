"""
Terminal Module

Safe terminal execution for ShipS* backend.
Provides whitelisted command execution with validation.

Usage:
    from app.terminal import execute_command, validate_command, ALLOWED_COMMANDS
    
    result = await execute_command(CommandRequest(
        command="npm install",
        cwd="/path/to/project"
    ))
"""

# Re-export models
from .models import (
    CommandStatus,
    CommandRequest,
    CommandResult,
    AllowedCommand,
)

# Re-export security functions
from .security import (
    ALLOWED_COMMANDS,
    validate_command,
    is_path_safe,
    get_allowed_command_config,
)

# Re-export executor functions
from .executor import (
    execute_command,
    execute_command_sync,
)

__all__ = [
    # Models
    "CommandStatus",
    "CommandRequest",
    "CommandResult",
    "AllowedCommand",
    # Security
    "ALLOWED_COMMANDS",
    "validate_command",
    "is_path_safe",
    "get_allowed_command_config",
    # Executor
    "execute_command",
    "execute_command_sync",
]
