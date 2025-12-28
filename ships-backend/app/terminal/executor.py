"""
Terminal Executor Module

Executes validated commands using subprocess.
Handles timeouts and output streaming.
"""

import subprocess
import time
import platform
import logging
from typing import Optional, Callable
from pathlib import Path

from .models import CommandRequest, CommandResult
from .security import validate_command, get_allowed_command_config

logger = logging.getLogger("ships.terminal")


def get_shell_config() -> tuple[str, list[str]]:
    """Get shell configuration for the current platform."""
    if platform.system() == "Windows":
        return "cmd.exe", ["/c"]
    return "/bin/sh", ["-c"]


async def execute_command(request: CommandRequest) -> CommandResult:
    """
    Execute a command and return the result.
    
    This is the main async execution function for agent tools.
    """
    start_time = time.time()
    
    # Validate first
    is_valid, error, sanitized = validate_command(request.command, request.cwd)
    if not is_valid:
        logger.warning(f"[EXECUTOR] ❌ Validation failed: {error}")
        return CommandResult(
            success=False,
            error=error,
            duration_ms=int((time.time() - start_time) * 1000)
        )
    
    # Get timeout from config
    cmd_config = get_allowed_command_config(request.command)
    timeout = request.timeout or (cmd_config.max_timeout if cmd_config else 60)
    
    shell, shell_args = get_shell_config()
    
    try:
        logger.info(f"[EXECUTOR] 🚀 Running: {sanitized}")
        
        # Run the command
        result = subprocess.run(
            [shell] + shell_args + [sanitized],
            cwd=request.cwd,
            capture_output=True,
            timeout=timeout,
            text=True,
            env={
                **subprocess.run.__globals__.get("os", __import__("os")).environ,
                "CI": "true",
                "npm_config_yes": "true",
            }
        )
        
        duration = int((time.time() - start_time) * 1000)
        
        logger.info(f"[EXECUTOR] {'✅' if result.returncode == 0 else '❌'} Exit code: {result.returncode} in {duration}ms")
        
        return CommandResult(
            success=result.returncode == 0,
            exit_code=result.returncode,
            stdout=result.stdout[:10000] if result.stdout else "",  # Limit output size
            stderr=result.stderr[:5000] if result.stderr else "",
            duration_ms=duration
        )
        
    except subprocess.TimeoutExpired as e:
        duration = int((time.time() - start_time) * 1000)
        logger.warning(f"[EXECUTOR] ⏰ Command timed out after {timeout}s")
        return CommandResult(
            success=False,
            error=f"Command timed out after {timeout} seconds",
            stdout=e.stdout[:5000] if e.stdout else "",
            stderr=e.stderr[:2500] if e.stderr else "",
            timed_out=True,
            duration_ms=duration
        )
        
    except Exception as e:
        duration = int((time.time() - start_time) * 1000)
        logger.error(f"[EXECUTOR] ❌ Execution error: {e}")
        return CommandResult(
            success=False,
            error=str(e),
            duration_ms=duration
        )


def execute_command_sync(request: CommandRequest) -> CommandResult:
    """
    Synchronous version for non-async contexts.
    """
    import asyncio
    return asyncio.get_event_loop().run_until_complete(execute_command(request))
