"""
PTY Executor Module

Async PTY-based command execution with real-time output streaming.
Enables the agent to interact with interactive terminal commands.

Features:
- Real-time output streaming via asyncio
- Prompt detection and auto-response
- Configurable timeout handling
- Proper resource cleanup

Usage:
    result = await execute_with_pty(
        command="npx create-vite@latest .",
        cwd="/path/to/project",
        timeout=300
    )
"""

import asyncio
import platform
import time
import logging
from typing import Optional, Callable, AsyncGenerator, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from .models import CommandRequest, CommandResult
from .security import validate_command, get_allowed_command_config
from .prompt_patterns import detect_prompt, get_auto_response, is_waiting_for_input

logger = logging.getLogger("ships.terminal")


@dataclass
class PTYExecutionConfig:
    """
    Configuration for PTY execution.
    
    Attributes:
        timeout: Maximum execution time in seconds.
        prompt_timeout: Time to wait before checking for prompts.
        max_output_size: Maximum output buffer size in bytes.
        auto_respond_prompts: Whether to automatically respond to known prompts.
    """
    timeout: float = 300.0
    prompt_timeout: float = 3.0
    max_output_size: int = 100_000
    auto_respond_prompts: bool = True


@dataclass
class PTYResult:
    """
    Result from PTY command execution.
    
    Attributes:
        success: Whether the command completed successfully.
        exit_code: Process exit code (None if timed out or error).
        output: Combined stdout/stderr output.
        prompts_handled: Number of prompts automatically handled.
        timed_out: Whether execution timed out.
        error: Error message if execution failed.
        duration_ms: Execution duration in milliseconds.
    """
    success: bool
    exit_code: Optional[int] = None
    output: str = ""
    prompts_handled: int = 0
    timed_out: bool = False
    error: Optional[str] = None
    duration_ms: int = 0


def get_shell_command() -> Tuple[str, list]:
    """
    Get the shell executable and arguments for the current platform.
    
    Returns:
        Tuple of (shell_path, shell_args).
    """
    if platform.system() == "Windows":
        return "cmd.exe", ["/c"]
    return "/bin/bash", ["-c"]


def get_environment() -> dict:
    """
    Get environment variables for PTY execution.
    
    Sets variables to encourage non-interactive behavior while
    still allowing the PTY to function for true interactive cases.
    
    Returns:
        Environment dictionary.
    """
    import os
    return {
        **os.environ,
        "CI": "true",
        "npm_config_yes": "true",
        "NPM_CONFIG_YES": "true",
        "TERM": "xterm-256color",  # Full terminal for PTY
        "FORCE_COLOR": "0",
        "NO_COLOR": "1",
        "npm_config_loglevel": "warn",
    }


