"""
Terminal Execution Types

Pydantic models for terminal command execution.
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class CommandStatus(str, Enum):
    """Status of a command execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


class CommandRequest(BaseModel):
    """Request to execute a terminal command."""
    command: str = Field(..., description="The command to execute")
    cwd: str = Field(..., description="Working directory (project path)")
    timeout: Optional[int] = Field(60, description="Timeout in seconds")


class CommandResult(BaseModel):
    """Result of a command execution."""
    success: bool
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None
    timed_out: bool = False
    duration_ms: int = 0


class AllowedCommand(BaseModel):
    """Configuration for an allowed command prefix."""
    prefix: str
    description: str
    max_timeout: int = 300  # seconds
    requires_approval: bool = False
