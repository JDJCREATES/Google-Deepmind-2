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
    
    # For interactive commands with PTY:
    from app.terminal import execute_with_pty, PTYExecutionConfig
    
    result = await execute_with_pty(
        command="npx create-vite@latest .",
        cwd="/path/to/project"
    )
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

# Re-export PTY executor (for interactive commands)
from .pty_executor import (
    execute_with_pty,
    execute_command_streaming,
    PTYExecutionConfig,
    PTYResult,
)

# Re-export prompt patterns
from .prompt_patterns import (
    detect_prompt,
    get_auto_response,
    PromptType,
    PromptPattern,
    PROMPT_PATTERNS,
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
    # Standard Executor
    "execute_command",
    "execute_command_sync",
    # PTY Executor (interactive support)
    "execute_with_pty",
    "execute_command_streaming",
    "PTYExecutionConfig",
    "PTYResult",
    # Prompt Patterns
    "detect_prompt",
    "get_auto_response",
    "PromptType",
    "PromptPattern",
    "PROMPT_PATTERNS",
]

