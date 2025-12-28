"""
Terminal Operations Tools

Agent tools for executing terminal commands.
Uses the secure terminal module for whitelisted command execution.
"""

from typing import Dict, Any, List
import logging
import asyncio

from langchain_core.tools import tool

from app.terminal import (
    execute_command,
    validate_command,
    CommandRequest,
    ALLOWED_COMMANDS,
)
from app.agents.tools.coder.context import get_project_root

logger = logging.getLogger("ships.coder")


@tool
def run_terminal_command(command: str, timeout: int = 60) -> Dict[str, Any]:
    """
    Run a whitelisted terminal command in the project directory.
    
    IMPORTANT: Only certain commands are allowed for security:
    - npm (install, run, build, etc.)
    - npx (create-vite, create-next-app, etc.)
    - yarn, pnpm
    - git (init, add, commit, etc.)
    - python, pip (requires approval)
    
    Args:
        command: The command to run (e.g., "npm install", "npx create-vite my-app")
        timeout: Maximum execution time in seconds (default: 60)
        
    Returns:
        Dict with success status, stdout, stderr, and exit_code
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
        
        # Execute the command
        logger.info(f"[TERMINAL] 🚀 Executing: {command}")
        
        # Run async executor in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                execute_command(CommandRequest(
                    command=command,
                    cwd=project_root,
                    timeout=timeout
                ))
            )
        finally:
            loop.close()
        
        logger.info(f"[TERMINAL] {'✅' if result.success else '❌'} Command completed in {result.duration_ms}ms")
        
        return {
            "success": result.success,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "error": result.error,
            "timed_out": result.timed_out,
            "duration_ms": result.duration_ms
        }
        
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
        "note": "Only commands starting with these prefixes are allowed."
    }


# Export all terminal tools
TERMINAL_TOOLS = [
    run_terminal_command,
    get_allowed_terminal_commands,
]
