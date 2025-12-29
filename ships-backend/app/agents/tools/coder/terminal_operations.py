"""
Terminal Operations Tools

Agent tools for executing terminal commands.
Uses the secure terminal module for whitelisted command execution.
Supports interactive commands via PTY streaming with prompt auto-response.
"""

from typing import Dict, Any, List
import logging
import asyncio

from langchain_core.tools import tool

from app.terminal import (
    execute_command,
    execute_with_pty,
    validate_command,
    CommandRequest,
    ALLOWED_COMMANDS,
    PTYExecutionConfig,
)
from app.agents.tools.coder.context import get_project_root

logger = logging.getLogger("ships.coder")


def _should_use_pty(command: str) -> bool:
    """
    Determine if a command should use PTY execution.
    
    Strategy: ALWAYS use PTY for all commands.
    PTY handles both interactive and non-interactive commands safely,
    with automatic prompt detection and response.
    
    Args:
        command: The command to check.
        
    Returns:
        Always True - all commands use PTY for consistency and safety.
    """
    return True


@tool
def run_terminal_command(command: str, timeout: int = 300) -> Dict[str, Any]:
    """
    Run a whitelisted terminal command in the project directory.
    
    Automatically uses PTY execution for interactive commands
    (like scaffolding) to handle prompts gracefully.
    
    IMPORTANT: Only certain commands are allowed for security:
    - npm (install, run, build, etc.)
    - npx (create-vite, create-next-app, etc.)
    - yarn, pnpm
    - git (init, add, commit, etc.)
    - python, pip (requires approval)
    
    Args:
        command: The command to run (e.g., "npm install", "npx create-vite my-app")
        timeout: Maximum execution time in seconds (default: 300 = 5 minutes)
        
    Returns:
        Dict with success status, output, and execution details
    """
    try:
        # Get project root from secure context
        project_root = get_project_root()
        
        if not project_root:
            logger.error("[TERMINAL] ❌ No project folder selected")
            return {
                "success": False,
                "error": "No project folder selected. Please select a project first.",
                "command": command
            }
        
        # Validate command first
        is_valid, error, _ = validate_command(command, project_root)
        if not is_valid:
            logger.warning(f"[TERMINAL] ❌ Validation failed: {error}")
            return {
                "success": False,
                "error": error,
                "command": command
            }
        
        # Decide execution method
        use_pty = _should_use_pty(command)
        logger.info(f"[TERMINAL] 🚀 Executing ({('PTY' if use_pty else 'standard')}): {command}")
        
        # Run async executor
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            if use_pty:
                # Use PTY for interactive commands
                result = loop.run_until_complete(
                    execute_with_pty(
                        command=command,
                        cwd=project_root,
                        config=PTYExecutionConfig(
                            timeout=float(timeout),
                            auto_respond_prompts=True
                        )
                    )
                )
                
                logger.info(f"[TERMINAL] {'✅' if result.success else '❌'} PTY completed in {result.duration_ms}ms (handled {result.prompts_handled} prompts)")
                
                # Truncate output to save tokens
                output_preview = result.output[:300] + "\n...[output truncated]..." if len(result.output) > 300 else result.output
                
                return {
                    "success": result.success,
                    "exit_code": result.exit_code,
                    "output": output_preview,
                    "prompts_handled": result.prompts_handled,
                    "error": result.error,
                    "timed_out": result.timed_out,
                    "duration_ms": result.duration_ms,
                    "execution_mode": "pty"
                }
            else:
                # Use standard executor for simple commands
                result = loop.run_until_complete(
                    execute_command(CommandRequest(
                        command=command,
                        cwd=project_root,
                        timeout=timeout
                    ))
                )
                
                logger.info(f"[TERMINAL] {'✅' if result.success else '❌'} Command completed in {result.duration_ms}ms")
                
                return {
                    "success": result.success,
                    "exit_code": result.exit_code,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "error": result.error,
                    "timed_out": result.timed_out,
                    "duration_ms": result.duration_ms,
                    "execution_mode": "standard"
                }
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"[TERMINAL] ❌ Exception: {e}")
        return {
            "success": False,
            "error": str(e),
            "command": command
        }


@tool
def get_allowed_terminal_commands() -> Dict[str, Any]:
    """
    Get the list of allowed terminal command prefixes.
    
    Use this to understand what commands can be executed.
    
    Returns:
        Dict with list of allowed commands and their descriptions
    """
    return {
        "allowed_commands": [
            {
                "prefix": cmd.prefix,
                "description": cmd.description,
                "max_timeout": cmd.max_timeout,
                "requires_approval": cmd.requires_approval
            }
            for cmd in ALLOWED_COMMANDS
        ],
        "note": "Only commands starting with these prefixes are allowed.",
        "execution_mode": "pty",
        "execution_note": "All commands use PTY execution for interactive prompt handling."
    }


# Export all terminal tools
TERMINAL_TOOLS = [
    run_terminal_command,
    get_allowed_terminal_commands,
]