async def execute_with_pty(
    command: str,
    cwd: str,
    config: Optional[PTYExecutionConfig] = None,
    on_output: Optional[Callable[[str], None]] = None,
) -> PTYResult:
    """
    Execute a command using async subprocess with PTY-like behavior.
    
    Streams output in real-time, detects interactive prompts,
    and automatically responds to known prompts.
    
    Args:
        command: The command to execute.
        cwd: Working directory for the command.
        config: Execution configuration.
        on_output: Optional callback for real-time output chunks.
        
    Returns:
        PTYResult with execution details.
        
    Raises:
        No exceptions raised - errors returned in PTYResult.
    """
    config = config or PTYExecutionConfig()
    start_time = time.time()
    
    # Validate first
    is_valid, error, sanitized = validate_command(command, cwd)
    if not is_valid:
        logger.warning(f"[PTY] ❌ Validation failed: {error}")
        return PTYResult(
            success=False,
            error=error,
            duration_ms=int((time.time() - start_time) * 1000)
        )
    
    shell, shell_args = get_shell_command()
    env = get_environment()
    
    # Get timeout from security config
    cmd_config = get_allowed_command_config(command)
    timeout = min(config.timeout, cmd_config.max_timeout if cmd_config else 300)
    
    output_buffer = []
    prompts_handled = 0
    
    try:
        logger.info(f"[PTY] 🚀 Starting: {sanitized}")
        
        # Create subprocess with pipes
        process = await asyncio.create_subprocess_shell(
            f'{shell} {" ".join(shell_args)} "{sanitized}"',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            stdin=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
        )
        
        async def read_output():
            """Read output from process."""
            nonlocal output_buffer, prompts_handled
            last_output_time = time.time()
            
            while True:
                try:
                    # Read with timeout
                    chunk = await asyncio.wait_for(
                        process.stdout.read(1024),
                        timeout=config.prompt_timeout
                    )
                    
                    if not chunk:
                        break
                    
                    text = chunk.decode('utf-8', errors='replace')
                    output_buffer.append(text)
                    last_output_time = time.time()
                    
                    # Callback for real-time streaming
                    if on_output:
                        on_output(text)
                    
                    # Limit buffer size
                    full_output = ''.join(output_buffer)
                    if len(full_output) > config.max_output_size:
                        # Keep last portion
                        output_buffer = [full_output[-config.max_output_size:]]
                    
                    # Check for prompts if auto-respond is enabled
                    if config.auto_respond_prompts:
                        prompt = detect_prompt(full_output)
                        if prompt:
                            response = get_auto_response(prompt)
                            if response and process.stdin:
                                logger.info(f"[PTY] 📝 Sending auto-response for: {prompt.name}")
                                process.stdin.write(response.encode())
                                await process.stdin.drain()
                                prompts_handled += 1
                                
                except asyncio.TimeoutError:
                    # No output for prompt_timeout seconds
                    # Check if likely waiting for input
                    current_output = ''.join(output_buffer)
                    if is_waiting_for_input(current_output):
                        # Try sending Enter if stuck
                        idle_time = time.time() - last_output_time
                        if idle_time > config.prompt_timeout * 2:
                            logger.warning("[PTY] Process seems stuck, sending Enter")
                            if process.stdin:
                                process.stdin.write(b'\n')
                                await process.stdin.drain()
                    
                    # Check total timeout
                    if time.time() - start_time > timeout:
                        logger.warning(f"[PTY] ⏰ Timeout after {timeout}s")
                        raise asyncio.TimeoutError()
                    
                    continue
        
        # Run with overall timeout
        try:
            await asyncio.wait_for(read_output(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"[PTY] ⏰ Command timed out after {timeout}s")
            process.kill()
            return PTYResult(
                success=False,
                output=''.join(output_buffer),
                prompts_handled=prompts_handled,
                timed_out=True,
                error=f"Command timed out after {timeout} seconds",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        
        # Wait for process to complete
        exit_code = await process.wait()
        duration = int((time.time() - start_time) * 1000)
        
        output = ''.join(output_buffer)
        success = exit_code == 0
        
        logger.info(f"[PTY] {'✅' if success else '❌'} Exit code: {exit_code} in {duration}ms (handled {prompts_handled} prompts)")
        
        return PTYResult(
            success=success,
            exit_code=exit_code,
            output=output[:config.max_output_size],
            prompts_handled=prompts_handled,
            duration_ms=duration
        )
        
    except Exception as e:
        duration = int((time.time() - start_time) * 1000)
        logger.error(f"[PTY] ❌ Execution error: {e}")
        return PTYResult(
            success=False,
            output=''.join(output_buffer),
            error=str(e),
            duration_ms=duration
        )


async def execute_command_streaming(
    request: CommandRequest
) -> AsyncGenerator[str, None]:
    """
    Execute a command and yield output chunks in real-time.
    
    This is a generator version that allows the caller to process
    output as it arrives.
    
    Args:
        request: Command request with command and cwd.
        
    Yields:
        Output chunks as they arrive.
    """
    output_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
    
    async def on_output(chunk: str):
        await output_queue.put(chunk)
    
    # Start execution in background
    async def run():
        result = await execute_with_pty(
            command=request.command,
            cwd=request.cwd,
            config=PTYExecutionConfig(timeout=request.timeout or 300),
            on_output=lambda chunk: asyncio.create_task(output_queue.put(chunk))
        )
        await output_queue.put(None)  # Signal completion
        return result
    
    execution_task = asyncio.create_task(run())
    
    # Yield chunks as they arrive
    while True:
        chunk = await output_queue.get()
        if chunk is None:
            break
        yield chunk
    
    # Ensure task is complete
    await execution_task
